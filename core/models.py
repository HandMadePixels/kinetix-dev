"""
Core models for device management and system configuration
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from core.fields import EncryptedTextField


from django.core.serializers.json import DjangoJSONEncoder


class Device(models.Model):
    """Registered endpoint device"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('blocked', 'Blocked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostname = models.CharField(max_length=255, unique=True, db_index=True)
    ip_address = models.GenericIPAddressField()
    os_version = models.CharField(max_length=255)
    current_user = models.CharField(max_length=255, blank=True, null=True)
    last_boot_time = models.DateTimeField(null=True, blank=True)
    uptime = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    
    # Authentication
    auth_token = EncryptedTextField()  # Encrypted JWT token
    
    # Metadata
    registered_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True, db_index=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Grouping
    group = models.ForeignKey('DeviceGroup', on_delete=models.SET_NULL, null=True, blank=True, related_name='devices')
    
    # Additional info
    notes = models.TextField(blank=True)
    refresh_inventory_requested = models.BooleanField(default=False)
    ip_mismatch = models.BooleanField(default=False, help_text="True if reported IP differs from connection IP")
    registration_public_key = models.TextField(blank=True, null=True, help_text="The agent's unique public key for re-registration challenges")
    registration_nonce = models.CharField(max_length=64, blank=True, null=True, help_text="Temporary nonce for secure token exchange")
    last_heartbeat_audit = models.DateTimeField(null=True, blank=True, help_text="Timestamp of the last time this device's heartbeat was audited")
    
    INVENTORY_STATUS_CHOICES = [
        ('idle', 'Idle'),
        ('requested', 'Requested'),
        ('processing', 'Processing'),
    ]
    inventory_refresh_status = models.CharField(
        max_length=20, 
        choices=INVENTORY_STATUS_CHOICES, 
        default='idle'
    )
    
    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['hostname', 'status']),
            models.Index(fields=['last_seen', 'status']),
        ]
        permissions = [
            ("can_view_details", "Can view detailed device info"),
            ("can_request_refresh", "Can request inventory refresh"),
        ]

    def __str__(self):
        return f"{self.hostname} ({self.ip_address})"
    
    @property
    def is_authenticated(self):
        """Always return True for registered devices"""
        return True

    @property
    def is_active(self):
        """Map status to is_active for compatibility"""
        return self.status == 'active'

    def is_online(self):
        """Check if device is online based on heartbeat"""
        from django.conf import settings
        try:
            from core.models import SystemConfig
            config = SystemConfig.get_config()
            timeout_seconds = config.device_heartbeat_timeout
        except:
            timeout_seconds = getattr(settings, 'DEVICE_HEARTBEAT_TIMEOUT', 300)
            
        timeout = timezone.timedelta(seconds=timeout_seconds + 60) # Add 1m grace period
        return timezone.now() - self.last_seen < timeout
    
    def update_heartbeat(self, ip_address=None, update_primary=True):
        """Update last seen timestamp and sync IP address with throttled auditing"""
        self.last_seen = timezone.now()
        if ip_address:
            self.last_ip = ip_address
            # Automatically update the primary IP if it has changed, but only if requested
            # or if we don't have one yet
            if (update_primary or not self.ip_address) and self.ip_address != ip_address:
                self.ip_address = ip_address
        
        # SECURITY FIX: Heartbeat Auditing (Throttled to once per hour)
        audit_threshold = timezone.now() - timezone.timedelta(hours=1)
        if not self.last_heartbeat_audit or self.last_heartbeat_audit < audit_threshold:
            AuditLog.objects.create(
                device=self,
                ip_address=ip_address or self.ip_address or '0.0.0.0',
                action='device_update',
                severity='info',
                description=f"Heartbeat received for {self.hostname}",
                metadata={'type': 'heartbeat', 'connection_ip': ip_address}
            )
            self.last_heartbeat_audit = timezone.now()
            
        self.save(update_fields=['last_seen', 'last_ip', 'ip_address', 'last_heartbeat_audit'])

    def get_latest_refresh_time(self):
        """Get the timestamp of the latest inventory snapshot"""
        snapshot = self.inventory_snapshots.order_by('-collected_at').first()
        return snapshot.collected_at if snapshot else None


