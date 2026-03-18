"""
项目名称: pyMediaTools
创建日期: 2025-12-20
作者: TimCode
版本: v1.13.5
许可证: GPL License
"""

__version__ = "1.13.5"
__author__ = "TimCode"
__description__ = "A professional media conversion tool based on FFmpeg"
__license__ = "GPL License"

import sys
import os
from pathlib import Path

# --- 1. 核心路径初始化 (必须放在最前面) ---
def initialize_environment():
    if getattr(sys, 'frozen', False):
        # Nuitka 打包后 sys.executable 是 MediaTools.app/Contents/MacOS/MediaTools
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        # 开发环境
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 强制切换工作目录，确保相对路径读取 bin/config.toml 正常
    os.chdir(base_dir)
    
    # 将当前目录加入 sys.path，确保能 import 手动拷贝的 yt_dlp
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    
    # 修复打包环境下 SSL 证书验证失败导致无法检查更新的问题
    if getattr(sys, 'frozen', False):
        try:
            # 尝试使用 certifi 获取证书路径并设置环境变量
            import certifi
            os.environ["SSL_CERT_FILE"] = certifi.where()
            os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
        except (ImportError, Exception):
            # 备用方案：查找 base_dir 下可能存在的证书文件 (如 Nuitka/PyInstaller 可能会将 cacert.pem 放在根目录)
            possible_certs = ["cacert.pem", os.path.join("certifi", "cacert.pem")]
            for cert in possible_certs:
                cert_path = os.path.join(base_dir, cert)
                if os.path.exists(cert_path):
                    os.environ["SSL_CERT_FILE"] = cert_path
                    os.environ["REQUESTS_CA_BUNDLE"] = cert_path
                    break

    return base_dir

BASE_DIR = initialize_environment()

# --- 2. 编码修复 ---
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# --- 3. 导入业务组件 ---
# 只有在路径初始化之后，import 内部包才安全
from pyMediaTools import setup_logging
from pyMediaTools.ui import MediaConverterWidget, ElevenLabsWidget, VideoDownloadWidget, VideoCutWidget
from pyMediaTools.ui import styles  # 假设你的 styles.py 在这里

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QIcon

# --- 4. Qt 插件路径修复 (解决颜色变浅的关键) ---
if getattr(sys, 'frozen', False):
    # 显式指向 Nuitka 打包的插件目录
    # 通常在 PySide6/Qt/plugins
    plugin_path = os.path.join(BASE_DIR, "PySide6", "Qt", "plugins")
    if os.path.exists(plugin_path):
        QCoreApplication.addLibraryPath(plugin_path)

# initialize logging early
setup_logging()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MediaTools")
        self.resize(900, 700)
        tabs = QTabWidget()
        tabs.addTab(MediaConverterWidget(), "媒体转换")
        tabs.addTab(ElevenLabsWidget(), "ElevenLabs")
        tabs.addTab(VideoCutWidget(), "场景分割")
        tabs.addTab(VideoDownloadWidget(), "视频下载")
        self.setCentralWidget(tabs)




if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 强制设置 Fusion 样式，确保在所有平台打包后都有统一美观的界面
    app.setStyle("Fusion")
    app.setApplicationName("Media Tools")

    win = MainWindow()
    win.show()
    sys.exit(app.exec())