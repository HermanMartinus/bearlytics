import os
import random
import string
import hashlib
import base64
from datetime import timedelta
import user_agents
import geoip2

from django.utils import timezone
from django.db.models import Q
from django.db import connection
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib.gis.geoip2 import GeoIP2
from django.contrib.auth.models import User

from .models import PageView, Website


PIXEL = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")

SALT_SECRET = os.getenv("SALT_SECRET")


def hit(request, website_id):
    website = get_object_or_404(Website, id=website_id)

    if request.method == "OPTIONS":
        response = HttpResponse()
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response
    
    # Set response headers
    response = HttpResponse(PIXEL, content_type='image/png')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, OPTIONS"

    # Parse User-Agent
    ua_string = request.META.get('HTTP_USER_AGENT', '')
    user_agent = user_agents.parse(ua_string)
    
    # Skip bots
    if (user_agent.is_bot or 
        any(bot_keyword in ua_string.lower() 
            for bot_keyword in ['bot', 'crawler', 'spider', 'headless', 'puppet'])):
        return response
        
    browser = user_agent.browser.family
    browser = browser.replace("Mobile", "").replace("iOS", "").replace("WebView", "").replace("UI/WK", "").strip()
    device = "Mobile" if user_agent.is_mobile else "Desktop"

    # Get the real IP address
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '') or \
         request.META.get('HTTP_CF_CONNECTING_IP', '') or \
         request.META.get('REMOTE_ADDR', '')
    ip = ip.split(',')[0].strip()

    # Get country from CloudFlare header (if available) otherwise do an IP lookup
    country = request.META.get('HTTP_CF_IPCOUNTRY', get_country(ip))

    # Generate ID using IP, User Agent, current date, and secret
    date = timezone.now().strftime('%Y-%m-%d')
    data = f"{ip}|{ua_string}|{date}|{SALT_SECRET}"
    hash_id = hashlib.sha256(data.encode()).hexdigest()

    # Get path, and ref from query parameter
    path = request.GET.get('path', '/')
    if not path.startswith('/'):
        path = '/' + path

    referrer = request.GET.get('ref', 'direct')
    if referrer == "":
        referrer = "direct"
    referrer = referrer.replace('http://', '').replace('https://', '').replace('www.', '').split('/')[0]

    # Extract basic language code
    language = extract_basic_language(request.META.get('HTTP_ACCEPT_LANGUAGE', ''))

    PageView.objects.create(
        website=website,
        hash_id=hash_id,
        path=path,
        referrer=referrer,
        device=device,
        browser=browser,
        country=country,
        language=language
    )

    return response


def get_country(user_ip):
    # Test IPs from different countries
    # user_ip = '45.222.31.178'  # South Africa
    # user_ip = '103.48.198.141'  # India
    # user_ip = '185.53.179.29'  # Germany 
    # user_ip = '156.146.56.161'  # United States
    # user_ip = '223.252.33.75'  # China
    # user_ip = '197.255.255.246'  # Nigeria
    # user_ip = '1.179.183.86'  # Thailand
    try:
        g = GeoIP2()
        country = g.country(user_ip)

        return country['country_name']
    except (geoip2.errors.AddressNotFoundError, Exception):
        return 'unknown'


def extract_basic_language(lang_header):
    if not lang_header:
        return "unknown"
    lang_parts = lang_header.split(',')
    return lang_parts[0].split('-')[0]


@login_required(login_url='login')
def websites(request):
    if request.method == 'POST':
        website_name = request.POST.get('website_name')
        if website_name:
            website_id = generate_website_id()
            # Create new website object
            Website.objects.create(
                name=website_name,
                id=website_id
            )
            messages.success(request, 'Website added successfully!')
            return redirect('websites')
        else:
            messages.error(request, 'Website name is required.')
    
    websites = Website.objects.all()
    return render(request, 'websites.html', {"websites": websites})