class DeviceGroup(models.Model):
    """Device grouping for bulk operations"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def device_count(self):
        return self.devices.count()


class AuditLog(models.Model):
    """Comprehensive audit logging"""
    
    ACTION_CHOICES = [
        ('device_register', 'Device Registration'),
        ('device_update', 'Device Update'),
        ('device_delete', 'Device Deletion'),
        ('update_upload', 'Update Upload'),
        ('update_verify', 'Update Verification'),
        ('update_push', 'Update Push'),
        ('inventory_submit', 'Inventory Submission'),
        ('config_change', 'Configuration Change'),
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('failed_auth', 'Failed Authentication'),
    ]
    
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Who
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # What
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='info', db_index=True)
    description = models.TextField()
    
    # Context
    resource_type = models.CharField(max_length=50, blank=True)  # e.g., 'Update', 'Device'
    resource_id = models.CharField(max_length=255, blank=True)
    
    # Additional data (JSON)
    metadata = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'action']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['device', 'timestamp']),
            models.Index(fields=['severity', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.timestamp} - {self.action} by {self.user or self.device}"


class SystemConfig(models.Model):
    """System-wide configuration (singleton)"""
    
    id = models.AutoField(primary_key=True)
    
    # Server settings
    server_url = models.URLField(default='https://localhost:8000')
    
    # API keys
    virustotal_api_key = EncryptedTextField(blank=True)
    
    # Policies
    update_retention_days = models.IntegerField(default=90)
    audit_log_retention_days = models.IntegerField(default=365)
    device_heartbeat_timeout = models.IntegerField(default=10)  # seconds (Reduced from 300 for immediacy)
    
    # Rate limiting
    api_rate_limit_per_minute = models.IntegerField(default=100)
    upload_rate_limit_per_hour = models.IntegerField(default=10)
    agent_update_interval = models.IntegerField(default=3600, help_text="How often agents check for self-updates (in seconds)")
    
    # File upload
    max_upload_size_mb = models.IntegerField(default=500)
    
    # Agent Auto-Update
    latest_agent_version = models.CharField(max_length=50, default='1.0.0.0')
    agent_msi_file = models.FileField(upload_to='agent_updates/', null=True, blank=True)
    agent_msi_sha256 = models.CharField(max_length=64, blank=True, help_text="SHA256 hash of the agent installer")
    
    # Security
    require_update_signature = models.BooleanField(default=True)
    require_malware_scan = models.BooleanField(default=True)
    
    # Notifications
    alert_email = models.EmailField(blank=True)
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.IntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = EncryptedTextField(blank=True)
    
    # Timestamps
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = 'System Configuration'
        verbose_name_plural = 'System Configuration'
    
    def __str__(self):
        return "System Configuration"
    
    @classmethod
    def get_config(cls):
        """Get or create singleton config"""
        config, _ = cls.objects.get_or_create(pk=1)
        return config
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists and handle agent MSI hashing"""
        self.pk = 1
        
        # Auto-compute hash if MSI file is changed
        if self.agent_msi_file:
            try:
                import hashlib
                hasher = hashlib.sha256()
                # If it's a new file object, hash it
                if hasattr(self.agent_msi_file, 'file'):
                    for chunk in self.agent_msi_file.chunks():
                        hasher.update(chunk)
                    self.agent_msi_sha256 = hasher.hexdigest()
            except Exception as e:
                print(f"Error hashing agent MSI: {e}")

        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion"""
        pass


class RSAKeyPair(models.Model):
    """RSA keypair for update signing (singleton)"""
    
    id = models.AutoField(primary_key=True)
    private_key = EncryptedTextField()  # PEM format, encrypted
    public_key = models.TextField()  # PEM format, public
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'RSA Key Pair'
        verbose_name_plural = 'RSA Key Pair'
    
    def __str__(self):
        return f"RSA Key Pair (created {self.created_at})"
    
    @classmethod
    def get_keypair(cls):
        """Get or create singleton keypair"""
        keypair = cls.objects.first()
        if not keypair:
            from core.crypto import generate_rsa_keypair
            private_pem, public_pem = generate_rsa_keypair()
            keypair = cls.objects.create(
                private_key=private_pem,
                public_key=public_pem
            )
        return keypair
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists"""
        if not self.pk and RSAKeyPair.objects.exists():
            raise ValueError("RSA keypair already exists")
        super().save(*args, **kwargs)

from django.core.validators import RegexValidator

class RemoteCommand(models.Model):
    """Generic remote execution commands for agents"""
    
    # Validator to prevent command injection characters
    # Only block critical shell operators: ; & | ` $ < > 
    # Must allow: \ (file paths), {} (MSI GUIDs), () (Program Files (x86)), " (quotes)
    PAYLOAD_VALIDATOR = RegexValidator(
        regex=r'^[^;&|`\$<>]+$',
        message="Payload contains forbidden characters (; & | ` $ < >) to prevent command injection.",
        code='invalid_payload'
    )

    COMMAND_CHOICES = [
        ('uninstall', 'Uninstall Software'),
        ('shell', 'Execute Shell Command'),
        ('reboot', 'Restart Device'),
        ('restart_agent', 'Restart Agent Service'),
        ('registry', 'Registry Management'),
        ('service_control', 'Service Control (Start/Stop)'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent to Agent'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='remote_commands')
    command_type = models.CharField(max_length=50, choices=COMMAND_CHOICES)
    
    # Payload (e.g., the uninstall string or script)
    payload = models.TextField(validators=[PAYLOAD_VALIDATOR])
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        permissions = [
            ("can_trigger_reboot", "Can remotely restart devices"),
            ("can_manage_registry", "Can manage device registry"),
            ("can_control_services", "Can start/stop device services"),
            ("can_uninstall_apps", "Can remotely uninstall software"),
            ("can_execute_shell", "Can execute arbitrary shell commands"),
        ]

    def __str__(self):
        return f"{self.command_type} on {self.device.hostname} ({self.status})"