from django.urls import path
from . import views

app_name = 'auditor'

urlpatterns = [
    path('join/', views.join, name='join'),
    path('join/<str:session_pin>/', views.join_with_pin, name='join_with_pin'),
    path('authenticate/', views.authenticate, name='authenticate'),
    path('hydrate/', views.hydrate, name='hydrate'),
    path('catalog.json', views.catalog_json, name='catalog_json'),
    path('scan/', views.scan, name='scan'),
    path('sw.js', views.service_worker, name='service_worker'),
]
