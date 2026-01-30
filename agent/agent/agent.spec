# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('agent.ini', '.'),
    ],
    hiddenimports=[
        'win32timezone',
        'servicemanager',
        'win32service',
        'win32serviceutil',
        'win32event',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'psutil',
        'wmi',
        'pythoncom',
        'gui',
        'tkinter',
        'PIL',
        'PIL._tkinter_finder',
        'agent_service',
        'agent_logger',
        'agent_client',
        'agent_collector',
        'agent_config',
        'agent_updater',
        'magic',
        'packaging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='kinetix_agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='kinetix_agent',
)
