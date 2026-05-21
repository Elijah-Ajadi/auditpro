from django.urls import path
from . import views

app_name = 'supervisor'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('create/', views.audit_create, name='audit_create'),
    path('upload/<uuid:session_id>/', views.audit_upload, name='audit_upload'),
    path('upload/<uuid:session_id>/map/', views.submit_column_mapping, name='submit_column_mapping'),
    path('upload/<uuid:session_id>/confirm/', views.confirm_import, name='confirm_import'),
    path('session/<uuid:session_id>/', views.session_detail, name='session_detail'),
    path('monitor/<uuid:session_id>/', views.monitor, name='monitor'),
    path('monitor/<uuid:session_id>/refresh/', views.monitor_refresh, name='monitor_refresh'),
    path('variance/<uuid:session_id>/', views.variance, name='variance'),
    path('variance/<uuid:session_id>/recount/<str:barcode>/', views.trigger_recount, name='trigger_recount'),
    path('session/<uuid:session_id>/archive/', views.archive_session, name='archive_session'),
    path('archives/', views.archived_sessions, name='archived_sessions'),
]
