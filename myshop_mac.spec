# -*- mode: python ; coding: utf-8 -*-
import os, sys
block_cipher = None

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
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MYSHOP',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    target_arch=None,
    icon='icon_1024.png',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='MYSHOP',
)
app = BUNDLE(
    coll,
    name='MYSHOP.app',
    icon='icon_1024.png',
    bundle_identifier='com.myshop.manager',
    info_plist={
        'CFBundleShortVersionString': '1.3.2',
        'LSMinimumSystemVersion': '10.15',
        'NSHighResolutionCapable': True,
    },
)
