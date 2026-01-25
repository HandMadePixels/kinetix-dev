"""
Models for update management
"""

import uuid
import os
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Device


def update_file_path(instance, filename):
    """Generate upload path for update files"""
    # uploads/updates/YYYY/MM/uuid_filename
    now = timezone.now()
    ext = os.path.splitext(filename)[1]
    new_filename = f"{uuid.uuid4()}{ext}"
    return f"updates/{now.year}/{now.month:02d}/{new_filename}"


class Update(models.Model):
    """Update file with metadata and verification"""
    
    SCAN_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scanning', 'Scanning'),
        ('clean', 'Clean'),
        ('infected', 'Infected'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # File
    name = models.CharField(max_length=100, default='Software', db_index=True)
    file = models.FileField(upload_to=update_file_path)
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField()  # bytes
    
    # Metadata
    version = models.CharField(max_length=50, db_index=True)
    description = models.TextField()
    
    # Security
    sha256_hash = models.CharField(max_length=64, unique=True, db_index=True)
    signature = models.TextField()  # RSA signature (base64)
    
    # Malware scan
    scan_status = models.CharField(
        max_length=20,
        choices=SCAN_STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    scan_result = models.JSONField(default=dict, blank=True)
    scanned_at = models.DateTimeField(null=True, blank=True)
    
    # Audit
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['version', 'uploaded_at']),
            models.Index(fields=['scan_status', 'uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.name} v{self.version}"
    
    def is_verified(self):
        """Check if update is verified and safe"""
        return self.scan_status == 'clean'
    
    def file_size_mb(self):
        """Return file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)

    def save(self, *args, **kwargs):
        # Calculate file size if not set
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except:
                pass
        
        # Check if we need to sign/hash
        # We do this if they are empty
        needs_signing = not self.sha256_hash or not self.signature
        
        super().save(*args, **kwargs)
        
        if needs_signing and self.file:
            try:
                from core.crypto import sign_file
                from core.models import RSAKeyPair
                import logging
                logger = logging.getLogger(__name__)

                # Only attempt if file exists on disk
                if os.path.exists(self.file.path):
                    keypair = RSAKeyPair.get_keypair()
                    file_hash, signature = sign_file(self.file.path, keypair.private_key)
                    
                    # Use update() to avoid recursion and signals
                    Update.objects.filter(id=self.id).update(
                        sha256_hash=file_hash,
                        signature=signature
                    )
                    
                    # Trigger scan if it's pending
                    if self.scan_status == 'pending':
                        from updates.tasks import scan_update_file
                        scan_update_file.delay(str(self.id))
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error auto-signing update {self.id}: {e}")


class UpdatePush(models.Model):
    """Track update push to devices"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    update = models.ForeignKey(Update, on_delete=models.CASCADE, related_name='pushes')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='update_pushes')
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # Timing
    scheduled_at = models.DateTimeField(db_index=True)
    pushed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    # Audit
    pushed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-scheduled_at']
        unique_together = [['update', 'device']]  # One push per update per device
        indexes = [
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['device', 'status']),
        ]
        permissions = [
            ("can_deploy_updates", "Can deploy software updates"),
            ("can_retry_deployments", "Can retry failed deployments"),
        ]

    def __str__(self):
        return f"{self.update.filename} -> {self.device.hostname} ({self.status})"
    
    def mark_completed(self):
        """Mark push as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, error_message):
        """Mark push as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.retry_count += 1
        self.save()


class ScanResult(models.Model):
    """Detailed malware scan results"""
    
    SCANNER_CHOICES = [
        ('virustotal', 'VirusTotal'),
        ('clamav', 'ClamAV'),
        ('manual', 'Manual Review'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    update = models.ForeignKey(Update, on_delete=models.CASCADE, related_name='scan_results')
    
    # Scanner info
    scanner = models.CharField(max_length=20, choices=SCANNER_CHOICES)
    scanner_version = models.CharField(max_length=100, blank=True)
    
    # Results
    is_clean = models.BooleanField()
    threat_names = models.JSONField(default=list, blank=True)  # List of detected threats
    detection_ratio = models.CharField(max_length=20, blank=True)  # e.g., "2/70"
    
    # Raw data
    raw_response = models.JSONField(default=dict, blank=True)
    
    # Metadata
    scanned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-scanned_at']
    
    def __str__(self):
        status = "Clean" if self.is_clean else "Infected"
        return f"{self.scanner} - {self.update.filename} - {status}"
