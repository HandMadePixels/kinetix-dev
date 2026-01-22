"""
Updates app configuration
"""

from django.apps import AppConfig


class UpdatesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'updates'
    verbose_name = 'Update Management'
