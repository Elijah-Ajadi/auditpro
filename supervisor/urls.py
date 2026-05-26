from django.urls import path
from . import views, exports

app_name = 'supervisor'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('create/', views.audit_create, name='audit_create'),
    path('upload/<uuid:session_id>/', views.audit_upload, name='audit_upload'),
    path('upload/<uuid:session_id>/map/', views.submit_column_mapping, name='submit_column_mapping'),
    path('upload/<uuid:session_id>/confirm/', views.confirm_import, name='confirm_import'),
    path('session/<uuid:session_id>/', views.session_detail, name='session_detail'),
    path('monitor/<uuid:session_id>/', views.monitor, name='monitor'),
    path('session/<uuid:session_id>/monitor/refresh/', views.monitor_refresh, name='monitor_refresh'),
    path('session/<uuid:session_id>/variance/', views.variance, name='variance'),
    path('session/<uuid:session_id>/variance/recount/<str:barcode>/', views.trigger_recount, name='trigger_recount'),
    
    # Exports
    path('session/<uuid:session_id>/export/reconciliation/', exports.export_variance_csv, name='export_reconciliation'),
    path('session/<uuid:session_id>/export/audit-trail/', exports.export_audit_trail_csv, name='export_audit_trail'),
    path('session/<uuid:session_id>/export/adjustment/', exports.export_adjustment_json, name='export_adjustment'),
    path('session/<uuid:session_id>/export/summary/', exports.executive_summary, name='executive_summary'),
    
    path('session/<uuid:session_id>/archive/', views.archive_session, name='archive_session'),
    path('archives/', views.archived_sessions, name='archived_sessions'),
    
    # Team Management
    path('team/', views.team_list, name='team_list'),
    path('team/create/', views.user_create, name='user_create'),
]
