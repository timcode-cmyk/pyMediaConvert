"""
项目名称: pyMediaTools
创建日期: 2025-12-20
作者: TimCode
版本: v1.11.2
许可证: GPL License
"""

__version__ = "1.11.2"
__author__ = "TimCode"
__description__ = "A professional media conversion tool based on FFmpeg"
__license__ = "GPL License"

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

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
    win = ToolBoxMainWindow()
    win.show()
    sys.exit(app.exec())