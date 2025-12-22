import os
import platform
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, 
                               QLineEdit, QPushButton, QComboBox, QProgressBar, QMessageBox, 
                               QFileDialog, QSizePolicy, QGroupBox, QApplication)
from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtGui import QFont, QPalette, QColor

from pyMediaTools.core.config import MODES
from .styles import apply_common_style
from pyMediaTools import get_logger

logger = get_logger(__name__)


class DropLineEdit(QLineEdit):
    pathDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setReadOnly(True)  # 防止手动乱输，鼓励拖拽或点击按钮

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            local_path = event.mimeData().urls()[0].toLocalFile()
            if os.path.isdir(local_path):
                self.setText(local_path)
                self.pathDropped.emit(local_path)
                event.accept()
            else:
                directory = os.path.dirname(local_path)
                self.setText(directory)
                self.pathDropped.emit(directory)
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
    # Emit (success: bool, error_msg: str)
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
            # pm_worker.GlobalProgressMonitor = self.monitor
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
            logger.exception(f"Worker 线程中发生未捕获的异常: {e}")
            is_successful = False
        finally:
            # pm_worker.GlobalProgressMonitor = None
            # Emit error message (empty string if none)
            self.finished.emit(is_successful, error_msg)


class MediaConverterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker_thread = None
        self.conversion_monitor = None
        self.is_converting = False
        self.last_total_files = 0
        self.last_stop_requested = False
        self.init_ui()
        self.apply_styles()

    def apply_styles(self):
        # 使用统一的样式并保留向后扩展的能力
        apply_common_style(self)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20) # 增加边距
        main_layout.setSpacing(15)

        # 标题区域
        title = QLabel("媒体转换工具")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(title)

        # 1. 模式选择区
        mode_group = QGroupBox("STEP 1: 选择转换模式")
        mode_layout = QVBoxLayout(mode_group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mode_combo.currentIndexChanged.connect(self.updateModeDescription)
        
        self.desc_label = QLabel("请选择一个转换模式以查看详情。")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: palette(mid); margin-top: 5px;")
        
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addWidget(self.desc_label)
        main_layout.addWidget(mode_group)

        # 2. 路径设置区
        path_group = QGroupBox("STEP 2: 文件路径")
        path_layout = QVBoxLayout(path_group)
        path_layout.setSpacing(10)

        # 输入
        input_label = QLabel("输入源 (拖拽文件夹到下方框中):")
        self.input_path_edit = DropLineEdit()
        self.input_path_edit.setPlaceholderText("📂 拖放文件夹/文件到此处，或点击右侧按钮")
        self.input_path_edit.setMinimumHeight(50) # 增加高度方便拖拽
        self.input_path_edit.pathDropped.connect(self.updateOutputPath)
        self.input_path_edit.textChanged.connect(self.updateOutputPath)
        
        input_btn = QPushButton("浏览...")
        input_btn.setCursor(Qt.PointingHandCursor)
        input_btn.clicked.connect(self.selectInputPath)
        
        input_box = QHBoxLayout()
        input_box.addWidget(self.input_path_edit)
        input_box.addWidget(input_btn)
        
        path_layout.addWidget(input_label)
        path_layout.addLayout(input_box)

        # 输出
        output_label = QLabel("输出目录:")
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("转换后的文件将保存在这里")
        
        output_btn = QPushButton("浏览...")
        output_btn.setCursor(Qt.PointingHandCursor)
        output_btn.clicked.connect(self.selectOutputDirectory)
        
        output_box = QHBoxLayout()
        output_box.addWidget(self.output_path_edit)
        output_box.addWidget(output_btn)
        
        path_layout.addWidget(output_label)
        path_layout.addLayout(output_box)
        
        main_layout.addWidget(path_group)

        # 3. 进度与操作区
        progress_group = QGroupBox("STEP 3: 状态与控制")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(8)

        self.status_label = QLabel("等待开始...")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)
        
        # 进度条
        progress_layout.addWidget(QLabel("总进度:"))
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_text = QLabel("0/0 (0%)")
        self.overall_progress_text.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        overall_layout = QHBoxLayout()
        overall_layout.addWidget(self.overall_progress_bar)
        overall_layout.addWidget(self.overall_progress_text)
        progress_layout.addLayout(overall_layout)

        progress_layout.addWidget(QLabel("当前文件:"))
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setRange(0, 100)
        self.file_progress_text = QLabel("无")
        self.file_progress_text.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        file_p_layout = QHBoxLayout()
        file_p_layout.addWidget(self.file_progress_bar)
        file_p_layout.addWidget(self.file_progress_text)
        progress_layout.addLayout(file_p_layout)
        
        progress_layout.addWidget(self.status_label)
        main_layout.addWidget(progress_group)

        # 启动按钮
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
        for key, config in MODES.items():
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
        path, _ = QFileDialog.getOpenFileName(self, "选择输入文件 (将使用其目录) 或选择目录", "", "All Files (*);;Videos (*.mp4 *.mkv *.mov)")
        if not path:
            # 尝试作为目录打开 (Qt 没有原生的既选文件又选目录的对话框，通常分步处理)
            path = QFileDialog.getExistingDirectory(self, "选择输入目录")
        
        if path:
            if os.path.isfile(path):
                directory = os.path.dirname(path)
                self.input_path_edit.setText(directory)
            else:
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
            default_output = os.path.join(input_dir, "PROCESSED_OUTPUT")
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
        mode_key = self.mode_combo.currentData()
        mode_config = MODES.get(mode_key)
        
        if not os.path.isdir(input_dir) or not mode_config:
            QMessageBox.critical(self, "配置错误", "请输入有效的文件夹路径并选择转换模式。")
            return
            
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError as e:
                QMessageBox.critical(self, "系统错误", f"无法创建输出目录: {e}")
                return

        # 检查文件
        try:
            self.status_label.setText("正在扫描文件...")
            QApplication.processEvents() # 刷新界面
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

        # UI 状态更新
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

        # 线程启动
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
        
        # 在状态栏显示当前文件名，截断过长的名字
        display_name = (file_name[:40] + '..') if len(file_name) > 40 else file_name
        self.status_label.setText(f"正在处理: {display_name}")

    @Slot(int, int, str)
    def updateOverallProgress(self, current: int, total: int, status: str):
        if total > 0:
            overall_progress = (current / total) * 100.0
            self.overall_progress_bar.setValue(int(overall_progress))
            self.overall_progress_text.setText(f"{current}/{total}")
        
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
            self.status_label.setText("所有任务已完成。")
            QMessageBox.information(self, "完成", "所有文件转换成功完成!")
        elif self.last_stop_requested:
            self.status_label.setText("任务已由用户手动停止。")
            QMessageBox.information(self, "已中断", "转换操作已停止。")
        else:
            self.status_label.setText("转换过程中遇到错误。")
            # 显示更详细的错误信息到用户，方便诊断（如果有长堆栈则只显示首行摘要并记录完整堆栈到日志）
            if error_msg:
                # 取首条异常消息作为摘要
                first_line = error_msg.strip().splitlines()[0]
                # 如果是资源缺失（如字体），给出更友好的提示
                if "not found" in first_line.lower() or "未找到" in first_line:
                    QMessageBox.critical(self, "错误", f"资源未找到：{first_line}\n请检查 assets/ 目录并确保字体/资源存在。")
                else:
                    QMessageBox.critical(self, "错误", f"转换失败: {first_line}\n详情请查看日志。")
            else:
                QMessageBox.critical(self, "错误", "转换失败，请查看日志获取详情。")