from django.contrib import admin
from .models import AuditSession, CatalogItem, AuditLogEntry, AuditorSession


@admin.register(AuditSession)
class AuditSessionAdmin(admin.ModelAdmin):
    list_display = ['name', 'session_pin', 'status', 'created_at', 'completed_at']
    list_filter = ['status']
    search_fields = ['name', 'session_pin']
    readonly_fields = ['id', 'session_pin', 'created_at']


@admin.register(CatalogItem)
class CatalogItemAdmin(admin.ModelAdmin):
    list_display = ['product_name', 'barcode', 'session', 'expected_quantity']
    list_filter = ['session']
    search_fields = ['product_name', 'barcode']


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ['barcode', 'delta', 'auditor_id', 'zone', 'timestamp', 'synced', 'is_unlisted']
    list_filter = ['synced', 'is_unlisted', 'session', 'zone']
    search_fields = ['barcode', 'auditor_id']
    readonly_fields = ['id', 'created_at']


@admin.register(AuditorSession)
class AuditorSessionAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'zone', 'session', 'joined_at', 'last_active', 'is_online']
    list_filter = ['session', 'is_online']
    search_fields = ['nickname', 'zone']
