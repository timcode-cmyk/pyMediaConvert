"""
项目名称: pyMediaTools
创建日期: 2025-12-20
作者: TimCode
版本: v1.11.3
许可证: GPL License
"""

__version__ = "1.12.0"
__author__ = "TimCode"
__description__ = "A professional media conversion tool based on FFmpeg"
__license__ = "GPL License"

import sys
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
from pyMediaTools.ui import MediaConverterWidget, ElevenLabsWidget, DownloadManagerWidget, VideoDownloadWidget



# initialize logging early
setup_logging()


class ToolBoxMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MediaTools")
        self.resize(900, 700)
        tabs = QTabWidget()
        tabs.addTab(MediaConverterWidget(), "媒体转换")
        tabs.addTab(ElevenLabsWidget(), "ElevenLabs")
        tabs.addTab(DownloadManagerWidget(), "下载管理")
        tabs.addTab(VideoDownloadWidget(), "视频下载")
        self.setCentralWidget(tabs)




if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 强制设置 Fusion 样式，确保在所有平台打包后都有统一美观的界面
    app.setStyle("Fusion")
    
    win = ToolBoxMainWindow()
    win.show()
    sys.exit(app.exec())