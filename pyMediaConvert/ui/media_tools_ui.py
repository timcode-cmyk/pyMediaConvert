import os
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar, QMessageBox, QFileDialog, QSizePolicy, QGroupBox)
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QFont

from pyMediaConvert.config import MODES
from pyMediaConvert import worker as pm_worker
from pyMediaConvert.utils import get_ffmpeg_exe, get_ffprobe_exe


class DropLineEdit(QLineEdit):
    pathDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)

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
    finished = Signal(bool)

    def __init__(self, input_dir, output_dir, mode_config, monitor, parent=None):
        super().__init__(parent)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.mode_config = mode_config
        self.monitor = monitor

    @Slot()
    def run(self):
        is_successful = False
        try:
            pm_worker.GlobalProgressMonitor = self.monitor
            ConverterClass = self.mode_config['class']
            converter = ConverterClass(
                params=self.mode_config.get('params', {}),
                support_exts=self.mode_config.get('support_exts'),
                output_ext=self.mode_config.get('output_ext')
            )
            converter.run(Path(self.input_dir), Path(self.output_dir))
            is_successful = not self.monitor.check_stop_flag()
        except Exception as e:
            print(f"致命错误: Worker 线程中发生未捕获的异常: {e}")
            is_successful = False
        finally:
            pm_worker.GlobalProgressMonitor = None
            self.finished.emit(is_successful)


class MediaConverterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker_thread = None
        self.conversion_monitor = None
        self.is_converting = False
        self.last_total_files = 0
        self.last_stop_requested = False
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        title = QLabel("<h1>媒体转换器</h1>")
        title.setFont(QFont("Arial", 18))
        main_layout.addWidget(title)

        mode_group = QGroupBox("转换模式设置")
        mode_layout = QFormLayout(mode_group)
        self.mode_combo = QComboBox()
        self.mode_combo.currentIndexChanged.connect(self.updateModeDescription)
        self.desc_label = QLabel("模式说明: 请选择一个转换模式。")
        self.desc_label.setWordWrap(True)
        mode_layout.addRow("选择模式:", self.mode_combo)
        mode_layout.addRow("模式说明:", self.desc_label)
        main_layout.addWidget(mode_group)

        path_group = QGroupBox("路径设置")
        path_layout = QFormLayout(path_group)
        self.input_path_edit = DropLineEdit()
        self.input_path_edit.setPlaceholderText("拖放文件夹或文件到此处，或点击按钮选择...")
        self.input_path_edit.pathDropped.connect(self.updateOutputPath)
        self.input_path_edit.textChanged.connect(self.updateOutputPath)
        input_btn = QPushButton("选择输入路径")
        input_btn.clicked.connect(self.selectInputPath)
        input_h_layout = QHBoxLayout()
        input_h_layout.addWidget(self.input_path_edit)
        input_h_layout.addWidget(input_btn)
        path_layout.addRow("输入路径:", input_h_layout)
        self.output_path_edit = QLineEdit()
        output_btn = QPushButton("选择输出目录")
        output_btn.clicked.connect(self.selectOutputDirectory)
        output_h_layout = QHBoxLayout()
        output_h_layout.addWidget(self.output_path_edit)
        output_h_layout.addWidget(output_btn)
        path_layout.addRow("输出目录:", output_h_layout)
        main_layout.addWidget(path_group)

        self.start_stop_button = QPushButton("🚀 开始转换")
        self.start_stop_button.clicked.connect(self.toggleConversion)
        main_layout.addWidget(self.start_stop_button)

        progress_group = QGroupBox("转换状态和进度")
        progress_layout = QVBoxLayout(progress_group)
        self.status_label = QLabel("等待配置...")
        self.status_label.setWordWrap(True)
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(QLabel("总进度:"))
        self.overall_progress_text = QLabel("0/0 文件 (0.0%)")
        progress_layout.addWidget(self.overall_progress_text)
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.overall_progress_bar)
        progress_layout.addWidget(QLabel("当前文件进度:"))
        self.file_progress_text = QLabel("正在等待...")
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.file_progress_bar)
        progress_layout.addWidget(self.file_progress_text)
        main_layout.addWidget(progress_group)

        self.loadModes()

    def loadModes(self):
        if not MODES:
            self.mode_combo.addItem("ERROR: Config file not loaded.", None)
            return
        for key, config in MODES.items():
            display_text = f"[{key}] - {config['description']}"
            self.mode_combo.addItem(display_text, key)
        self.updateModeDescription()

    def updateModeDescription(self):
        mode_key = self.mode_combo.currentData()
        if mode_key and mode_key in MODES:
            desc = MODES[mode_key]['description']
            support_exts = MODES[mode_key].get('support_exts')
            exts = ", ".join(support_exts) if support_exts else "由 Worker 默认"
            self.desc_label.setText(f"模式说明: {desc}\n支持的扩展名: {exts}")
        else:
            self.desc_label.setText("模式说明: 未知模式或配置未加载。")

    def selectInputPath(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择输入文件 (将使用其目录) 或选择目录", "", "All Files (*);;Videos (*.mp4 *.mkv *.mov)")
        if not path:
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
            QMessageBox.critical(self, "错误", "请设置有效的输入目录和转换模式。")
            return
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError as e:
                QMessageBox.critical(self, "错误", f"无法创建输出目录: {e}")
                return
        try:
            temp_worker = mode_config['class'](params=mode_config['params'], init_checks=False)
            temp_worker.find_files(Path(input_dir))
            files_to_process_count = len(temp_worker.files)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"文件检查失败: {e}")
            return
        if files_to_process_count == 0:
            QMessageBox.critical(self, "错误", f"在目录 {input_dir} 中未找到支持的文件。")
            return
        self.last_total_files = files_to_process_count
        self.last_stop_requested = False
        self.is_converting = True
        self.start_stop_button.setText(f"🛑 停止转换 (处理中: {files_to_process_count} 文件)")
        self.start_stop_button.setEnabled(True)
        self.overall_progress_bar.setValue(0)
        self.file_progress_bar.setValue(0)
        self.overall_progress_text.setText(f"0/{self.last_total_files} 文件 (0.0%)")
        self.file_progress_text.setText(f"当前文件: 准备开始...")
        self.status_label.setText(f"开始处理 {self.last_total_files} 个文件...")
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
            self.status_label.setText("正在发送停止请求... FFMPEG 进程正在终止，请稍候。")
            self.start_stop_button.setEnabled(False)

    @Slot(float, float, str)
    def updateFileProgress(self, seconds: float, duration: float, file_name: str):
        if duration > 0:
            file_progress = min(100.0, (seconds / duration) * 100.0)
            self.file_progress_bar.setValue(int(file_progress))
            self.file_progress_text.setText(f"🎬 {file_name}: 正在处理 ({file_progress:.1f}%)")
        else:
            self.file_progress_bar.setValue(0)
            self.file_progress_text.setText(f"🎬 {file_name}: 无法获取时长，进度未知...")

    @Slot(int, int, str)
    def updateOverallProgress(self, current: int, total: int, status: str):
        if total > 0:
            overall_progress = (current / total) * 100.0
            self.overall_progress_bar.setValue(int(overall_progress))
            self.overall_progress_text.setText(f"{current}/{total} 文件 ({overall_progress:.1f}%)")
        else:
            self.overall_progress_bar.setValue(0)
            self.overall_progress_text.setText("0/0 文件 (0.0%)")
        self.status_label.setText(status)
        if self.is_converting:
            self.start_stop_button.setText(f"🛑 停止转换 (已完成: {current}/{total})")

    @Slot(bool)
    def conversionFinished(self, is_successful):
        self.is_converting = False
        self.start_stop_button.setEnabled(True)
        self.start_stop_button.setText("🚀 开始转换")
        if is_successful:
            self.overall_progress_bar.setValue(100)
            self.file_progress_bar.setValue(100)
            self.overall_progress_text.setText(f"{self.last_total_files}/{self.last_total_files} 文件 (100.0%)")
            self.file_progress_text.setText("当前文件: 已完成")
            QMessageBox.information(self, "转换完成", "所有文件转换成功完成!")
        elif self.last_stop_requested:
            self.status_label.setText("已停止。请点击 '开始转换' 重新开始。")
            QMessageBox.information(self, "已中断", "转换已被用户停止。")
        else:
            self.status_label.setText("转换失败，请检查控制台输出。")
            QMessageBox.critical(self, "错误", "转换过程中发生错误。详情请查看控制台。")
