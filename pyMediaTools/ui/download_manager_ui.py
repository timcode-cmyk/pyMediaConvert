from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QTextEdit, QComboBox, QMessageBox, QProgressBar, QFileDialog, 
                               QGroupBox, QSizePolicy, QSpinBox, QApplication)
from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class DownloaderWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        label = QLabel("下载管理功能暂未实现")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)