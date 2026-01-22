"""
Celery configuration for Kinetix
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'command_center.settings')

app = Celery('command_center')

# Load config from Django settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Periodic tasks configuration
app.conf.beat_schedule = {
    'check-device-heartbeats': {
        'task': 'core.tasks.check_device_heartbeats',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'cleanup-old-updates': {
        'task': 'updates.tasks.cleanup_old_updates',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'cleanup-old-audit-logs': {
        'task': 'core.tasks.cleanup_old_audit_logs',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'generate-daily-reports': {
        'task': 'dashboard.tasks.generate_daily_reports',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
    },
}

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')
