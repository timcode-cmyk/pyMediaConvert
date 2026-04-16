import os
import sys
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QLabel, QStackedWidget, QLineEdit, QSpacerItem, 
                               QSizePolicy, QDialog, QTextEdit, QFrame)
from PySide6.QtCore import Qt, QSize, QPoint, QThread, Signal, Slot, QUrl
from PySide6.QtGui import QFont, QIcon, QDesktopServices
from pyMediaTools.core.update import check_latest_release

class UpdateCheckWorker(QThread):
    """异步检测 GitHub Release 更新"""
    finished = Signal(dict)

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def run(self):
        # 调用核心逻辑
        info = check_latest_release(current_version=self.current_version)
        self.finished.emit(info)

class UpdateDialog(QDialog):
    """更新检测子窗口"""
    def __init__(self, update_info, current_version, parent=None):
        super().__init__(parent)
        self.setWindowTitle("版本检测")
        self.resize(500, 380)
        self.info = update_info
        layout = QVBoxLayout(self)
        
        status_text = f"🚀 发现新版本: v{self.info['latest_version']}" if self.info['has_update'] else "🎉 当前已是最新版本"
        header = QLabel(status_text)
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: palette(highlight);")
        layout.addWidget(header)
        
        layout.addWidget(QLabel(f"当前版本: v{current_version}"))
        layout.addWidget(QLabel("更新日志:"))
        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setPlainText(self.info['release_notes'])
        layout.addWidget(notes)
        
        btn_layout = QHBoxLayout()
        if self.info['has_update']:
            btn_dl = QPushButton("💾 下载最新安装包")
            btn_dl.setCursor(Qt.PointingHandCursor)
            btn_dl.clicked.connect(self.open_download)
            btn_layout.addWidget(btn_dl)
            
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def open_download(self):
        import platform
        url = self.info['download_url']
        system = sys.platform
        machine = platform.machine().lower()
        
        # 定义当前平台的识别关键字（对应 release.yml 中的 platform_tag）
        if system == "win32":
            target_tag = "win-x64"
            preferred_exts = ('.exe', '.zip')
        elif system == "darwin":
            if machine in ('arm64', 'aarch64'):
                target_tag = "mac-AppleSilicon"
            else:
                target_tag = "mac-Intel"
            preferred_exts = ('.dmg', '.pkg', '.zip')
        else:
            target_tag = ""
            preferred_exts = ('.exe', '.dmg', '.pkg', '.zip')

        # 优先级：首先尝试匹配对应平台的 tag 且后缀名正确
        best_match = None
        for asset in self.info['assets']:
            name = asset.get('name', '')
            # 检查是否包含平台标识 (如 mac-AppleSilicon)
            if target_tag and target_tag.lower() in name.lower():
                if name.lower().endswith(preferred_exts):
                    best_match = asset.get('browser_download_url')
                    # 如果匹配了最理想的后缀（dmg/exe），直接退出循环
                    if name.lower().endswith(preferred_exts[:1]):
                        break
        
        if best_match:
            url = best_match
        else:
            # 次优选择：寻找任何匹配当前系统后缀的文件
            for asset in self.info['assets']:
                name = asset.get('name', '').lower()
                if name.endswith(preferred_exts):
                    url = asset.get('browser_download_url', url)
                    break
                    
        QDesktopServices.openUrl(QUrl(url))

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

class WindowControlButton(QPushButton):
    def __init__(self, obj_name, parent=None):
        super().__init__(parent)
        self.setObjectName(obj_name)
        self.setFixedSize(12, 12)
        self.setCursor(Qt.PointingHandCursor)

