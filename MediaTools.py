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

# --- 2. 编码修复 ---
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# --- 3. 导入业务组件 ---
# 只有在路径初始化之后，import 内部包才安全
from pyMediaTools import setup_logging
from pyMediaTools.ui import MediaConverterWidget, ElevenLabsWidget, VideoDownloadWidget, VideoCutWidget, ASSEditorWidget
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

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
        # tabs.addTab(RembgWidget(), "智能抠图")
        tabs.addTab(ASSEditorWidget(), "ASS样式编辑器")
        self.setCentralWidget(tabs)




if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 强制设置 Fusion 样式，确保在所有平台打包后都有统一美观的界面
    app.setStyle("Fusion")
    app.setApplicationName("Media Tools")

    win = MainWindow()
    win.show()
    sys.exit(app.exec())