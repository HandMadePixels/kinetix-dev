"""
Celery tasks for update management
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def scan_update_file(self, update_id):
    """
    Scan uploaded update file for malware.
    Uses VirusTotal API or ClamAV.
    """
    from updates.models import Update, ScanResult
    from updates.scanners import VirusTotalScanner, ClamAVScanner
    
    try:
        update = Update.objects.get(id=update_id)
        update.scan_status = 'scanning'
        update.save()
        
        logger.info(f"Scanning update: {update.filename}")
        
        # Try VirusTotal first
        if settings.VIRUSTOTAL_ENABLED:
            scanner = VirusTotalScanner()
            result = scanner.scan_file(update.file.path)
            
            if result:
                # Save scan result
                scan_record = ScanResult.objects.create(
                    update=update,
                    scanner='virustotal',
                    scanner_version=result.get('scanner_version', ''),
                    is_clean=result['is_clean'],
                    threat_names=result.get('threats', []),
                    detection_ratio=result.get('detection_ratio', ''),
                    raw_response=result.get('raw_response', {})
                )
                
                # Update status
                if result['is_clean']:
                    update.scan_status = 'clean'
                else:
                    update.scan_status = 'infected'
                
                update.scan_result = result
                update.scanned_at = timezone.now()
                update.save()
                
                logger.info(f"VirusTotal scan complete: {update.filename} - {update.scan_status}")
                return
        
        # Fallback to ClamAV
        if settings.CLAMAV_ENABLED:
            scanner = ClamAVScanner()
            result = scanner.scan_file(update.file.path)
            
            if result:
                scan_record = ScanResult.objects.create(
                    update=update,
                    scanner='clamav',
                    scanner_version=result.get('scanner_version', ''),
                    is_clean=result['is_clean'],
                    threat_names=result.get('threats', []),
                    raw_response=result.get('raw_response', {})
                )
                
                if result['is_clean']:
                    update.scan_status = 'clean'
                else:
                    update.scan_status = 'infected'
                
                update.scan_result = result
                update.scanned_at = timezone.now()
                update.save()
                
                logger.info(f"ClamAV scan complete: {update.filename} - {update.scan_status}")
                return
        
        # No scanner available - In development or when no scanners are configured, 
        # we mark as clean but with a warning.
        logger.warning(f"No malware scanner available for: {update.filename}. Marking as clean.")
        update.scan_status = 'clean'
        update.scan_result = {
            'warning': 'No malware scanner (VirusTotal or ClamAV) is configured. File marked as clean by default.',
            'timestamp': timezone.now().isoformat()
        }
        update.save()
    
    except Update.DoesNotExist:
        logger.error(f"Update not found: {update_id}")
    except Exception as e:
        logger.error(f"Error scanning update {update_id}: {e}")
        
        # Retry on error
        try:
            update = Update.objects.get(id=update_id)
            update.scan_status = 'error'
            update.scan_result = {'error': str(e)}
            update.save()
        except:
            pass
        
        raise self.retry(exc=e, countdown=60)


@shared_task
def push_update_to_device(push_id):
    """
    Handle update push to device.
    Device will poll /api/v1/commands to retrieve the update.
    """
    from updates.models import UpdatePush
    from core.models import AuditLog
    
    try:
        push = UpdatePush.objects.get(id=push_id)
        
        logger.info(f"Processing push: {push.update.filename} -> {push.device.hostname}")
        
        # Check if device is online
        is_online = push.device.is_online()
        
        # Update will be delivered when device polls /api/v1/commands
        # This task serves as a notification/audit point
        
        status_msg = "Device is online, waiting for next poll." if is_online else "Device is currently offline, will deliver when it reconnects."
        
        AuditLog.objects.create(
            device=push.device,
            ip_address='0.0.0.0',
            action='update_push',
            severity='info',
            description=f"Update queued for {push.device.hostname}. {status_msg}",
            resource_type='UpdatePush',
            resource_id=str(push.id)
        )
        
        logger.info(f"Push queued: {push.id}")
    
    except UpdatePush.DoesNotExist:
        logger.error(f"UpdatePush not found: {push_id}")
    except Exception as e:
        logger.error(f"Error pushing update {push_id}: {e}")


@shared_task
def cleanup_old_updates():
    """
    Remove old update files based on retention policy.
    Runs daily via Celery Beat.
    """
    from updates.models import Update
    from core.models import SystemConfig
    from datetime import timedelta
    
    try:
        config = SystemConfig.get_config()
        retention_days = config.update_retention_days
        
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        old_updates = Update.objects.filter(
            uploaded_at__lt=cutoff_date,
            pushes__status='completed'  # Only delete completed pushes
        ).distinct()
        
        count = 0
        for update in old_updates:
            # Check if all pushes are completed
            if not update.pushes.exclude(status='completed').exists():
                logger.info(f"Deleting old update: {update.filename}")
                update.file.delete()  # Delete file from storage
                update.delete()  # Delete record
                count += 1
        
        logger.info(f"Cleaned up {count} old updates")
    
    except Exception as e:
        logger.error(f"Error cleaning up old updates: {e}")


@shared_task
def retry_failed_pushes():
    """
    Retry failed update pushes (up to max retries).
    Runs every hour via Celery Beat.
    """
    from updates.models import UpdatePush
    
    try:
        failed_pushes = UpdatePush.objects.filter(
            status='failed',
            retry_count__lt=3  # Max 3 retries
        )
        
        count = 0
        for push in failed_pushes:
            if push.device.is_online():
                logger.info(f"Retrying push: {push.id}")
                push.status = 'pending'
                push.save()
                
                # Re-queue task
                push_update_to_device.delay(str(push.id))
                count += 1
        
        logger.info(f"Retried {count} failed pushes")
    
    except Exception as e:
        logger.error(f"Error retrying failed pushes: {e}")
