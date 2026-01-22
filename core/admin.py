from django.contrib import admin
from core.models import Device, DeviceGroup, AuditLog, SystemConfig, RSAKeyPair

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['hostname', 'ip_address', 'os_version', 'status', 'last_seen', 'is_online']
    list_filter = ['status', 'group', 'registered_at']
    search_fields = ['hostname', 'ip_address']
    readonly_fields = ['id', 'registered_at', 'last_seen']
    
    def is_online(self, obj):
        return obj.is_online()
    is_online.boolean = True

@admin.register(DeviceGroup)
class DeviceGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'device_count', 'created_at']
    search_fields = ['name']
    
    def device_count(self, obj):
        return obj.device_count()

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'action', 'severity', 'user', 'device', 'ip_address']
    list_filter = ['action', 'severity', 'timestamp']
    search_fields = ['description', 'ip_address']
    readonly_fields = [f.name for f in AuditLog._meta.get_fields() if not f.auto_created]
    
    def has_add_permission(self, request):
        return False

@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ['server_url', 'updated_at', 'updated_by']
    
    def has_add_permission(self, request):
        # Already exists as singleton
        return not SystemConfig.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(RSAKeyPair)
class RSAKeyPairAdmin(admin.ModelAdmin):
    list_display = ['created_at']
    readonly_fields = ['public_key', 'created_at']
    
    def has_add_permission(self, request):
        return not RSAKeyPair.objects.exists()
