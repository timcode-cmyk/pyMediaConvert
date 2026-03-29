# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 获取当前项目根目录，确保路径处理的一致性
block_cipher = None
project_root = os.path.abspath(os.getcwd())

# --- 1. 分析阶段 ---
a = Analysis(
    ['MediaTools.py'],  # 主程序入口
    pathex=[project_root],
    binaries=[], # 外部二进制文件建议放在 datas 中，或者在这里明确指定
    datas=[
        # 格式: (源路径, 目标文件夹)
        ('bin', 'bin'),                 # 存放 ffmpeg/ffprobe 等
        ('assets', 'assets'),           # 图片、图标等资源
        ('config.toml', '.'),           # 配置文件
        ('yt_dlp', 'yt_dlp'),           # yt-dlp 源码（支持动态更新）
        *collect_data_files('PySide6'), # 自动收集 PySide6 的资源文件
    ],
    hiddenimports=[
        'pysrt',
        'toml',
        *collect_submodules('pyMediaTools'), # 自动收集项目内所有子模块
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],    
    excludes=[
        # 排除标准库中不需要的模块
        'tkinter', 
        'unittest', 
        'test',
        # 明确排除不需要的 PySide6 模块以减小体积
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtNetworkAuth',
        'PySide6.QtPositioning',
        'PySide6.QtScxml',
        'PySide6.QtSensors',
        'PySide6.QtSql',
        'PySide6.QtTest',
        'PySide6.QtWebEngineWidgets',
    ], # 排除不需要的库以减小体积
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# --- 2. 编译 Python 脚本 ---
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- 3. 创建可执行文件 (EXE) ---
# 注意：这里去掉了 a.binaries 和 a.datas，从而实现 One-Dir 模式
app_icon = 'MediaTools.ico'
if sys.platform == 'darwin':
    app_icon = 'Icon.icns'

exe = EXE(
    pyz,
    a.scripts,
    [],                 # 不在 EXE 中打包二进制
    [],                 # 不在 EXE 中打包数据
    exclude_binaries=True, # 关键：开启文件夹模式
    name='MediaTools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,           # 使用 UPX 压缩可执行文件
    console=True,      # 调试模式开启控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
)

# --- 4. 收集所有碎片 (COLLECT) ---
# 这步会将所有 dll、pyd 和 datas 整理到 dist/MediaTools 文件夹下
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MediaTools', # 最终生成的文件夹名称
)

# --- 5. macOS 专属捆绑 (BUNDLE) ---
if sys.platform == 'darwin':
    app = BUNDLE(
        coll, # 注意：macOS 下通常基于 COLLECT 结果创建 .app
        name='MediaTools.app',
        icon=app_icon,
        bundle_identifier='com.mediatools.app',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSBackgroundOnly': 'False',
        },
    )