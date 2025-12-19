from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QTextEdit, QComboBox, QMessageBox, QProgressBar, QFileDialog, 
                               QGroupBox, QSizePolicy, QSpinBox, QApplication)
from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class VideoDownloaWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()