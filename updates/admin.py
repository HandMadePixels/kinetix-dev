from django.contrib import admin
from updates.models import Update, UpdatePush, ScanResult

@admin.register(Update)
class UpdateAdmin(admin.ModelAdmin):
    list_display = ['version', 'file', 'scan_status', 'uploaded_at', 'uploaded_by']
    list_filter = ['scan_status', 'uploaded_at']
    search_fields = ['version', 'description']
    readonly_fields = ['sha256_hash', 'signature', 'uploaded_at']

@admin.register(UpdatePush)
class UpdatePushAdmin(admin.ModelAdmin):
    list_display = ['update', 'device', 'status', 'pushed_at', 'retry_count']
    list_filter = ['status', 'pushed_at']
    search_fields = ['device__hostname', 'update__version']

@admin.register(ScanResult)
class ScanResultAdmin(admin.ModelAdmin):
    list_display = ['update', 'scanner', 'is_clean', 'scanned_at']
    list_filter = ['scanner', 'is_clean']
    search_fields = ['update__version', 'raw_response']
