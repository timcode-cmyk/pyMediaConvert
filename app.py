"""
项目名称: pyMediaTools
创建日期: 2025-12-20
作者: TimCode
版本: v1.11.0
许可证: GPL License
"""

__version__ = "1.11.0"
__author__ = "TimCode"
__description__ = "A professional media conversion tool based on FFmpeg"
__license__ = "GPL License"

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from pyMediaTools import setup_logging
from pyMediaTools.ui import MediaConverterWidget, ElevenLabsWidget, DownloaderWidget, VideoDownloaWidget



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
        tabs.addTab(DownloaderWidget(), "下载管理")
        tabs.addTab(VideoDownloaWidget(), "视频下载")
        self.setCentralWidget(tabs)




if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = ToolBoxMainWindow()
    win.show()
    sys.exit(app.exec())