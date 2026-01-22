from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from core.models import Device, AuditLog
import logging

logger = logging.getLogger('core.audit')

@receiver(post_save, sender=Device)
def log_device_save(sender, instance, created, **kwargs):
    """Log device creation/update"""
    action = 'device_register' if created else 'device_update'
    try:
        # Check if we have enough metadata to log
        AuditLog.objects.create(
            device=instance,
            ip_address='0.0.0.0',
            action=action,
            severity='info',
            description=f"Device {'registered' if created else 'updated'}: {instance.hostname}",
            resource_type='Device',
            resource_id=str(instance.id)
        )
    except Exception as e:
        logger.error(f"Failed to log device save signal: {e}")

@receiver(pre_delete, sender=Device)
def log_device_delete(sender, instance, **kwargs):
    """Log device deletion"""
    try:
        AuditLog.objects.create(
            device=instance,
            ip_address='0.0.0.0',
            action='device_delete',
            severity='warning',
            description=f"Device deleted: {instance.hostname}",
            resource_type='Device',
            resource_id=str(instance.id)
        )
    except Exception as e:
        logger.error(f"Failed to log device delete signal: {e}")
