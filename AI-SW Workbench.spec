# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('ui_desktop/styles/theme.qss', 'ui_desktop/styles'), ('ui_desktop/resources/app_icon.ico', 'ui_desktop/resources'), ('ui_desktop/resources/app_icon.png', 'ui_desktop/resources'), ('resources/materials/material_catalog.json', 'resources/materials')]
binaries = []
hiddenimports = ['win32com', 'win32com.client', 'pythoncom', 'pywintypes', 'win32api']
hiddenimports += collect_submodules('cad_dsl')
hiddenimports += collect_submodules('policy')
hiddenimports += collect_submodules('solidworks_api')
tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('shiboken6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['ui_desktop/main.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AI-SW Workbench',
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
    icon=['ui_desktop/resources/app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AI-SW Workbench',
)
