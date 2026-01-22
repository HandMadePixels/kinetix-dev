# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Kinetix
Bundles Django application with all dependencies for Windows deployment
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Get project root
project_root = os.path.abspath(os.path.join(SPECPATH, '..'))
sys.path.insert(0, project_root)

# Collect Django data files
django_datas = collect_data_files('django')
drf_datas = collect_data_files('rest_framework')

# Application data files
app_datas = [
    (os.path.join(project_root, 'templates'), 'templates'),
    (os.path.join(project_root, 'static'), 'static'),
    (os.path.join(project_root, 'media'), 'media'),
    (os.path.join(project_root, 'core', 'migrations'), 'core/migrations'),
    (os.path.join(project_root, 'api', 'migrations'), 'api/migrations'),
    (os.path.join(project_root, 'inventory', 'migrations'), 'inventory/migrations'),
    (os.path.join(project_root, 'updates', 'migrations'), 'updates/migrations'),
    (os.path.join(project_root, 'dashboard', 'migrations'), 'dashboard/migrations'),
]

# Collect all Django submodules
django_hidden_imports = collect_submodules('django')
drf_hidden_imports = collect_submodules('rest_framework')

# Additional hidden imports
hidden_imports = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.core.management',
    'django.core.management.commands',
    'django.db.backends.sqlite3',
    'django.template.loaders.filesystem',
    'django.template.loaders.app_directories',
    
    # Django REST Framework
    'rest_framework',
    'rest_framework.authentication',
    'rest_framework.permissions',
    'rest_framework.parsers',
    'rest_framework.renderers',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.authentication',
    'rest_framework_simplejwt.tokens',
    
    # Celery
    'celery',
    'celery.app',
    'celery.backends',
    'celery.backends.database',
    'django_celery_beat',
    'django_celery_results',
    
    # Security
    'cryptography',
    'cryptography.fernet',
    'cryptography.hazmat',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.backends',
    
    # Other
    'whitenoise',
    'whitenoise.middleware',
    'decouple',
    'cerberus',
    'bleach',
    'requests',
    
    # Local apps
    'core',
    'core.models',
    'core.views',
    'api',
    'api.views',
    'api.serializers',
    'inventory',
    'inventory.models',
    'updates',
    'updates.models',
    'dashboard',
    'dashboard.views',
]

# Combine hidden imports
hidden_imports.extend(django_hidden_imports)
hidden_imports.extend(drf_hidden_imports)

# Exclude unnecessary modules to reduce size
excludes = [
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'PIL.ImageQt',
    'PyQt5',
    'PySide2',
    'wx',
]

a = Analysis(
    [os.path.join(project_root, 'manage.py')],
    pathex=[project_root],
    binaries=[],
    datas=django_datas + drf_datas + app_datas,
    hiddenimports=hidden_imports,
    hookspath=[os.path.join(SPECPATH, 'hooks')],
    hooksconfig={},
    runtime_hooks=[os.path.join(SPECPATH, 'runtime_hook.py')],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='command_center',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Console app for manage.py commands
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'static', 'icon.ico') if os.path.exists(os.path.join(project_root, 'static', 'icon.ico')) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Kinetix',
)