class DashboardWindow(QMainWindow):
    def __init__(self, modules, version="1.0.0", parent=None):
        """
        modules: list of tuples (title, widget_instance)
        """
        super().__init__(parent)
        self.modules = modules
        self.version = version
        self.update_info = None
        self.buttons = []
        self.init_ui()
        self.init_stylesheet_listener()
        self.check_for_updates()

    def init_ui(self):
        self.setWindowTitle("pyMediaTools")
        self.resize(1100, 720)
        
        # 设置无边框与透明背景（实现圆角关键）
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # 主容器：用于承载背景色和圆角
        self.main_container = QWidget()
        self.main_container.setObjectName("MainContainer")
        self.setCentralWidget(self.main_container)
        
        main_layout = QHBoxLayout(self.main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Sidebar ---
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 15, 0, 0)
        sidebar_layout.setSpacing(0)

        # --- macOS 风格红绿灯按钮 (放在侧边栏顶部) ---
        if sys.platform == "darwin":
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(15, 0, 0, 10)
            btn_layout.setSpacing(8)
            self.btn_close = WindowControlButton("WindowClose")
            self.btn_min = WindowControlButton("WindowMin")
            self.btn_max = WindowControlButton("WindowMax")
            for b in [self.btn_close, self.btn_min, self.btn_max]: btn_layout.addWidget(b)
            btn_layout.addStretch()
            sidebar_layout.addLayout(btn_layout)

        # Logo/Title
        title_label = QLabel("MediaTools")
        title_label.setObjectName("SidebarTitle")
        title_label.setContentsMargins(20, 10, 0, 10)
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

        # --- 版本号与设置按钮 ---
        ver_set_layout = QHBoxLayout()
        ver_set_layout.setContentsMargins(20, 0, 20, 0)
        
        self.version_label = QLabel(f"v{self.version}")
        self.version_label.setStyleSheet("color: #718096; font-size: 11px; margin-bottom: 2px;")
        self.version_label.setCursor(Qt.PointingHandCursor)
        self.version_label.mousePressEvent = lambda e: self.show_update_dialog()
        ver_set_layout.addWidget(self.version_label)
        
        ver_set_layout.addStretch()
        
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedSize(24, 24)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 15px; } QPushButton:hover { background: rgba(0,0,0,0.05); border-radius: 12px; }")
        self.settings_btn.clicked.connect(self.show_settings_dialog)
        ver_set_layout.addWidget(self.settings_btn)
        
        sidebar_layout.addLayout(ver_set_layout)

        github_link = QLabel("<a href='https://github.com/timcode-cmyk/pyMediaConvert' style='color: #4A5568; text-decoration: none;'>GitHub Project</a>")
        github_link.setAlignment(Qt.AlignCenter)
        github_link.setOpenExternalLinks(True)
        github_link.setStyleSheet("font-size: 11px; margin-bottom: 10px;")
        sidebar_layout.addWidget(github_link)

        # Bottom Exit button
        exit_btn = SidebarButton("🚪 退出")
        exit_btn.clicked.connect(self.close)
        sidebar_layout.addWidget(exit_btn)
        sidebar_layout.addSpacing(20)

        main_layout.addWidget(self.sidebar)

        # --- Right Content Area ---
        right_area = QWidget()
        right_area_layout = QVBoxLayout(right_area)
        right_area_layout.setContentsMargins(20, 10, 20, 15)
        right_area_layout.setSpacing(15)

        # Header
        header = QWidget()
        header.setObjectName("Header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.header_title = QLabel("Dashboard")
        self.header_title.setObjectName("HeaderTitleText")
        self.header_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        
        # --- Search Bar with Icon Styling ---
        self.search_container = QFrame()
        self.search_container.setObjectName("SearchContainer")
        self.search_container.setAttribute(Qt.WA_StyledBackground, True)
        self.search_container.setFixedWidth(320)
        search_layout = QHBoxLayout(self.search_container)
        search_layout.setContentsMargins(10, 0, 10, 0)
        search_layout.setSpacing(5)
        
        search_icon = QLabel("Q")
        search_icon.setStyleSheet("color: #718096; font-size: 14px;")
        
        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("HeaderSearch")
        self.search_bar.setPlaceholderText("关键词查找工具...")
        self.search_bar.setFrame(False)
        self.search_bar.setStyleSheet("background: transparent; border: none; padding: 5px;")
        
        search_layout.addWidget(search_icon)
        search_layout.addWidget(self.search_bar)

        # --- Header Action Icons ---
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(15)
        
        btn_feedback = QPushButton("💬")
        btn_feedback.setToolTip("反馈建议")
        btn_notif = QPushButton("🔔")
        btn_notif.setToolTip("通知中心")
        btn_user = QPushButton("👤")
        btn_user.setToolTip("用户中心")
        
        for b in [btn_feedback, btn_notif, btn_user]:
            b.setFixedSize(32, 32)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border-radius: 16px;
                    font-size: 16px;
                    color: #4A5568;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 0.05);
                }
            """)
            actions_layout.addWidget(b)

        header_layout.addWidget(self.header_title)
        header_layout.addStretch()
        header_layout.addWidget(self.search_container)
        header_layout.addSpacing(10)
        header_layout.addLayout(actions_layout)
        
        # --- Windows 风格控制按钮 (放在 Header 右侧) ---
        if sys.platform != "darwin":
            win_btn_layout = QHBoxLayout()
            win_btn_layout.setContentsMargins(10, 0, 0, 0)
            win_btn_layout.setSpacing(15)
            self.btn_min = QPushButton("—")
            self.btn_max = QPushButton("▢")
            self.btn_close = QPushButton("✕")
            for b, name in zip([self.btn_min, self.btn_max, self.btn_close], ["WinMin", "WinMax", "WinClose"]):
                b.setObjectName(name)
                win_btn_layout.addWidget(b)
            header_layout.addLayout(win_btn_layout)

        right_area_layout.addWidget(header)
        right_area_layout.addWidget(self.stacked_widget)
        
        main_layout.addWidget(right_area)

        # 绑定基础功能
        self.btn_close.clicked.connect(self.close)
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_max.clicked.connect(self.toggle_maximize)

        # Set initial state
        if self.modules:
            self.switch_module(0)

    # --- 窗口拖拽逻辑 ---
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def mouseDoubleClickEvent(self, event):
        # 双击顶部区域最大化/还原
        if event.button() == Qt.LeftButton and event.position().y() < 70:
            self.toggle_maximize()
            event.accept()

    def _resize_edge_at_pos(self, pos):
        margin = 8
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        top = y <= margin
        bottom = y >= h - margin
        left = x <= margin
        right = x >= w - margin

        if top and left:
            return Qt.TopLeftCorner
        if top and right:
            return Qt.TopRightCorner
        if bottom and left:
            return Qt.BottomLeftCorner
        if bottom and right:
            return Qt.BottomRightCorner
        if left:
            return Qt.LeftEdge
        if right:
            return Qt.RightEdge
        if top:
            return Qt.TopEdge
        if bottom:
            return Qt.BottomEdge
        return None

    def _update_resize_cursor(self, event):
        if self.isMaximized():
            self.unsetCursor()
            return
        edge = self._resize_edge_at_pos(event.pos())
        if edge in (Qt.TopEdge, Qt.BottomEdge):
            self.setCursor(Qt.SizeVerCursor)
        elif edge in (Qt.LeftEdge, Qt.RightEdge):
            self.setCursor(Qt.SizeHorCursor)
        elif edge in (Qt.TopLeftCorner, Qt.BottomRightCorner):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edge in (Qt.TopRightCorner, Qt.BottomLeftCorner):
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.isMaximized():
            edge = self._resize_edge_at_pos(event.pos())
            if edge and self.windowHandle():
                self.windowHandle().startSystemResize(edge)
                event.accept()
                return
            if event.position().y() < 70:
                self.windowHandle().startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.NoButton:
            self._update_resize_cursor(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def switch_module(self, index):
        self.stacked_widget.setCurrentIndex(index)
        self.header_title.setText(self.modules[index][0])
        for i, btn in enumerate(self.buttons):
            btn.set_active(i == index)

    def check_for_updates(self):
        """启动后台更新检测"""
        self.update_worker = UpdateCheckWorker(self.version)
        self.update_worker.finished.connect(self.on_update_checked)
        self.update_worker.start()

    def on_update_checked(self, info):
        """更新检测完成回调"""
        self.update_info = info
        if info['has_update']:
            self.version_label.setText(f"v{self.version} (发现新版本: v{info['latest_version']})")
            self.version_label.setStyleSheet("color: #e53e3e; font-size: 11px; font-weight: bold; margin-bottom: 2px;")
            self.version_label.setToolTip("点击查看更新内容并下载新版本")

    def show_update_dialog(self):
        """弹出更新对话框"""
        if self.update_info:
            dialog = UpdateDialog(self.update_info, self.version, self)
            dialog.exec()
        else:
            self.check_for_updates()

    def show_settings_dialog(self):
        """弹出全局设置面板"""
        from pyMediaTools.ui.settings_dialog import GlobalSettingsDialog
        dialog = GlobalSettingsDialog(self)
        dialog.exec()

    def init_stylesheet_listener(self):
        from PySide6.QtGui import QGuiApplication
        
        # Apply initial stylesheet
        self.apply_stylesheet(QGuiApplication.styleHints().colorScheme())
        
        # Listen for changes
        QGuiApplication.styleHints().colorSchemeChanged.connect(self.apply_stylesheet)

    def apply_stylesheet(self, scheme=None):
        from PySide6.QtCore import Qt
        from .qss_resources import DARK_STYLE, LIGHT_STYLE
        
        if scheme == Qt.ColorScheme.Dark:
            self.setStyleSheet(DARK_STYLE)
        else:
            self.setStyleSheet(LIGHT_STYLE)
