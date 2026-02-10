from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
from project.models import PageView, Website
import uuid

class Command(BaseCommand):
    help = 'Generates sample pageview data for the specified time period'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Number of days to generate data for'
        )
        parser.add_argument(
            '--max-daily-views',
            type=int,
            default=20000,
            help='Maximum number of daily views to generate'
        )

    def handle(self, *args, **kwargs):
        # More realistic and varied data
        paths = [
            '/', '/home', '/about', '/blog', '/contact', '/products', '/services',
            '/blog/post-1', '/blog/post-2', '/blog/how-to-guide', '/blog/tutorial',
            '/products/item-1', '/products/item-2', '/products/category/tech',
            '/portfolio', '/projects', '/pricing', '/faq', '/terms', '/privacy',
            '/api/docs', '/documentation', '/getting-started', '/download'
        ]

        # Include None for blank referrers (direct traffic)
        referrers = [
            None, None, None, None,  # 40% chance of no referrer (direct traffic)
            'https://www.google.com/search',
            'https://www.google.com',
            'https://www.bing.com/search',
            'https://search.yahoo.com',
            'https://duckduckgo.com',
            'https://twitter.com',
            'https://t.co',
            'https://www.facebook.com',
            'https://www.reddit.com',
            'https://news.ycombinator.com',
            'https://www.linkedin.com',
            'https://github.com',
            'https://stackoverflow.com',
            'https://dev.to',
            'https://medium.com'
        ]

        devices = [
            'Desktop', 'Desktop', 'Desktop',  # Desktop is more common
            'Mobile', 'Mobile', 'Mobile', 'Mobile', 'Mobile',  # Mobile is most common
            'Tablet'
        ]

        browsers = [
            'Chrome', 'Chrome', 'Chrome', 'Chrome', 'Chrome',  # Chrome most common
            'Safari', 'Safari', 'Safari',
            'Firefox', 'Firefox',
            'Edge', 'Edge',
            'Opera',
            'Brave',
            'Samsung Internet',
            'Chrome Mobile',
            'Safari Mobile'
        ]

        languages = [
            'en', 'en', 'en', 'en', 'en',  # English most common
            'es', 'es',
            'fr',
            'de',
            'zh',
            'ja',
            'pt',
            'ru',
            'it',
            'nl',
            'pl',
            'ko',
            'ar'
        ]

        countries = [
            'US', 'US', 'US', 'US', 'US',  # US most common
            'GB', 'GB',
            'CA', 'CA',
            'DE',
            'FR',
            'AU',
            'IN',
            'BR',
            'NL',
            'ES',
            'IT',
            'SE',
            'JP',
            'KR',
            'CN',
            'MX',
            'PL',
            'BE',
            'CH'
        ]

        # Get all existing websites
        websites = list(Website.objects.all())
        if not websites:
            self.stdout.write(self.style.WARNING('No websites found in database. Creating a test website.'))
            website = Website.objects.create(id="TEST", name="Test Website")
            websites = [website]
        else:
            self.stdout.write(f"Found {len(websites)} websites:")
            for w in websites:
                self.stdout.write(f"  - {w.id}: {w.name}")

        end_date = timezone.now()
        start_date = end_date - timedelta(days=kwargs['days'])
        current_date = start_date

        total_views_created = 0

        self.stdout.write(f"\nGenerating data from {start_date.date()} to {end_date.date()}")
        self.stdout.write(f"Max daily views: {kwargs['max_daily_views']}\n")

        while current_date <= end_date:
            # Random number of views per day (0 to max)
            daily_views = random.randint(0, kwargs['max_daily_views'])

            for _ in range(daily_views):
                # Pick a random website
                website = random.choice(websites)

                # Random timestamp within the day
                random_seconds = random.randint(0, 86400)
                timestamp = current_date + timedelta(seconds=random_seconds)

                # Randomly leave some fields blank
                referrer = random.choice(referrers)
                browser = random.choice(browsers) if random.random() > 0.02 else ''  # 2% blank
                device = random.choice(devices) if random.random() > 0.01 else ''  # 1% blank
                country = random.choice(countries) if random.random() > 0.05 else ''  # 5% blank
                language = random.choice(languages) if random.random() > 0.03 else ''  # 3% blank

                pageview = PageView.objects.create(
                    website=website,
                    hash_id=str(uuid.uuid4())[:8],
                    path=random.choice(paths),
                    referrer=referrer,
                    device=device,
                    browser=browser,
                    country=country,
                    language=language,
                )
                PageView.objects.filter(id=pageview.id).update(timestamp=timestamp)
                total_views_created += 1

            current_date += timedelta(days=1)
            if current_date.day == 1 or current_date == end_date:
                self.stdout.write(f"Progress: {current_date.strftime('%B %d, %Y')} - Total views: {total_views_created:,}")

        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully generated {total_views_created:,} pageviews over {kwargs["days"]} days'))