@login_required(login_url='login')
def dashboard(request, website_id):
    website = get_object_or_404(Website, id=website_id)

    time_range = request.GET.get('range', '24h')
    end_time = timezone.now().replace(minute=59, second=59, microsecond=999999)
    
    ranges = {
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
        '90d': timedelta(days=90),
        '180d': timedelta(days=180),
        '365d': timedelta(days=365)
    }
    start_time = end_time - ranges.get(time_range, ranges['24h'])

    # Optimize base query by selecting only needed fields
    base_query = PageView.objects.filter(
        website=website,
        timestamp__range=(start_time, end_time)
    ).only('hash_id', 'path', 'referrer', 'browser', 'country', 'device', 'timestamp')
    
    # Add filters
    path_filter = request.GET.get('path')
    referrer_filter = request.GET.get('referrer')

    if path_filter:
        base_query = base_query.filter(path=path_filter)
    if referrer_filter:
        base_query = base_query.filter(referrer=referrer_filter)

    where_conditions = [
        'website_id = %s',
        'timestamp BETWEEN %s AND %s'
    ]
    params = [website.id, start_time, end_time]

    if path_filter:
        where_conditions.append('path = %s')
        params.append(path_filter)
    if referrer_filter:
        where_conditions.append('referrer = %s')
        params.append(referrer_filter)

    where_clause = ' AND '.join(where_conditions)

    def get_top_metrics(column, limit=100):
        """Helper function to get top metrics for a given column"""
        return (base_query
            .values(column)
            .annotate(
                visits=Count('hash_id', distinct=True)
            )
            .order_by('-visits')[:limit])

    # Get overall stats using raw SQL for better performance
    stats_sql = f"""
        SELECT
            COUNT(*) as views,
            COUNT(DISTINCT hash_id || path) as visits,
            COUNT(DISTINCT hash_id) as visitors,
            COUNT(DISTINCT path) as unique_pages,
            COUNT(DISTINCT browser) as unique_browsers,
            COUNT(DISTINCT country) as unique_countries
        FROM pageviews
        WHERE {where_clause}
    """

    with connection.cursor() as cursor:
        cursor.execute(stats_sql, params)
        row = cursor.fetchone()
        stats = {
            'views': row[0],
            'visits': row[1],
            'visitors': row[2],
            'unique_pages': row[3],
            'unique_browsers': row[4],
            'unique_countries': row[5]
        }
    
    # Determine time grouping based on duration
    duration = end_time - start_time
    if duration <= timedelta(hours=24):
        truncate_func = 'hour'
        date_format = '%Y-%m-%d %H:00'
    elif duration <= timedelta(days=90):
        truncate_func = 'day'
        date_format = '%Y-%m-%d'
    else:
        truncate_func = 'month'
        date_format = '%Y-%m'

    # Optimized time series query using raw SQL for better performance
    # This is much faster than Window functions for large datasets
    # Use strftime for SQLite datetime formatting (escape % for Django)
    if truncate_func == 'hour':
        period_format = '%%Y-%%m-%%d %%H:00:00'
    elif truncate_func == 'day':
        period_format = '%%Y-%%m-%%d 00:00:00'
    else:  # month
        period_format = '%%Y-%%m-01 00:00:00'

    # Optimized query with better CTE structure
    time_series_sql = f"""
        WITH periods AS (
            SELECT strftime('{period_format}', timestamp) as period
            FROM pageviews
            WHERE {where_clause}
            GROUP BY period
        ),
        views_per_period AS (
            SELECT
                strftime('{period_format}', timestamp) as period,
                COUNT(*) as view_count
            FROM pageviews
            WHERE {where_clause}
            GROUP BY period
        ),
        first_visits AS (
            SELECT
                hash_id,
                path,
                MIN(timestamp) as first_timestamp
            FROM pageviews
            WHERE {where_clause}
            GROUP BY hash_id, path
        ),
        visits_per_period AS (
            SELECT
                strftime('{period_format}', first_timestamp) as period,
                COUNT(*) as visit_count
            FROM first_visits
            GROUP BY period
        )
        SELECT
            p.period,
            COALESCE(v.view_count, 0) as views,
            COALESCE(vp.visit_count, 0) as visits
        FROM periods p
        LEFT JOIN views_per_period v ON p.period = v.period
        LEFT JOIN visits_per_period vp ON p.period = vp.period
        ORDER BY p.period
    """

    # Need to repeat params for each WHERE clause in the CTEs
    time_series_params = params * 3  # 3 CTEs use the where_clause

    with connection.cursor() as cursor:
        cursor.execute(time_series_sql, time_series_params)
        columns = [col[0] for col in cursor.description]
        time_series = [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]
    
    # Format time series data for the template
    time_labels = []
    views_data = []
    visits_data = []
    
    # Create time slots and initialize with zeros
    current = start_time
    end_time_slots = timezone.now() + timedelta(hours=1)
    
    total_time_series_visits = 0
    
    # Adjust the time slot creation for monthly grouping
    while current <= end_time_slots:
        time_labels.append(current.strftime(date_format))
        views_data.append(0)
        visits_data.append(0)
        if duration <= timedelta(hours=24):
            current += timedelta(hours=1)
        else:
            current += timedelta(days=1)
        # else:
        #     # Add one month
        #     if current.month == 12:
        #         current = current.replace(year=current.year + 1, month=1)
        #     else:
        #         current = current.replace(month=current.month + 1)
    
    # Fill in actual data
    # Period from raw SQL is already a formatted string
    time_data_map = {}
    for ts in time_series:
        # Convert SQLite datetime string to Python datetime for formatting
        period_str = ts['period']
        if not period_str:
            continue
        try:
            dt = timezone.datetime.strptime(period_str, '%Y-%m-%d %H:%M:%S')
            formatted_period = dt.strftime(date_format)
            time_data_map[formatted_period] = (ts['views'], ts['visits'])
        except (ValueError, KeyError, TypeError) as e:
            continue
    
    for i, label in enumerate(time_labels):
        if label in time_data_map:
            views_data[i] = time_data_map[label][0]
            visits_data[i] = time_data_map[label][1]
            total_time_series_visits += time_data_map[label][1]
    
    context = {
        'website': website,
        'stats': stats,
        'time_labels': time_labels[1:],
        'views_data': views_data[1:],
        'visits_data': visits_data[1:],
        'top_pages': get_top_metrics('path'),
        'top_referrers': get_top_metrics('referrer'),
        'top_countries': get_top_metrics('country'),
        'top_devices': get_top_metrics('device'),
        'top_browsers': get_top_metrics('browser'),
        'selected_range': time_range,
        'path_filter': path_filter,
        'referrer_filter': referrer_filter,
    }
    
    return render(request, 'dashboard.html', context)


def generate_website_id():
    # Generate a random 7-character string using uppercase letters
    return ''.join(random.choices(string.ascii_uppercase, k=7))


@login_required(login_url='login')
def all_hits(request):
    hits = PageView.objects.all().order_by('-timestamp')[:100]
    return render(request, 'all_hits.html', {'hits': hits})


@login_required(login_url='login')
def delete_website(request, website_id):
    if request.method == 'POST':
        website = get_object_or_404(Website, id=website_id)
        website.delete()
        messages.success(request, 'Website deleted successfully!')
    return redirect('websites')


def login_view(request):
    # Check if any users exist
    if User.objects.count() == 0:
        # Handle registration
        if request.method == 'POST':
            username = request.POST.get('username')
            password = request.POST.get('password')
            
            if username and password:
                # Create superuser
                User.objects.create_superuser(username=username, password=password)
                # Log them in
                user = authenticate(request, username=username, password=password)
                login(request, user)
                messages.success(request, 'Account created successfully!')
                return redirect('websites')
            else:
                messages.error(request, 'Both username and password are required.')
        
        return render(request, 'login.html', {'is_registration': True})
    
    # Normal login flow
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('websites')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'login.html', {'is_registration': False})