"""
Celery tasks for core system functions
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task
def check_device_heartbeats():
    """
    Check device heartbeats and mark offline devices as inactive.
    Runs every 5 minutes via Celery Beat.
    """
    from core.models import Device, AuditLog, SystemConfig
    
    try:
        config = SystemConfig.get_config()
        timeout = timedelta(seconds=config.device_heartbeat_timeout)
        cutoff_time = timezone.now() - timeout
        
        # Find devices that haven't checked in
        offline_devices = Device.objects.filter(
            status='active',
            last_seen__lt=cutoff_time
        )
        
        count = 0
        for device in offline_devices:
            logger.warning(f"Device offline: {device.hostname}")
            
            # Log to audit
            AuditLog.objects.create(
                device=device,
                ip_address='0.0.0.0',
                action='device_update',
                severity='warning',
                description=f"Device marked offline: {device.hostname}",
                resource_type='Device',
                resource_id=str(device.id),
                metadata={
                    'last_seen': device.last_seen.isoformat(),
                    'timeout_seconds': config.device_heartbeat_timeout
                }
            )
            
            count += 1
        
        logger.info(f"Checked heartbeats: {count} devices offline")
    
    except Exception as e:
        logger.error(f"Error checking device heartbeats: {e}")


@shared_task
def cleanup_old_audit_logs():
    """
    Archive or delete old audit logs based on retention policy.
    Runs daily via Celery Beat.
    """
    from core.models import AuditLog, SystemConfig
    
    try:
        config = SystemConfig.get_config()
        retention_days = config.audit_log_retention_days
        
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # Delete old logs (or archive to file/external storage)
        old_logs = AuditLog.objects.filter(timestamp__lt=cutoff_date)
        count = old_logs.count()
        
        # TODO: Archive to file before deleting
        # For now, just delete
        old_logs.delete()
        
        logger.info(f"Cleaned up {count} old audit logs")
    
    except Exception as e:
        logger.error(f"Error cleaning up audit logs: {e}")


@shared_task
def generate_security_report():
    """
    Generate daily security report.
    Analyzes failed auth attempts, suspicious activity, etc.
    """
    from core.models import AuditLog
    from datetime import datetime
    
    try:
        # Get yesterday's date range
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        start_time = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()))
        end_time = timezone.make_aware(datetime.combine(yesterday, datetime.max.time()))
        
        # Failed authentication attempts
        failed_auths = AuditLog.objects.filter(
            action='failed_auth',
            timestamp__range=(start_time, end_time)
        ).count()
        
        # Critical/error events
        critical_events = AuditLog.objects.filter(
            severity__in=['critical', 'error'],
            timestamp__range=(start_time, end_time)
        ).count()
        
        # Unique IPs with failed auth
        failed_ips = AuditLog.objects.filter(
            action='failed_auth',
            timestamp__range=(start_time, end_time)
        ).values_list('ip_address', flat=True).distinct()
        
        report = {
            'date': yesterday.isoformat(),
            'failed_auth_count': failed_auths,
            'critical_events': critical_events,
            'suspicious_ips': list(failed_ips),
        }
        
        logger.info(f"Security report generated: {report}")
        
        # TODO: Send email alert if thresholds exceeded
        if failed_auths > 10:
            logger.warning(f"High number of failed auth attempts: {failed_auths}")
        
        return report
    
    except Exception as e:
        logger.error(f"Error generating security report: {e}")
        return None


@shared_task
def backup_database():
    """
    Create database backup.
    Runs daily via Celery Beat.
    """
    import os
    import shutil
    from django.conf import settings
    
    try:
        # Only for SQLite
        if 'sqlite' in settings.DATABASES['default']['ENGINE']:
            db_path = settings.DATABASES['default']['NAME']
            backup_dir = settings.BASE_DIR / 'backups'
            backup_dir.mkdir(exist_ok=True)
            
            # Create backup with timestamp
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            backup_path = backup_dir / f"db_backup_{timestamp}.sqlite3"
            
            shutil.copy2(db_path, backup_path)
            
            logger.info(f"Database backup created: {backup_path}")
            
            # Keep only last 7 backups
            backups = sorted(backup_dir.glob('db_backup_*.sqlite3'))
            if len(backups) > 7:
                for old_backup in backups[:-7]:
                    old_backup.unlink()
                    logger.info(f"Deleted old backup: {old_backup}")
        
        else:
            logger.info("Database backup skipped (not SQLite)")
    
    except Exception as e:
        logger.error(f"Error creating database backup: {e}")


@shared_task
def monitor_disk_space():
    """
    Monitor disk space and alert if low.
    Runs every hour via Celery Beat.
    """
    import shutil
    from django.conf import settings
    
    try:
        media_root = settings.MEDIA_ROOT
        total, used, free = shutil.disk_usage(media_root)
        
        # Convert to GB
        free_gb = free / (1024 ** 3)
        total_gb = total / (1024 ** 3)
        percent_free = (free / total) * 100
        
        logger.info(f"Disk space: {free_gb:.2f}GB free ({percent_free:.1f}%)")
        
        # Alert if less than 10% free or less than 5GB
        if percent_free < 10 or free_gb < 5:
            logger.critical(f"Low disk space: {free_gb:.2f}GB free ({percent_free:.1f}%)")
            
            # TODO: Send email alert
    
    except Exception as e:
        logger.error(f"Error monitoring disk space: {e}")


@shared_task
def async_log_event(user_id, device_id, ip_address, user_agent, action, severity, description, resource_type='', resource_id='', metadata=None):
    """
    Asynchronously create an audit log entry.
    """
    from core.models import AuditLog
    from django.contrib.auth.models import User
    from core.models import Device
    
    try:
        user = User.objects.get(id=user_id) if user_id else None
        device = Device.objects.get(id=device_id) if device_id else None
        
        AuditLog.objects.create(
            user=user,
            device=device,
            ip_address=ip_address,
            user_agent=user_agent,
            action=action,
            severity=severity,
            description=description,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata or {}
        )
    except Exception as e:
        logger.error(f"Error in async_log_event: {e}")
