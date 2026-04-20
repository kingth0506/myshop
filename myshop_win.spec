# -*- mode: python ; coding: utf-8 -*-
import os, sys
block_cipher = None

# Playwright 경로
try:
    import playwright
    pw_path = os.path.dirname(playwright.__file__)
except:
    pw_path = None

datas = [('icon_1024.png', '.'), ('check.png', '.'), ('arrow_down.png', '.')]
if pw_path:
    datas.append((pw_path, 'playwright'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['playwright', 'playwright.sync_api', 'playwright.async_api'],
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
    name='ORDERMASTER',
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
    icon='icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ORDERMASTER',
)
