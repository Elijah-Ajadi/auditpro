from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('sync/', views.sync_endpoint, name='sync_endpoint'),
    path('catalog/<str:session_id>/', views.catalog_api, name='catalog_api'),
    path('recount/<str:session_id>/', views.recount_tasks, name='recount_tasks'),
]
