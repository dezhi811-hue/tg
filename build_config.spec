# -*- mode: python ; coding: utf-8 -*-
import sys

block_cipher = None

a = Analysis(
    ['run_gui.py', 'gui_monitor.py', 'account_manager.py', 'filter.py', 'rate_limiter.py', 'remote_logger.py', 'updater.py', 'version.py', 'batch_import.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'gui_monitor',
        'account_manager',
        'filter',
        'rate_limiter',
        'remote_logger',
        'updater',
        'version',
        'batch_import',
        'telethon',
        'telethon.tl',
        'telethon.tl.types',
        'telethon.tl.functions',
        'telethon.tl.functions.contacts',
        'telethon.tl.alltlobjects',
        'telethon.errors',
        'telethon.network',
        'telethon.network.connection',
        'telethon.crypto',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
        'socks',
        'sockshandler',
        'asyncio',
        'json',
        'datetime',
        'requests',
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

# Windows 单文件 EXE
if sys.platform == 'win32':
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='TelegramFilter',
        debug=True,  # 开启调试模式
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,  # 开启控制台窗口，方便看错误
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )
# macOS 单文件可执行
else:
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
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

    # macOS app bundle
    app = BUNDLE(
        exe,
        name='TelegramFilter.app',
        icon=None,
        bundle_identifier='com.telegramfilter.app',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSBackgroundOnly': 'False',
            'LSMinimumSystemVersion': '11.0',  # 最低支持 macOS 11
        },
    )
