"""
PyInstaller runtime hook for Django
Sets up Django environment before application starts
"""

import os
import sys

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'command_center.settings')

# Disable Django debug mode
os.environ['DJANGO_DEBUG'] = 'False'

# Set up Django
import django
django.setup()
