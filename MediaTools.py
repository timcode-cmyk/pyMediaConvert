import sys
import os
from pathlib import Path
from PySide6.QtWidgets import ( # <-- 更改为 PySide6
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QProgressBar, QMessageBox, QFileDialog, QSizePolicy, QGroupBox
)
from PySide6.QtCore import ( # <-- 更改为 PySide6
    QObject, QThread, Signal, Slot, Qt # <-- pyqtSignal/pyqtSlot 更改为 Signal/Slot
)
from PySide6.QtGui import QPalette, QColor, QFont, QGuiApplication # <-- 更改为 PySide6

# --- 1. Import Config and Worker Classes ---
try:
    # 假设这些文件已存在且适用于 PySide6 环境
    from pyMediaConvert.config import MODES
    from pyMediaConvert import worker
    from pyMediaConvert.utils import get_ffmpeg_exe, get_ffprobe_exe
except ImportError as e:
    MODES = {}
    print(f"FATAL: 无法导入依赖文件 (config.py/worker.py/utils.py)。错误: {e}", file=sys.stderr)


# --- 2. 自定义 QLineEdit 以支持拖放 (Drag-and-Drop) ---
class DropLineEdit(QLineEdit):
    """一个支持拖放文件/文件夹路径的 QLineEdit。"""
    pathDropped = Signal(str) # <-- 更改为 Signal

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        """接受文件/文件夹的拖入操作。"""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """处理文件/文件夹的放下操作。"""
        if event.mimeData().hasUrls():
            local_path = event.mimeData().urls()[0].toLocalFile()
            
            if os.path.isdir(local_path):
                self.setText(local_path)
                self.pathDropped.emit(local_path)
                event.accept()
            else:
                 # 如果是文件，获取其所在目录
                 directory = os.path.dirname(local_path)
                 self.setText(directory)
                 self.pathDropped.emit(directory)
                 event.accept()
        else:
            super().dropEvent(event)


# --- 3. 进度监控器 (信号发射器) ---
class ProgressMonitor(QObject):
    """
    作为 worker.py 和 GUI 线程之间的信号桥梁。
    """
    file_progress = Signal(float, float, str) # <-- 更改为 Signal
    overall_progress = Signal(int, int, str) # <-- 更改为 Signal
    
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


# --- 4. 转换工作线程 (Worker Thread) ---
class ConversionWorker(QObject):
    """在单独的线程中执行 worker.MediaConverter.run() 方法。"""
    finished = Signal(bool) # <-- 更改为 Signal

    def __init__(self, input_dir, output_dir, mode_config, monitor, parent=None):
        super().__init__(parent)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.mode_config = mode_config
        self.monitor = monitor

    @Slot() # <-- 更改为 Slot
    def run(self):
        """主循环：实例化真实的转换器并运行批处理."""
        is_successful = False
        try:
            # 假设 worker 模块已正确配置 GlobalProgressMonitor
            worker.GlobalProgressMonitor = self.monitor
            ConverterClass = self.mode_config['class']
            
            converter = ConverterClass(
                params=self.mode_config['params'],
                support_exts=self.mode_config.get('support_exts'),
                output_ext=self.mode_config.get('output_ext')
            )
            
            # 在 run() 中调用 find_files 或在外部调用并传递文件列表，取决于 worker 的实现
            # 如果 worker.run() 内部处理 find_files，则此处不需要调用。
            # 为了兼容原代码的结构，此处假设 find_files 在 run 外部的 startConversion 中被调用过
            # 但是，worker.run() 可能需要访问文件列表，为了安全，这里假设 run 方法会处理文件查找或接收文件列表。
            # 由于原 ConversionWorker.run() 仅调用了 converter.run()，我们保持这种结构。
            
            converter.run(Path(self.input_dir), Path(self.output_dir))
            
            is_successful = not self.monitor.check_stop_flag()
            
        except Exception as e:
            print(f"致命错误: Worker 线程中发生未捕获的异常: {e}", file=sys.stderr)
            is_successful = False
        finally:
            worker.GlobalProgressMonitor = None
            self.finished.emit(is_successful)


