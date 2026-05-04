# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

import os
import sys

datas = []
binaries = []
hiddenimports = []

# Collect requirements
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('playwright')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# On macOS, we handle pw-browsers differently to avoid binary processing errors
if sys.platform == 'darwin':
    # We will add it to COLLECT instead of Analysis datas to avoid PyInstaller's inspection
    browser_data = []
else:
    datas += [('pw-browsers', 'pw-browsers')]

# Include local modules and config files
datas += [
    ('staffspy', 'staffspy'),
    ('social_engine.py', '.'),
    ('email_social_engine.py', '.'),
    ('database.py', '.'),
    ('models.py', '.'),
    ('config.json', '.')
]

a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'tensorflow', 'tensorboard', 'matplotlib', 'notebook', 'scipy', 'IPython'],
    noarchive=False,
    optimize=0,
)

# On macOS, filter out any mistakenly identified binaries from pw-browsers
if sys.platform == 'darwin':
    a.binaries = [x for x in a.binaries if 'pw-browsers' not in x[0] and 'pw-browsers' not in x[1]]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MapsLeadScraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='file_version_info.txt',
    icon='NONE',
)

# Manual data collection for macOS browsers
extra_datas = a.datas
if sys.platform == 'darwin':
    # Add pw-browsers manually to the collection step
    if os.path.exists('pw-browsers'):
        extra_datas += Tree('pw-browsers', prefix='pw-browsers')

coll = COLLECT(
    exe,
    a.binaries,
    extra_datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MapsLeadScraper',
)
app = BUNDLE(
    coll,
    name='MapsLeadScraper.app',
    icon=None,
    bundle_identifier='com.mapsleadscraper.app',
)

