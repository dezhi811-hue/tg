# -*- mode: python ; coding: utf-8 -*-
"""
TelegramFilter EXE 打包配置
用法: pyinstaller TelegramFilter.spec
"""
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# 收集 PyQt5 数据文件（icons, fonts, etc.）
pyqt5_data = collect_data_files('PyQt5')

# 收集 PyQt5 子模块
pyqt5_imports = collect_submodules('PyQt5')

a = Analysis(
    ['gui_monitor.py'],
    pathex=[],
    binaries=[],
    datas=pyqt5_data,
    hiddenimports=[
        # PyQt5 核心
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
        # PyQt5 子模块
    ] + pyqt5_imports + [
        # Telethon 核心模块
        'telethon',
        'telethon.connection',
        'telethon.extensions',
        'telethon.extensions.message_parse',
        'telethon.network',
        'telethon.network.authenticator',
        'telethon.crypto',
        'telethon.tl',
        'telethon.tl.alltlobjects',
        'telethon.tl.functions',
        'telethon.tl.types',
        # PySocks（telethon 代理支持）
        'pysocks',
        'urllib3',
    ],
    hookspath=[],
    hooksconfig={},
    keys=[],
    exclude_binaries=False,
    name='TelegramFilter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    entitlements_file=None,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TelegramFilter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    entitlements_file=None,
    icon=None,
)
