"""
项目名称: pyMediaTools
创建日期: 2025-12-20
作者: TimCode
版本: v3.0.0
许可证: GPL License
"""

__version__ = "3.0.0"
__author__ = "TimCode"
__description__ = "A professional media conversion tool based on FFmpeg"
__license__ = "GPL License"

import sys
import os
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl, Qt

# 解决打包环境下 stdout/stderr 默认编码可能为 ascii 导致的 UnicodeEncodeError
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from pyMediaTools import setup_logging
from pyMediaTools.bridges.media_converter_bridge import MediaConverterBridge
from pyMediaTools.bridges.elevenlabs_bridge import ElevenLabsBridge
from pyMediaTools.bridges.video_cut_bridge import VideoCutBridge
from pyMediaTools.bridges.download_manager_bridge import DownloadManagerBridge
from pyMediaTools.bridges.video_downloader_bridge import VideoDownloaderBridge

# initialize logging early
setup_logging()

# Fix QML styling warnings on macOS
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

if __name__ == '__main__':
    # Use QApplication to enable QtWidgets features like QFileDialog on some platforms
    app = QApplication(sys.argv)
    
    # 强制设置 Fusion 样式，确保在所有平台打包后都有统一美观的界面
    app.setStyle("Fusion")
    app.setApplicationName("Media Tools")

    import sys as _sys
    _icon_candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MediaTools.ico'),
    ]
    if getattr(_sys, 'frozen', False):
        _icon_candidates.insert(0, os.path.join(os.path.dirname(_sys.executable), 'MediaTools.ico'))
        if hasattr(_sys, '_MEIPASS'):
            _icon_candidates.insert(0, os.path.join(_sys._MEIPASS, 'MediaTools.ico'))
    for _icon_path in _icon_candidates:
        if os.path.exists(_icon_path):
            app.setWindowIcon(QIcon(_icon_path))
            break

    engine = QQmlApplicationEngine()
    
    # 注册 QML Bridge
    media_converter_bridge = MediaConverterBridge()
    engine.rootContext().setContextProperty("mediaConverterBridge", media_converter_bridge)
    
    elevenlabs_bridge = ElevenLabsBridge()
    engine.rootContext().setContextProperty("elevenLabsBridge", elevenlabs_bridge)

    video_cut_bridge = VideoCutBridge()
    engine.rootContext().setContextProperty("videoCutBridge", video_cut_bridge)

    download_manager_bridge = DownloadManagerBridge()
    engine.rootContext().setContextProperty("downloadManagerBridge", download_manager_bridge)

    video_downloader_bridge = VideoDownloaderBridge()
    engine.rootContext().setContextProperty("videoDownloaderBridge", video_downloader_bridge)

    # 加载主 QML
    qml_file = Path(__file__).resolve().parent / "pyMediaTools" / "qml" / "main.qml"
    engine.load(QUrl.fromLocalFile(os.fspath(qml_file)))

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())