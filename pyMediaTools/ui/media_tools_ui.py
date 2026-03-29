import os
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, 
                               QLineEdit, QPushButton, QComboBox, QProgressBar, QMessageBox, 
                               QFileDialog, QSizePolicy, QGroupBox, QApplication,
                               QTabWidget, QScrollArea, QCheckBox, QSpinBox, QFrame, QGridLayout)
from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt, QSettings
from PySide6.QtGui import QFont, QPixmap, QCursor

from ..core.config import MODES
from .styles import apply_common_style
from pyMediaTools import get_logger
from ..utils import load_project_config

logger = get_logger(__name__)


class DropLineEdit(QLineEdit):
    pathDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setReadOnly(True)  # 防止手动乱输

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            local_path = event.mimeData().urls()[0].toLocalFile()
            self.setText(local_path)
            self.pathDropped.emit(local_path)
            event.accept()
        else:
            super().dropEvent(event)


class ProgressMonitor(QObject):
    file_progress = Signal(float, float, str)
    overall_progress = Signal(int, int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stop_requested = False

    def update_file_progress(self, seconds: float, duration: float, name: str):
        self.file_progress.emit(seconds, duration, name)
    def update_overall_progress(self, current: int, total: int, status: str):
        self.overall_progress.emit(current, total, status)
    def check_stop_flag(self) -> bool:
        return self.stop_requested
    def request_stop(self):
        self.stop_requested = True


class ConversionWorker(QObject):
    finished = Signal(bool, str)

    def __init__(self, input_dir, output_dir, mode_config, monitor, parent=None):
        super().__init__(parent)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.mode_config = mode_config
        self.monitor = monitor

    @Slot()
    def run(self):
        is_successful = False
        error_msg = ""
        try:
            ConverterClass = self.mode_config['class']
            converter = ConverterClass(
                params=self.mode_config.get('params', {}),
                support_exts=self.mode_config.get('support_exts'),
                output_ext=self.mode_config.get('output_ext')
            )
            converter.run(Path(self.input_dir), Path(self.output_dir), self.monitor)
            is_successful = not self.monitor.check_stop_flag()
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            logger.exception(f"Worker 线程异常: {e}")
            is_successful = False
        finally:
            self.finished.emit(is_successful, error_msg)


class LogoConfigWidget(QFrame):
    def __init__(self, platform_name, default_path, x, y, default_scale, blur, enabled, parent=None):
        super().__init__(parent)
        self.platform_name = platform_name
        self.default_path = default_path
        self.config_x = x
        self.config_y = y
        self.config_scale = default_scale
        
        self.is_enabled = enabled
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("LogoCard")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)
        
        # 1. Image
        self.lbl_logo = QLabel()
        from pyMediaTools.utils import get_resource_path
        pixmap = QPixmap(str(get_resource_path(default_path)))
        if not pixmap.isNull():
            # scale the pixmap to a smaller height
            self.lbl_logo.setPixmap(pixmap.scaledToHeight(26, Qt.SmoothTransformation))
        else:
            self.lbl_logo.setText(platform_name)
        self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Ensure white logos are visible on light mode by adding a dark rounded background just for the image area
        self.lbl_logo.setStyleSheet("""
            QLabel {
                background-color: rgba(35, 35, 35, 0.8);
                border-radius: 5px;
                padding: 4px;
                color: white;
            }
        """)
        layout.addWidget(self.lbl_logo)
        
        # 2. Controls Layout (Name + Blur checkbox)
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 3, 0, 0)
        
        self.lbl_name = QLabel(platform_name)
        self.lbl_name.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        
        self.chk_blur = QCheckBox("背景模糊")
        self.chk_blur.setChecked(blur)
        
        controls_layout.addWidget(self.lbl_name)
        controls_layout.addStretch()
        controls_layout.addWidget(self.chk_blur)
        
        layout.addLayout(controls_layout)
        
        self.update_style()
        self.chk_blur.setEnabled(self.is_enabled)
        
    def mousePressEvent(self, event):
        # Prevent checking or unchecking if clicking on the checkbox itself
        child = self.childAt(event.position().toPoint())
        if child == self.chk_blur:
            super().mousePressEvent(event)
            return
            
        self.is_enabled = not self.is_enabled
        self.chk_blur.setEnabled(self.is_enabled)
        self.update_style()
        super().mousePressEvent(event)

    def update_style(self):
        if self.is_enabled:
            self.setStyleSheet("""
                QFrame#LogoCard {
                    background-color: rgba(65, 137, 230, 0.1);
                    border: 2px solid #4189E6;
                    border-radius: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#LogoCard {
                    background-color: transparent;
                    border: 1px solid #777777;
                    border-radius: 10px;
                }
                QFrame#LogoCard:hover {
                    border: 1px solid #AAAAAA;
                    background-color: rgba(255, 255, 255, 0.05);
                }
            """)

    def get_config(self):
        return {
            "enabled": self.is_enabled,
            "name": self.platform_name,
            "path": self.default_path,
            "x": self.config_x,
            "y": self.config_y,
            "scale": self.config_scale,
            "blur": self.chk_blur.isChecked()
        }
        
    def set_config(self, cfg):
        if not isinstance(cfg, dict):
            return
        if "enabled" in cfg:
            self.is_enabled = bool(cfg["enabled"])
            self.update_style()
            self.chk_blur.setEnabled(self.is_enabled)
        if "blur" in cfg:
            self.chk_blur.setChecked(bool(cfg["blur"]))


class MediaConverterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker_thread = None
        self.conversion_monitor = None
        self.is_converting = False
        self.last_total_files = 0
        self.last_stop_requested = False
        self.logo_widgets = []
        self.init_ui()
        self.apply_styles()

    def apply_styles(self):
        apply_common_style(self)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # title = QLabel("媒体转换工具 v1.14.2")
        # title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        # title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        # main_layout.addWidget(title)

        # Tabs for Modes
        self.tabs = QTabWidget()
        
        # ---------------- Tab 1: Watermark ----------------
        self.tab_watermark = QWidget()
        wm_layout = QVBoxLayout(self.tab_watermark)
        
        wm_desc = QLabel("多选下方 Logo，程序会将其叠加到视频上。可独立设置位置、缩放比例、并应用底层模糊。")
        wm_desc.setWordWrap(True)
        wm_layout.addWidget(wm_desc)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.logos_layout = QGridLayout(scroll_content)
        self.logos_layout.setSpacing(15)
        
        # 从 config.toml 加载平台配置
        config = load_project_config()
        platforms = config.get('watermark', {}).get('platforms', [])
        
        if not platforms:
            platforms = [
                {"name": "Dreamina AI", "path": "assets/Dream.png"},
                {"name": "Gemini", "path": "assets/Gemini.png"},
                {"name": "Vidu", "path": "assets/vidu.png"},
                {"name": "Veo", "path": "assets/Veo.png"},
                {"name": "Kling", "path": "assets/Kling.png"},
                {"name": "Hailuo", "path": "assets/Hailuo.png"},
                {"name": "HeyGen", "path": "assets/HeyGen.png"},
            ]
        
        row = 0
        col = 0
        for plat in platforms:
            if isinstance(plat, list):
                # old format fallback
                name, pth = plat[0], plat[1]
                x, y, scale, blur, enabled = 700, 1810, 100, False, False
            else:
                name = plat.get("name", "Unknown")
                pth = plat.get("path", "")
                x = plat.get("x", 700)
                y = plat.get("y", 1810)
                scale = plat.get("scale", 100)
                blur = plat.get("blur", False)
                enabled = plat.get("enabled", False)
                
            lw = LogoConfigWidget(name, pth, x, y, scale, blur, enabled)
            self.logos_layout.addWidget(lw, row, col)
            self.logo_widgets.append(lw)
            col += 1
            if col > 1:
                col = 0
                row += 1
            
        self.logos_layout.setRowStretch(row + 1, 1)
        scroll.setWidget(scroll_content)
        wm_layout.addWidget(scroll)
        self.tabs.addTab(self.tab_watermark, "水印添加")
        
        # ---------------- Tab 2: Transcode ----------------
        self.tab_transcode = QWidget()
        tc_layout = QVBoxLayout(self.tab_transcode)
        
        self.mode_combo = QComboBox()
        self.mode_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mode_combo.currentIndexChanged.connect(self.updateModeDescription)
        
        self.desc_label = QLabel("请选择转码模式以查看详情。")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: palette(mid); margin-top: 5px;")
        
        tc_layout.addWidget(QLabel("常规转码模式:"))
        tc_layout.addWidget(self.mode_combo)
        tc_layout.addWidget(self.desc_label)
        tc_layout.addStretch()
        self.tabs.addTab(self.tab_transcode, "格式转码")
        
        main_layout.addWidget(self.tabs)

        # 2. 路径设置区
        path_group = QGroupBox("源文件与输出")
        path_layout = QFormLayout(path_group)
        path_layout.setSpacing(10)

        self.input_path_edit = DropLineEdit()
        self.input_path_edit.setPlaceholderText("📂 拖放文件夹/文件到此处，或点击右侧按钮")
        self.input_path_edit.setMinimumHeight(40)
        self.input_path_edit.pathDropped.connect(self.updateOutputPath)
        self.input_path_edit.textChanged.connect(self.updateOutputPath)
        
        input_btn = QPushButton("浏览...")
        input_btn.setCursor(Qt.PointingHandCursor)
        input_btn.setMinimumHeight(40)
        input_btn.clicked.connect(self.selectInputPath)
        
        input_box = QHBoxLayout()
        input_box.setContentsMargins(0, 0, 0, 0)
        input_box.addWidget(self.input_path_edit)
        input_box.addWidget(input_btn)
        
        path_layout.addRow("输入:" + " "*4, input_box)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("转换后的文件将保存在这里")
        self.output_path_edit.setMinimumHeight(40)
        
        output_btn = QPushButton("浏览...")
        output_btn.setCursor(Qt.PointingHandCursor)
        output_btn.setMinimumHeight(40)
        output_btn.clicked.connect(self.selectOutputDirectory)
        
        output_box = QHBoxLayout()
        output_box.setContentsMargins(0, 0, 0, 0)
        output_box.addWidget(self.output_path_edit)
        output_box.addWidget(output_btn)
        
        path_layout.addRow("输出:" + " "*4, output_box)
        main_layout.addWidget(path_group)

        # 3. 进度与操作区
        progress_group = QGroupBox("状态与控制")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(8)

        self.status_label = QLabel("等待开始...")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)
        
        progress_grid = QHBoxLayout()
        progress_grid.setContentsMargins(0, 0, 0, 0)
        
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setRange(0, 100)
        self.file_progress_text = QLabel("无")
        self.file_progress_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_progress_text.setFixedWidth(50)
        
        f_box = QHBoxLayout()
        f_box.addWidget(QLabel("文件:"))
        f_box.addWidget(self.file_progress_bar)
        f_box.addWidget(self.file_progress_text)
        
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_text = QLabel("0/0 (0%)")
        self.overall_progress_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overall_progress_text.setFixedWidth(80)
        
        o_box = QHBoxLayout()
        o_box.addWidget(QLabel("总计:"))
        o_box.addWidget(self.overall_progress_bar)
        o_box.addWidget(self.overall_progress_text)

        progress_grid.addLayout(f_box)
        progress_grid.addSpacing(20)
        progress_grid.addLayout(o_box)

        progress_layout.addLayout(progress_grid)
        progress_layout.addWidget(self.status_label)
        main_layout.addWidget(progress_group)

        self.start_stop_button = QPushButton("🚀 开始转换")
        self.start_stop_button.setObjectName('StartStopButton')
        self.start_stop_button.setCursor(Qt.PointingHandCursor)
        self.start_stop_button.clicked.connect(self.toggleConversion)
        self.start_stop_button.setProperty('converting', 'false')
        self.start_stop_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.start_stop_button.setMinimumHeight(45)
        main_layout.addWidget(self.start_stop_button)

        self.loadModes()


    def loadModes(self):
        if not MODES:
            self.mode_combo.addItem("ERROR: Config file not loaded.", None)
            return
        
        # 只在转码 Tab 展示非 Logo 的转换模式
        # 也就是不在模式里展示 LogoConverter，因为我们在水印tab原生支持
        from ..core.mediaconvert import LogoConverter
        for key, config in MODES.items():
            if config['class'] == LogoConverter:
                continue
            display_text = f"{config['description']} [{key}]"
            self.mode_combo.addItem(display_text, key)
        self.updateModeDescription()

    def updateModeDescription(self):
        mode_key = self.mode_combo.currentData()
        if mode_key and mode_key in MODES:
            desc = MODES[mode_key]['description']
            support_exts = MODES[mode_key].get('support_exts')
            exts = ", ".join(support_exts) if support_exts else "自动检测"
            self.desc_label.setText(f"说明: {desc}\n支持格式: {exts}")
        else:
            self.desc_label.setText("模式说明: 未知模式或配置未加载。")

    def selectInputPath(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择输入文件或目录", "", "All Files (*);;Videos (*.mp4 *.mkv *.mov *.avi *.m4v *.webm)")
        if not path:
            path = QFileDialog.getExistingDirectory(self, "选择输入目录")
        if path:
            self.input_path_edit.setText(path)
            self.updateOutputPath(self.input_path_edit.text())

    def selectOutputDirectory(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_path_edit.setText(path)

    @Slot(str)
    def updateOutputPath(self, input_path: str):
        input_path = input_path.strip()
        if input_path and os.path.exists(input_path):
            input_dir = os.path.dirname(input_path) if os.path.isfile(input_path) else input_path
            default_output = os.path.join(input_dir, "CONVERTED_OUTPUT")
            self.output_path_edit.setText(default_output)
        else:
            self.output_path_edit.setText("")

    def toggleConversion(self):
        if self.is_converting:
            self.stopConversion()
        else:
            self.startConversion()

    def startConversion(self):
        
        input_dir = self.input_path_edit.text().strip()
        output_dir = self.output_path_edit.text().strip()
        
        if not (os.path.isdir(input_dir) or os.path.isfile(input_dir)):
            QMessageBox.critical(self, "配置错误", "请输入有效的文件或文件夹路径。")
            return
            
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError as e:
                QMessageBox.critical(self, "系统错误", f"无法创建输出目录: {e}")
                return

        current_tab_idx = self.tabs.currentIndex()
        if current_tab_idx == 0:
            # Watermark Tab Mode
            active_logos = []

            # 添加勾选的平台
            for lw in self.logo_widgets:
                c = lw.get_config()
                if c["enabled"]:
                    if c["name"] == "Dreamina AI":
                        # Dream_AI 锁定在左上角
                        active_logos.append({
                            "logo_path": "assets/Dream_AI.png",
                            "x": 0, "y": 0, "scale": 100, "blur": True
                        })
                    
                    active_logos.append({
                        "logo_path": c["path"],
                        "x": c["x"],
                        "y": c["y"],
                        "scale": c["scale"],
                        "blur": c["blur"]
                    })
            
            if len(active_logos) == 0:
                QMessageBox.warning(self, "参数错误", "请至少勾选一个平台徽标！")
                return
            
            from ..core.mediaconvert import LogoConverter
            # Dynamic mode config
            mode_config = {
                'class': LogoConverter,
                'support_exts': [".mp4", ".mov", ".mkv", ".webm", ".avi"],
                'output_ext': "_watermarked.mp4",
                'params': {
                    'target_w': 1080,  # 默认竖屏
                    'target_h': 1920,
                    'logos': active_logos
                }
            }
        else:
            # Transcode Mode
            mode_key = self.mode_combo.currentData()
            mode_config = MODES.get(mode_key)
            if not mode_config:
                QMessageBox.critical(self, "配置错误", "请选择有效的转换模式。")
                return

        # 检查文件
        try:
            self.status_label.setText("正在扫描文件...")
            QApplication.processEvents() 
            temp_worker = mode_config['class'](params=mode_config.get('params', {}), support_exts=mode_config.get('support_exts'), init_checks=False)
            temp_worker.find_files(Path(input_dir))
            files_to_process_count = len(temp_worker.files)
        except Exception as e:
            logger.exception(f"文件扫描失败: {e}")
            QMessageBox.critical(self, "错误", f"文件扫描失败: {e}")
            return

        if files_to_process_count == 0:
            QMessageBox.warning(self, "无文件", f"在目录中未找到支持的文件类型。\n支持类型: {mode_config.get('support_exts')}")
            return

        self.last_total_files = files_to_process_count
        self.last_stop_requested = False
        self.is_converting = True
        
        self.start_stop_button.setText(f"🛑 停止转换")
        self.start_stop_button.setProperty('converting', 'true')
        self.start_stop_button.style().unpolish(self.start_stop_button)
        self.start_stop_button.style().polish(self.start_stop_button)
        
        self.overall_progress_bar.setValue(0)
        self.file_progress_bar.setValue(0)
        self.overall_progress_text.setText(f"0/{self.last_total_files}")
        self.file_progress_text.setText("准备中...")
        self.status_label.setText(f"正在初始化 Worker，共 {self.last_total_files} 个文件...")

        self.worker_thread = QThread()
        self.conversion_monitor = ProgressMonitor()
        self.worker = ConversionWorker(input_dir, output_dir, mode_config, self.conversion_monitor)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.conversionFinished)
        self.conversion_monitor.file_progress.connect(self.updateFileProgress)
        self.conversion_monitor.overall_progress.connect(self.updateOverallProgress)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def stopConversion(self):
        if self.worker_thread and self.worker_thread.isRunning() and self.conversion_monitor:
            self.last_stop_requested = True
            self.conversion_monitor.request_stop()
            self.status_label.setText("正在请求停止... FFMPEG 进程可能需要几秒钟才能释放。")
            self.start_stop_button.setEnabled(False)

    @Slot(float, float, str)
    def updateFileProgress(self, seconds: float, duration: float, file_name: str):
        if duration > 0:
            file_progress = min(100.0, (seconds / duration) * 100.0)
            self.file_progress_bar.setValue(int(file_progress))
            self.file_progress_text.setText(f"{file_progress:.1f}%")
        else:
            self.file_progress_bar.setValue(0)
            self.file_progress_text.setText("计算中...")
        
        display_name = (file_name[:40] + '..') if len(file_name) > 40 else file_name
        self.status_label.setText(f"正在处理: {display_name}")

    @Slot(int, int, str)
    def updateOverallProgress(self, current: int, total: int, status: str):
        if total > 0:
            pct = int((current / total) * 100.0)
            if current >= total:
                pct = 100
            self.overall_progress_bar.setValue(pct)
            self.overall_progress_text.setText(f"{current}/{total} ({pct}%)")
        
        if not self.is_converting:
            self.status_label.setText(status)

    @Slot(bool, str)
    def conversionFinished(self, is_successful, error_msg: str = ""):
        self.is_converting = False
        self.start_stop_button.setEnabled(True)
        self.start_stop_button.setText("🚀 开始转换")
        self.start_stop_button.setProperty('converting', 'false')
        self.start_stop_button.style().unpolish(self.start_stop_button)
        self.start_stop_button.style().polish(self.start_stop_button)

        if is_successful:
            self.overall_progress_bar.setValue(100)
            self.file_progress_bar.setValue(100)
            self.overall_progress_text.setText(f"{self.last_total_files}/{self.last_total_files} (100%)")
            self.file_progress_text.setText("100%")
            self.status_label.setText("所有任务已完成。")
            QMessageBox.information(self, "完成", "所有文件转换成功完成!")
        elif self.last_stop_requested:
            self.status_label.setText("任务已由用户手动停止。")
            QMessageBox.information(self, "已中断", "转换操作已停止。")
        else:
            self.status_label.setText("转换过程中遇到错误。")
            if error_msg:
                first_line = error_msg.strip().splitlines()[0]
                if "not found" in first_line.lower() or "未找到" in first_line:
                    QMessageBox.critical(self, "错误", f"资源未找到：{first_line}\n请检查 assets/ 目录并确保字体/资源存在。")
                else:
                    QMessageBox.critical(self, "错误", f"转换失败: {first_line}\n详情请查看日志。")
            else:
                QMessageBox.critical(self, "错误", "转换失败，请查看日志获取详情。")
