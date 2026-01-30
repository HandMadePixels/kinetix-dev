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
def scan_agent_updates():
    """
    Scans the 'agent_drops' directory for new MSI files.
    Treats this folder as the absolute source of truth for the latest agent version.
    """
    import os
    import re
    from django.conf import settings
    from django.core.files import File
    from core.models import SystemConfig, AuditLog
    from packaging import version as py_version
    
    drop_dir = os.path.join(settings.MEDIA_ROOT, 'agent_drops')
    if not os.path.exists(drop_dir):
        os.makedirs(drop_dir)
        return

    # Look for MSI files
    files = [f for f in os.listdir(drop_dir) if f.lower().endswith('.msi')]
    
    config = SystemConfig.get_config()
    
    if not files:
        # If no files in drop folder, but we have a file in config, 
        # ensure the config file actually exists on disk to prevent 404s
        if config.agent_msi_file:
            if not os.path.exists(config.agent_msi_file.path):
                logger.warning("Managed agent MSI file missing from disk. Clearing config.")
                config.agent_msi_file = None
                config.save()
        return

    # Sort files by actual version numbers
    def extract_version(filename):
        match = re.search(r'(\d+\.\d+\.\d+\.\d+)', filename)
        return py_version.parse(match.group(1)) if match else py_version.parse("0.0.0.0")

    files.sort(key=extract_version, reverse=True)
    latest_file = files[0]
    latest_ver_str = str(extract_version(latest_file))
    
    # Logic: If drop folder has a version, it MUST be the one we use.
    # We update if:
    # 1. Version string is different
    # 2. OR the file field is empty
    # 3. OR the file on disk is missing
    
    file_exists = False
    if config.agent_msi_file:
        try:
            file_exists = os.path.exists(config.agent_msi_file.path)
        except:
            file_exists = False

    if config.latest_agent_version == latest_ver_str and config.agent_msi_file and file_exists:
        return

    logger.info(f"Syncing SystemConfig to latest agent in drops: {latest_file} (v{latest_ver_str})")
    
    file_path = os.path.join(drop_dir, latest_file)
    try:
        with open(file_path, 'rb') as f:
            config.latest_agent_version = latest_ver_str
            # Save the file. Django will handle name conflicts by appending suffixes if needed,
            # but our check above prevents redundant saves.
            config.agent_msi_file.save(latest_file, File(f), save=True)
            
        AuditLog.objects.create(
            ip_address='127.0.0.1',
            action='config_change',
            severity='info',
            description=f"Agent Update Synced: v{latest_ver_str} picked up from drops folder.",
            metadata={'filename': latest_file, 'version': latest_ver_str}
        )
        
        # Cleanup: Move to processed
        processed_dir = os.path.join(drop_dir, 'processed')
        if not os.path.exists(processed_dir):
            os.makedirs(processed_dir)
        
        dest_path = os.path.join(processed_dir, latest_file)
        if os.path.exists(dest_path):
            os.remove(dest_path) # Overwrite old processed file if exists
        os.rename(file_path, dest_path)
        
    except Exception as e:
        logger.error(f"Error syncing agent update from drops: {e}")


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
