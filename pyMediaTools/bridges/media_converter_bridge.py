import os
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, Slot, Property

from pyMediaTools.core.config import MODES
from pyMediaTools import get_logger

logger = get_logger(__name__)

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
            logger.exception(f"Worker exception: {e}")
            is_successful = False
        finally:
            self.finished.emit(is_successful, error_msg)


class MediaConverterBridge(QObject):
    # Signals for QML to update UI
    isConvertingChanged = Signal()
    statusTextChanged = Signal()
    fileProgressChanged = Signal()
    fileProgressTextChanged = Signal()
    overallProgressChanged = Signal()
    overallProgressTextChanged = Signal()
    
    # Notify QML about completion or error
    conversionFinished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker_thread = None
        self.conversion_monitor = None
        self.worker = None
        
        self._is_converting = False
        self._status_text = "等待开始..."
        self._file_progress = 0
        self._file_progress_text = ""
        self._overall_progress = 0
        self._overall_progress_text = "0/0 (0%)"
        
        self.last_total_files = 0
        self.last_stop_requested = False

    # --- Properties ---
    
    @Property(bool, notify=isConvertingChanged)
    def isConverting(self):
        return self._is_converting

    @Property(str, notify=statusTextChanged)
    def statusText(self):
        return self._status_text

    @Property(int, notify=fileProgressChanged)
    def fileProgress(self):
        return self._file_progress

    @Property(str, notify=fileProgressTextChanged)
    def fileProgressText(self):
        return self._file_progress_text

    @Property(int, notify=overallProgressChanged)
    def overallProgress(self):
        return self._overall_progress

    @Property(str, notify=overallProgressTextChanged)
    def overallProgressText(self):
        return self._overall_progress_text

    @Slot(result='QVariantList')
    def getModes(self):
        """Returns a list of dictionaries with mode details for the QML ComboBox/ListView."""
        if not MODES:
            return [{"key": "error", "label": "ERROR: Config file not loaded.", "desc": "", "exts": ""}]
        
        result = []
        for key, config in MODES.items():
            desc = config.get('description', '')
            exts_list = config.get('support_exts', [])
            exts = ", ".join(exts_list) if exts_list else "自动检测"
            
            result.append({
                "key": key,
                "label": f"{desc} [{key}]",
                "desc": desc,
                "exts": exts
            })
        return result

    # --- Slots ---

    @Slot(str, result=str)
    def getDefaultOutput(self, input_path):
        input_path = str(input_path).replace('file://', '').strip()
        if input_path and os.path.exists(input_path):
            input_dir = os.path.dirname(input_path) if os.path.isfile(input_path) else input_path
            return os.path.join(input_dir, "CONVERTED_OUTPUT")
        return ""

    @Slot(str, str, str)
    def startConversion(self, input_path, output_path, mode_key):
        input_dir = str(input_path).replace('file://', '').strip()
        output_dir = str(output_path).replace('file://', '').strip()
        
        mode_config = MODES.get(mode_key)
        if not (os.path.isdir(input_dir) or os.path.isfile(input_dir)) or not mode_config:
            self.conversionFinished.emit(False, "配置错误: 请输入有效的文件或文件夹路径并选择转换模式。")
            return
            
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError as e:
                self.conversionFinished.emit(False, f"系统错误: 无法创建输出目录 {e}")
                return

        try:
            self._set_status_text("正在扫描文件...")
            temp_worker = mode_config['class'](
                params=mode_config.get('params', {}), 
                support_exts=mode_config.get('support_exts'), 
                init_checks=False
            )
            temp_worker.find_files(Path(input_dir))
            files_to_process_count = len(temp_worker.files)
        except Exception as e:
            logger.exception(f"文件扫描失败: {e}")
            self.conversionFinished.emit(False, f"文件扫描失败: {e}")
            return

        if files_to_process_count == 0:
            exts = mode_config.get('support_exts')
            self.conversionFinished.emit(False, f"无文件: 在目录中未找到支持的文件类型。\n支持类型: {exts}")
            return

        # Setup state
        self.last_total_files = files_to_process_count
        self.last_stop_requested = False
        self._set_is_converting(True)
        
        self._set_overall_progress(0)
        self._set_file_progress(0)
        self._set_overall_progress_text(f"0/{self.last_total_files} (0%)")
        self._set_file_progress_text("准备中...")
        self._set_status_text(f"正在初始化 Worker，共 {self.last_total_files} 个文件...")

        # Start Thread
        self.worker_thread = QThread()
        self.conversion_monitor = ProgressMonitor()
        self.worker = ConversionWorker(input_dir, output_dir, mode_config, self.conversion_monitor)
        
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_worker_finished)
        self.conversion_monitor.file_progress.connect(self._update_file_progress)
        self.conversion_monitor.overall_progress.connect(self._update_overall_progress)
        
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        
        self.worker_thread.start()

    @Slot()
    def stopConversion(self):
        if self.worker_thread and self.worker_thread.isRunning() and self.conversion_monitor:
            self.last_stop_requested = True
            self.conversion_monitor.request_stop()
            self._set_status_text("正在请求停止... FFMPEG 进程可能需要几秒钟才能释放。")

    # --- Internal Slots & Helpers ---

    @Slot(float, float, str)
    def _update_file_progress(self, seconds: float, duration: float, file_name: str):
        if duration > 0:
            file_progress = min(100.0, (seconds / duration) * 100.0)
            self._set_file_progress(int(file_progress))
            self._set_file_progress_text(f"{file_progress:.1f}%")
        else:
            self._set_file_progress(0)
            self._set_file_progress_text("计算中...")
        
        display_name = (file_name[:40] + '..') if len(file_name) > 40 else file_name
        self._set_status_text(f"正在处理: {display_name}")

    @Slot(int, int, str)
    def _update_overall_progress(self, current: int, total: int, status: str):
        if total > 0:
            pct = int((current / total) * 100.0)
            if current >= total:
                pct = 100
            self._set_overall_progress(pct)
            self._set_overall_progress_text(f"{current}/{total} ({pct}%)")
        
        if not self._is_converting:
            self._set_status_text(status)

    @Slot(bool, str)
    def _on_worker_finished(self, is_successful, error_msg):
        self._set_is_converting(False)
        
        if is_successful:
            self._set_overall_progress(100)
            self._set_file_progress(100)
            self._set_overall_progress_text(f"{self.last_total_files}/{self.last_total_files} (100%)")
            self._set_file_progress_text("100%")
            self._set_status_text("所有任务已完成。")
            self.conversionFinished.emit(True, "所有文件转换成功完成!")
        elif self.last_stop_requested:
            self._set_status_text("任务已由用户手动停止。")
            self.conversionFinished.emit(True, "转换操作已停止。")
        else:
            self._set_status_text("转换过程中遇到错误。")
            self.conversionFinished.emit(False, error_msg)

    # State Setters
    def _set_is_converting(self, val):
        if self._is_converting != val:
            self._is_converting = val
            self.isConvertingChanged.emit()

    def _set_status_text(self, val):
        if self._status_text != val:
            self._status_text = val
            self.statusTextChanged.emit()

    def _set_file_progress(self, val):
        if self._file_progress != val:
            self._file_progress = val
            self.fileProgressChanged.emit()

    def _set_file_progress_text(self, val):
        if self._file_progress_text != val:
            self._file_progress_text = val
            self.fileProgressTextChanged.emit()

    def _set_overall_progress(self, val):
        if self._overall_progress != val:
            self._overall_progress = val
            self.overallProgressChanged.emit()

    def _set_overall_progress_text(self, val):
        if self._overall_progress_text != val:
            self._overall_progress_text = val
            self.overallProgressTextChanged.emit()
