"""
项目名称: pyMediaTools
创建日期: 2025-12-20
作者: timcode-cmyk
版本: v1.15.1
描述: 基于 Python 和 PySide6 的专业媒体工具包，提供视频编辑、音频处理等一系列实用工具。
许可证: GPL License

# nuitka-project: --standalone
# nuitka-project: --assume-yes-for-downloads
# nuitka-project: --output-dir=dist-nuitka
# nuitka-project: --plugin-enable=pyside6
# nuitka-project: --nofollow-import-to=yt_dlp
# nuitka-project: --no-deployment-flag=excluded-module-usage
# nuitka-project: --include-qt-plugins=multimedia,platforms,styles,imageformats
# nuitka-project: --include-package=pyMediaTools
# nuitka-project: --include-module=optparse
# nuitka-project: --include-module=asyncio
# nuitka-project: --include-data-files={MAIN_DIRECTORY}/config.toml=config.toml
# nuitka-project: --include-data-dir={MAIN_DIRECTORY}/assets=assets



# nuitka-project-if: {OS} == "Windows":
#     nuitka-project: --windows-console-mode=disable
#     nuitka-project: --windows-icon-from-ico={MAIN_DIRECTORY}/MediaTools.ico
#     # Windows 下 FFmpeg 包含
#     nuitka-project: --include-data-files={MAIN_DIRECTORY}/bin/ffmpeg.exe=bin/ffmpeg.exe
#     nuitka-project: --include-data-files={MAIN_DIRECTORY}/bin/ffprobe.exe=bin/ffprobe.exe

# nuitka-project-if: {OS} == "Darwin":
#     nuitka-project: --macos-create-app-bundle
#     nuitka-project: --macos-app-icon={MAIN_DIRECTORY}/Icon.icns
#     # MacOS 下 FFmpeg 包含
#     nuitka-project: --include-data-files={MAIN_DIRECTORY}/bin/ffmpeg=bin/ffmpeg
#     nuitka-project: --include-data-files={MAIN_DIRECTORY}/bin/ffprobe=bin/ffprobe
"""

__version__ = "1.15.1"
__author__ = "timcode-cmyk"
__description__ = "A professional media toolkit built with Python and PySide6, offering a suite of utilities for video editing, audio processing, and more."
__license__ = "GPL License"

import sys

# --- 2. 编码修复 ---
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# --- 3. 初始化日志 ---
# 必须最先初始化，以便捕获后续导入中的错误
from pyMediaTools import setup_logging
logger = setup_logging()
logger.info("========================================")
logger.info(f"MediaTools 启动中 (v{__version__})...")

# --- 4. 导入业务组件 ---
try:
    logger.info("正在导入依赖组件 (Importing UI components)...")
    from pyMediaTools.ui import MediaConverterWidget, ElevenLabsWidget, VideoDownloadWidget, VideoCutWidget, ASSEditorWidget, DashboardWindow, WhisperWidget
    from PySide6.QtWidgets import QApplication
    logger.info("组件导入成功 (Components imported).")
except Exception as e:
    logger.critical(f"组件导入失败 (Import failure): {e}", exc_info=True)
    sys.exit(1)


def create_main_window():
    logger.info("正在创建主窗口各个模块 (Creating modules)...")
    modules = [
        ("工作台", MediaConverterWidget()),
        ("视频配音", ElevenLabsWidget()),
        ("语音识别", WhisperWidget()),
        ("场景分割", VideoCutWidget()),
        ("视频下载", VideoDownloadWidget()),
        ("字幕编辑", ASSEditorWidget()),
    ]
    logger.info("所有模块初始化完成 (Modules initialized).")
    return DashboardWindow(modules, version=__version__)


if __name__ == '__main__':
    try:
        logger.info("正在创建 QApplication (Creating QApplication)...")
        app = QApplication(sys.argv)
        
        # 强制设置 Fusion 样式
        logger.info("正在设置界面风格 (Setting Style: Fusion)...")
        app.setStyle("Fusion")
        app.setApplicationName("Media Tools")

        logger.info("正在展示主窗口 (Showing MainWindow)...")
        win = create_main_window()
        win.show()
        
        logger.info("进入主事件循环 (App starting main loop).")
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"运行时发生错误 (Runtime Error): {e}", exc_info=True)
        # 即使没有控制台，也会有弹窗提示 (在 Windows 上比较友好)
        try:
            from PySide6.QtWidgets import QMessageBox
            if 'app' in locals():
                QMessageBox.critical(None, "启动失败", f"程序启动发生关键错误:\n{str(e)}")
        except:
            pass
        sys.exit(1)