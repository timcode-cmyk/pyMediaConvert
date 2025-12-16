import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from pyMediaConvert.ui.media_tools_ui import MediaConverterWidget
from pyMediaConvert.ui.elevenlabs_ui import ElevenLabsWidget
from pyMediaConvert.logging_config import setup_logging

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
        self.setCentralWidget(tabs)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = ToolBoxMainWindow()
    win.show()
    sys.exit(app.exec())