# --- 5. 主应用程序窗口 (GUI) ---
class MediaConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("媒体转换工具") # 更改标题
        self.setGeometry(100, 100, 800, 700)
        
        # 线程和状态管理
        self.worker_thread = None
        self.conversion_monitor = None
        self.is_converting = False
        self.last_total_files = 0
        self.last_stop_requested = False

        self.initUI()
        self.loadModes()
        self.applyStyles() 
        self.checkFFmpeg()

    def applyStyles(self):
        """
        应用结构和通用的 QSS 样式。
        """
        # 强制更新调色板以确保获取到当前系统主题的颜色
        QApplication.setPalette(QGuiApplication.palette())
        # QPalette.ColorRole.Highlight 在 PySide6 中同样兼容
        progress_bar_chunk_color = QApplication.palette().color(QPalette.ColorRole.Highlight).name()

        style = f"""
            /* 结构样式 - 遵循系统主题 */
            QGroupBox {{
                margin-top: 10px;
                padding: 15px;
                border: 1px solid palette(midlight); /* 遵循系统颜色 */
                border-radius: 8px;
            }}
            /* 修复输入框边距问题 */
            QFormLayout, QHBoxLayout {{
                margin: 0;
                padding: 0;
            }}
            /* 输入框样式 */
            QLineEdit {{
                padding: 8px;
                border: 1px solid palette(mid); 
                border-radius: 4px;
                font-size: 14px;
                /* 确保输入框背景和文本颜色也遵循系统主题 */
                background: palette(base);
                color: palette(text);
            }}
            /* 按钮基本样式 */
            QPushButton {{
                padding: 8px 15px;
                font-size: 14px;
                border-radius: 4px;
                font-weight: 500;
            }}
            /* 进度条样式 (确保进度条可见) */
            QProgressBar {{
                border: 1px solid palette(midlight);
                border-radius: 5px;
                text-align: center;
                background: palette(alternate-base);
                color: palette(text); /* 文本颜色跟随主题 */
            }}
            QProgressBar::chunk {{
                background-color: {progress_bar_chunk_color}; 
                border-radius: 5px;
            }}
            /* 状态标签 */
            QLabel {{
                padding: 5px 0;
            }}
            /* 启动/停止按钮特殊样式 */
            #StartStopButton {{ 
                padding: 12px; 
                font-size: 18px; 
                font-weight: bold; 
                border-radius: 8px;
            }}
            #StartStopButton[converting="false"] {{
                background-color: #10b981; /* 绿色 */
                color: white;
            }}
            #StartStopButton[converting="true"] {{
                background-color: #ef4444; /* 红色 */
                color: white;
            }}
            #StartStopButton:hover {{ 
                opacity: 0.9;
            }}
            #StartStopButton:disabled {{
                opacity: 0.5;
            }}
        """
        self.setStyleSheet(style)

    def initUI(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(30, 30, 30, 30) 
        main_layout.setSpacing(20)
        
        # Title
        title = QLabel("<h1>媒体转换器</h1>")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold)) 
        main_layout.addWidget(title)
        
        # Mode Selection
        mode_group = QGroupBox("转换模式设置")
        mode_layout = QFormLayout(mode_group)
        mode_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        self.mode_combo = QComboBox()
        self.mode_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.mode_combo.currentIndexChanged.connect(self.updateModeDescription)
        
        self.desc_label = QLabel("模式说明: 请选择一个转换模式。")
        self.desc_label.setWordWrap(True)
        
        mode_layout.addRow("选择模式:", self.mode_combo)
        mode_layout.addRow("模式说明:", self.desc_label)
        
        main_layout.addWidget(mode_group)
        
        # Path Settings
        path_group = QGroupBox("路径设置")
        path_layout = QFormLayout(path_group)
        path_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        # Input Path (使用自定义的 DropLineEdit)
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
        
        # Output Directory
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("输出目录将自动填充")
        output_btn = QPushButton("选择输出目录")
        output_btn.clicked.connect(self.selectOutputDirectory)

        output_h_layout = QHBoxLayout()
        output_h_layout.addWidget(self.output_path_edit)
        output_h_layout.addWidget(output_btn)
        path_layout.addRow("输出目录:", output_h_layout)

        main_layout.addWidget(path_group)

        # Start/Stop Button
        self.start_stop_button = QPushButton("🚀 开始转换")
        self.start_stop_button.setObjectName("StartStopButton")
        self.start_stop_button.setProperty("converting", "false")
        self.start_stop_button.clicked.connect(self.toggleConversion)
        main_layout.addWidget(self.start_stop_button)

        # Status and Progress
        progress_group = QGroupBox("转换状态和进度")
        progress_layout = QVBoxLayout(progress_group)

        self.status_label = QLabel("等待配置...")
        self.status_label.setWordWrap(True)
        progress_layout.addWidget(self.status_label)
        
        # Overall Progress
        progress_layout.addWidget(QLabel("总进度:"))
        self.overall_progress_text = QLabel("0/0 文件 (0.0%)")
        progress_layout.addWidget(self.overall_progress_text)
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.overall_progress_bar)

        # File Progress
        progress_layout.addWidget(QLabel("当前文件进度:"))
        self.file_progress_text = QLabel("正在等待...")
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.file_progress_bar)
        progress_layout.addWidget(self.file_progress_text) 

        main_layout.addWidget(progress_group)
        main_layout.addStretch(1) 

        self.setCentralWidget(central_widget)

    def checkFFmpeg(self):
        """检查 FFMPEG 模拟路径以确保 worker.py 不会因 Path.exists() 失败。"""
        try:
            ffmpeg_path = Path(get_ffmpeg_exe())
            ffprobe_path = Path(get_ffprobe_exe())
            
            if not ffmpeg_path.exists() or not ffprobe_path.exists():
                 self.status_label.setText("⚠️ 警告: FFMPEG 或 FFPROBE 文件未找到。程序可能无法实际转换，但 GUI 正常工作。")
            else:
                 self.status_label.setText("✅ 准备就绪。请选择路径和模式。")
        except Exception as e:
            self.status_label.setText(f"❌ 错误: 检查 FFMPEG 路径失败: {e}")

    # --- UI Helpers ---
    def loadModes(self):
        if not MODES:
            self.mode_combo.addItem("ERROR: Config file not loaded.", None)
            return

        for key, config in MODES.items():
            # 兼容原代码的 description 字段
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
        # 允许选择单个文件（以获取其目录）或选择目录
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

    @Slot(str) # <-- 更改为 Slot
    def updateOutputPath(self, input_path: str):
        """根据输入的路径自动设置默认输出路径。"""
        input_path = input_path.strip()
        if input_path and os.path.exists(input_path):
            input_dir = os.path.dirname(input_path) if os.path.isfile(input_path) else input_path
            
            default_output = os.path.join(input_dir, "PROCESSED_OUTPUT")
            self.output_path_edit.setText(default_output)
        else:
            self.output_path_edit.setText("")

    # --- Conversion Control ---
    
    def toggleConversion(self):
        """根据当前状态，启动或停止转换。"""
        if self.is_converting:
            self.stopConversion()
        else:
            self.startConversion()

    def startConversion(self):
        """初始化并启动转换工作线程。"""
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
            # 检查文件数
            # 警告: 这里的实现依赖于 worker.MediaConverter 内部的 find_files 方法
            # 使用 init_checks=False 跳过耗时的 ffmpeg/ffprobe 检查（仅用于计数）
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
        
        # UI 更新为停止状态
        self.start_stop_button.setText(f"🛑 停止转换 (处理中: {files_to_process_count} 文件)")
        self.start_stop_button.setProperty("converting", "true")
        self.start_stop_button.style().polish(self.start_stop_button) # 强制应用 QSS
        
        # Reset progress bars
        self.overall_progress_bar.setValue(0)
        self.file_progress_bar.setValue(0)
        self.overall_progress_text.setText(f"0/{self.last_total_files} 文件 (0.0%)")
        self.file_progress_text.setText(f"当前文件: 准备开始...")
        self.status_label.setText(f"开始处理 {self.last_total_files} 个文件...")

        # 创建 Worker 和 Monitor
        self.worker_thread = QThread()
        self.conversion_monitor = ProgressMonitor()
        self.worker = ConversionWorker(input_dir, output_dir, mode_config, self.conversion_monitor)
        self.worker.moveToThread(self.worker_thread)

        # 连接信号
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.conversionFinished)
        
        self.conversion_monitor.file_progress.connect(self.updateFileProgress)
        self.conversion_monitor.overall_progress.connect(self.updateOverallProgress)
        
        # 清理连接
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    def stopConversion(self):
        """请求工作线程优雅地停止。"""
        if self.worker_thread and self.worker_thread.isRunning() and self.conversion_monitor:
            self.last_stop_requested = True
            self.conversion_monitor.request_stop()
            self.status_label.setText("正在发送停止请求... FFMPEG 进程正在终止，请稍候。")
            self.start_stop_button.setEnabled(False) # 禁用按钮直到线程真正停止

    @Slot(float, float, str) # <-- 更改为 Slot
    def updateFileProgress(self, seconds: float, duration: float, file_name: str):
        """由 Monitor 接收，更新单个文件进度条。"""
        if duration > 0:
            file_progress = min(100.0, (seconds / duration) * 100.0)
            self.file_progress_bar.setValue(int(file_progress))
            self.file_progress_text.setText(f"🎬 {file_name}: 正在处理 ({file_progress:.1f}%)")
        else:
             self.file_progress_bar.setValue(0)
             self.file_progress_text.setText(f"🎬 {file_name}: 无法获取时长，进度未知...")


    @Slot(int, int, str) # <-- 更改为 Slot
    def updateOverallProgress(self, current: int, total: int, status: str):
        """由 Monitor 接收，更新总进度条和状态。"""
        if total > 0:
            overall_progress = (current / total) * 100.0
            self.overall_progress_bar.setValue(int(overall_progress))
            self.overall_progress_text.setText(f"{current}/{total} 文件 ({overall_progress:.1f}%)")
        else:
            self.overall_progress_bar.setValue(0)
            self.overall_progress_text.setText("0/0 文件 (0.0%)")
            
        self.status_label.setText(status)
        
        # 实时更新停止按钮上的文件计数
        if self.is_converting:
             self.start_stop_button.setText(f"🛑 停止转换 (已完成: {current}/{total})")

    @Slot(bool) # <-- 更改为 Slot
    def conversionFinished(self, is_successful):
        """在转换线程结束后执行。"""
        self.is_converting = False
        self.start_stop_button.setEnabled(True)
        
        # 恢复初始按钮样式和属性
        self.start_stop_button.setText("🚀 开始转换")
        self.start_stop_button.setProperty("converting", "false")
        self.start_stop_button.style().polish(self.start_stop_button) # 强制应用 QSS
        
        if is_successful:
            self.overall_progress_bar.setValue(100)
            self.file_progress_bar.setValue(100)
            self.overall_progress_text.setText(f"{self.last_total_files}/{self.last_total_files} 文件 (100.0%)")
            self.file_progress_text.setText("当前文件: 已完成")
            QMessageBox.information(self, "转换完成", "所有文件转换成功完成!")
        elif self.last_stop_requested:
            self.status_label.setText("已停止。请点击 '开始转换' 重新开始。")
            self.overall_progress_bar.setValue(self.overall_progress_bar.value()) 
            QMessageBox.information(self, "已中断", "转换已被用户停止。")
        else:
            self.status_label.setText("转换失败，请检查控制台输出。")
            QMessageBox.critical(self, "错误", "转换过程中发生错误。详情请查看控制台。")


# --- 6. Application Entry ---
if __name__ == '__main__':

    app = QApplication(sys.argv)
    
    ex = MediaConverterApp()
    ex.show()
    # PySide6 和 PyQt6 都使用 app.exec()
    sys.exit(app.exec())