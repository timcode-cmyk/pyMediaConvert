import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QLabel, QStackedWidget, QLineEdit, QSpacerItem, QSizePolicy)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon

class SidebarButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("SidebarButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("active", "false")

    def set_active(self, active: bool):
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

class DashboardWindow(QMainWindow):
    def __init__(self, modules, parent=None):
        """
        modules: list of tuples (title, widget_instance)
        """
        super().__init__(parent)
        self.modules = modules
        self.buttons = []
        self.init_ui()
        self.init_stylesheet_listener()

    def init_ui(self):
        self.setWindowTitle("pyMediaTools Dashboard")
        self.resize(1280, 800)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Sidebar ---
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo/Title
        title_label = QLabel("MediaTools")
        title_label.setObjectName("SidebarTitle")
        sidebar_layout.addWidget(title_label)
        sidebar_layout.addSpacing(20)

        # Menu Items
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("MainContentArea")

        for idx, (title, widget) in enumerate(self.modules):
            btn = SidebarButton(f"  {title}")
            btn.clicked.connect(lambda checked, i=idx: self.switch_module(i))
            sidebar_layout.addWidget(btn)
            self.buttons.append(btn)
            
            self.stacked_widget.addWidget(widget)

        sidebar_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Bottom Exit button
        exit_btn = SidebarButton("🚪 退出")
        exit_btn.clicked.connect(self.close)
        sidebar_layout.addWidget(exit_btn)
        sidebar_layout.addSpacing(20)

        main_layout.addWidget(self.sidebar)

        # --- Right Content Area ---
        right_area = QWidget()
        right_area_layout = QVBoxLayout(right_area)
        right_area_layout.setContentsMargins(30, 20, 30, 30)
        right_area_layout.setSpacing(20)

        # Header
        header = QWidget()
        header.setObjectName("Header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.header_title = QLabel("Dashboard")
        self.header_title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.header_title.setStyleSheet("color: #2D3748;")
        
        search_bar = QLineEdit()
        search_bar.setObjectName("HeaderSearch")
        search_bar.setPlaceholderText("Q 关键词查找")
        search_bar.setFixedWidth(300)

        # Mock icons (similar to reference image)
        mock_icons = QLabel(" 🖲️   🔔   🧑 ")
        mock_icons.setStyleSheet("font-size: 16px; color: #4A5568;")
        mock_icons.setCursor(Qt.PointingHandCursor)

        header_layout.addWidget(self.header_title)
        header_layout.addStretch()
        header_layout.addWidget(search_bar)
        header_layout.addSpacing(20)
        header_layout.addWidget(mock_icons)

        right_area_layout.addWidget(header)
        right_area_layout.addWidget(self.stacked_widget)
        
        main_layout.addWidget(right_area)

        # Set initial state
        if self.modules:
            self.switch_module(0)

    def switch_module(self, index):
        self.stacked_widget.setCurrentIndex(index)
        self.header_title.setText(self.modules[index][0])
        for i, btn in enumerate(self.buttons):
            btn.set_active(i == index)

    def init_stylesheet_listener(self):
        from PySide6.QtGui import QGuiApplication
        
        # Apply initial stylesheet
        self.apply_stylesheet(QGuiApplication.styleHints().colorScheme())
        
        # Listen for changes
        QGuiApplication.styleHints().colorSchemeChanged.connect(self.apply_stylesheet)

    def apply_stylesheet(self, scheme=None):
        from PySide6.QtCore import Qt
        
        if scheme == Qt.ColorScheme.Dark:
            file_name = "dashboard_style_dark.qss"
        else:
            file_name = "dashboard_style_light.qss"

        style_path = os.path.join(os.path.dirname(__file__), file_name)
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
