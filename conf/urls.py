from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from project import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.websites, name='websites'),
    path('login/', views.login_view, name='login'),
    path('<website_id>/dashboard/', views.dashboard, name='dashboard'),
    path('<website_id>/delete/', views.delete_website, name='delete_website'),
    path('<website_id>/hit', views.hit, name='hit'),
    path('script.js', TemplateView.as_view(template_name='script.js', content_type='application/javascript'), name='script'),
    path('all-hits/', views.all_hits, name='all_hits'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain'), name='robots'),
]
