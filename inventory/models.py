"""
Models for device inventory management
"""

import uuid
from django.db import models
from core.models import Device


class InventorySnapshot(models.Model):
    """Snapshot of device inventory at a point in time"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='inventory_snapshots')
    collected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-collected_at']
        indexes = [
            models.Index(fields=['device', '-collected_at']),
        ]
    
    def __str__(self):
        return f"{self.device.hostname} - {self.collected_at}"
    
    def service_count(self):
        return self.services.count()
    
    def application_count(self):
        return self.applications.count()


class ServiceInventory(models.Model):
    """Windows service inventory"""
    
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('paused', 'Paused'),
        ('unknown', 'Unknown'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(
        InventorySnapshot,
        on_delete=models.CASCADE,
        related_name='services'
    )
    
    # Service details
    name = models.CharField(max_length=255, db_index=True)  # Service name
    display_name = models.CharField(max_length=255)  # Display name
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    
    # Additional metadata (optional)
    startup_type = models.CharField(max_length=50, blank=True)  # Auto, Manual, Disabled
    path = models.TextField(blank=True)  # Executable path
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['snapshot', 'name']),
            models.Index(fields=['name', 'status']),
        ]
    
    def __str__(self):
        return f"{self.display_name} ({self.status})"


class ApplicationInventory(models.Model):
    """Installed application inventory (from Windows Registry)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(
        InventorySnapshot,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    
    # Application details
    display_name = models.CharField(max_length=255, db_index=True)
    version = models.CharField(max_length=100, blank=True)
    publisher = models.CharField(max_length=255, blank=True, db_index=True)
    
    # Additional metadata (optional)
    install_date = models.DateField(null=True, blank=True)
    install_location = models.TextField(blank=True)
    uninstall_string = models.TextField(blank=True)
    estimated_size = models.BigIntegerField(null=True, blank=True)  # KB
    
    class Meta:
        ordering = ['display_name']
        indexes = [
            models.Index(fields=['snapshot', 'display_name']),
            models.Index(fields=['publisher', 'display_name']),
        ]
    
    def __str__(self):
        version_str = f" v{self.version}" if self.version else ""
        return f"{self.display_name}{version_str}"


class InventoryChange(models.Model):
    """Track changes in inventory over time"""
    
    CHANGE_TYPE_CHOICES = [
        ('service_added', 'Service Added'),
        ('service_removed', 'Service Removed'),
        ('service_status_changed', 'Service Status Changed'),
        ('app_installed', 'Application Installed'),
        ('app_uninstalled', 'Application Uninstalled'),
        ('app_updated', 'Application Updated'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='inventory_changes')
    
    # Change details
    change_type = models.CharField(max_length=30, choices=CHANGE_TYPE_CHOICES, db_index=True)
    item_name = models.CharField(max_length=255, db_index=True)
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    
    # Metadata
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    previous_snapshot = models.ForeignKey(
        InventorySnapshot,
        on_delete=models.SET_NULL,
        null=True,
        related_name='changes_from'
    )
    current_snapshot = models.ForeignKey(
        InventorySnapshot,
        on_delete=models.SET_NULL,
        null=True,
        related_name='changes_to'
    )
    
    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['device', '-detected_at']),
            models.Index(fields=['change_type', '-detected_at']),
        ]
    
    def __str__(self):
        return f"{self.device.hostname} - {self.change_type} - {self.item_name}"
