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
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
    
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
from pyMediaTools.ui import MediaConverterWidget, ElevenLabsWidget, VideoDownloadWidget, VideoCutWidget



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

    from PySide6.QtGui import QIcon
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




    win = MainWindow()
    win.show()
    sys.exit(app.exec())