from django.contrib import admin
from inventory.models import InventorySnapshot, ServiceInventory, ApplicationInventory, InventoryChange

@admin.register(InventorySnapshot)
class InventorySnapshotAdmin(admin.ModelAdmin):
    list_display = ['device', 'collected_at', 'service_count', 'application_count']
    list_filter = ['collected_at']
    search_fields = ['device__hostname']

@admin.register(ServiceInventory)
class ServiceInventoryAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'status', 'snapshot']
    list_filter = ['status']
    search_fields = ['display_name', 'name']

@admin.register(ApplicationInventory)
class ApplicationInventoryAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'version', 'publisher', 'snapshot']
    search_fields = ['display_name', 'publisher']

@admin.register(InventoryChange)
class InventoryChangeAdmin(admin.ModelAdmin):
    list_display = ['device', 'change_type', 'item_name', 'detected_at']
    list_filter = ['change_type', 'detected_at']
    search_fields = ['item_name', 'device__hostname']
