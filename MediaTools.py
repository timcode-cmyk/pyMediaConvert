"""
项目名称: pyMediaTools
创建日期: 2025-12-20
作者: timcode-cmyk
版本: v1.14.3
许可证: GPL License
"""

__version__ = "1.14.3"
__author__ = "timcode-cmyk"
__description__ = "A professional media toolkit built with Python and PySide6, offering a suite of utilities for video editing, audio processing, and more."
__license__ = "GPL License"

import sys

# --- 2. 编码修复 ---
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# --- 3. 导入业务组件 ---
# 只有在路径初始化之后，import 内部包才安全
from pyMediaTools import setup_logging
from pyMediaTools.ui import MediaConverterWidget, ElevenLabsWidget, VideoDownloadWidget, VideoCutWidget, ASSEditorWidget, DashboardWindow
from PySide6.QtWidgets import QApplication

setup_logging()

def create_main_window():
    modules = [
        ("工作台", MediaConverterWidget()),
        ("视频配音", ElevenLabsWidget()),
        ("场景分割", VideoCutWidget()),
        ("视频下载", VideoDownloadWidget()),
        ("字幕编辑", ASSEditorWidget()),
    ]
    return DashboardWindow(modules, version=__version__)




if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 强制设置 Fusion 样式，确保在所有平台打包后都有统一美观的界面
    app.setStyle("Fusion")
    app.setApplicationName("Media Tools")

    win = create_main_window()
    win.show()
    sys.exit(app.exec())