import os
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, Slot, Property

from ..core.vidoecut import SceneCutter, get_available_fonts
from ..ui.media_tools_ui import ProgressMonitor
from ..logging_config import get_logger

logger = get_logger(__name__)

class SceneCutWorker(QObject):
    finished = Signal(bool, str)

    def __init__(self, input_path, output_path, options, monitor, parent=None):
        super().__init__(parent)
        self.input_path = input_path
        self.output_path = output_path
        self.options = options
        self.monitor = monitor

    @Slot()
    def run(self):
        is_successful = False
        error_msg = ""
        try:
            # 从watermark_params中提取font_name用于初始化SceneCutter
            font_name = None
            if self.options.get('watermark_params'):
                font_name = self.options['watermark_params'].get('font_name')
            
            cutter = SceneCutter(monitor=self.monitor, font_name=font_name)
            cutter.run(Path(self.input_path), Path(self.output_path), **self.options)
            is_successful = not self.monitor.check_stop_flag()
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            logger.exception(f"SceneCutWorker 发生异常: {e}")
        finally:
            self.finished.emit(is_successful, error_msg)

class VideoCutBridge(QObject):
    # Signals for UI Updates
    overallProgressChanged = Signal()
    fileProgressChanged = Signal()
    statusTextChanged = Signal()
    isProcessingChanged = Signal()
    processingFinished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._overall_progress = 0
        self._overall_total = 100
        self._file_progress = 0
        self._file_total = 100
        self._status_text = "等待开始..."
        self._is_processing = False
        
        self.worker_thread = None
        self.monitor = None
        self.worker = None

    # --- Properties ---
    @Property(float, notify=overallProgressChanged)
    def overallProgress(self):
        return (self._overall_progress / self._overall_total * 100) if self._overall_total > 0 else 0

    @Property(float, notify=fileProgressChanged)
    def fileProgress(self):
        return (self._file_progress / self._file_total * 100) if self._file_total > 0 else 0

    @Property(str, notify=statusTextChanged)
    def statusText(self):
        return self._status_text

    @Property(bool, notify=isProcessingChanged)
    def isProcessing(self):
        return self._is_processing

    # --- Methods ---
    def set_status(self, text):
        self._status_text = text
        self.statusTextChanged.emit()

    def set_processing(self, processing):
        self._is_processing = processing
        self.isProcessingChanged.emit()

    @Slot(result=dict)
    def getInitialSettings(self):
        available_fonts = get_available_fonts()
        default_font = list(available_fonts.keys())[0] if available_fonts else "Roboto-Bold"
        return {
            "availableFonts": list(available_fonts.keys()),
            "defaultFont": default_font
        }

    @Slot(str, result=str)
    def generateOutputPath(self, input_path_str):
        if input_path_str and os.path.exists(input_path_str):
            p = Path(input_path_str)
            parent_dir = p.parent if p.is_file() else p
            return str(parent_dir / "SCENE_CUT_OUTPUT")
        return ""

    @Slot(dict)
    def startProcessing(self, params):
        """
        params = {
            'input_path': str,
            'output_path': str,
            'threshold': float,
            'export_frame': bool,
            'frame_offset': int,
            'add_watermark': bool,
            'watermark_text': str,
            'watermark_params': dict (from UI dialog),
            'person_id': str,
            'rename_lines': list[str]
        }
        """
        if self._is_processing:
            return

        input_path = params.get('input_path', '').strip()
        output_path = params.get('output_path', '').strip()

        if not input_path or not os.path.exists(input_path):
            self.processingFinished.emit(False, "请输入有效的输入路径。")
            return

        Path(output_path).mkdir(parents=True, exist_ok=True)

        options = {
            'threshold': params.get('threshold', 20) / 100.0,
            'export_frame': params.get('export_frame', True),
            'frame_offset': params.get('frame_offset', 10),
            'watermark_params': None,
            'person_id': params.get('person_id', '').strip(),
            'rename_lines': params.get('rename_lines', [])
        }

        if params.get('add_watermark', False):
            watermark_settings = params.get('watermark_params', {})
            watermark_settings['text'] = params.get('watermark_text', 'AI Created')
            
            # Verify font exists
            available_fonts = get_available_fonts()
            if watermark_settings.get('font_name') not in available_fonts:
                self.processingFinished.emit(False, f"字体 '{watermark_settings.get('font_name')}' 未找到。可用字体: {', '.join(available_fonts.keys())}")
                return
            
            options['watermark_params'] = watermark_settings

        self.set_processing(True)
        self.set_status("准备处理...")
        
        # Reset progress
        self._overall_progress = 0
        self._file_progress = 0
        self.overallProgressChanged.emit()
        self.fileProgressChanged.emit()

        self.monitor = ProgressMonitor()
        self.worker = SceneCutWorker(input_path, output_path, options, self.monitor)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_processing_finished)
        
        self.monitor.overall_progress.connect(self._update_overall_progress)
        self.monitor.file_progress.connect(self._update_file_progress)

        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    @Slot()
    def stopProcessing(self):
        if self.monitor and self._is_processing:
            self.monitor.request_stop()
            self.set_status("正在请求停止...")

    @Slot(int, int, str)
    def _update_overall_progress(self, current, total, status):
        self._overall_total = total
        self._overall_progress = min(current, total) if total > 0 else 0
        self.overallProgressChanged.emit()
        self.set_status(status)

    @Slot(float, float, str)
    def _update_file_progress(self, current, total, name):
        self._file_total = total
        self._file_progress = min(current, total) if total > 0 else 0
        self.fileProgressChanged.emit()

    @Slot(bool, str)
    def _on_processing_finished(self, success, error_msg):
        self.set_processing(False)

        if success:
            self._overall_progress = self._overall_total
            self._file_progress = self._file_total
            self.overallProgressChanged.emit()
            self.fileProgressChanged.emit()
            self.set_status("处理完成！")
            self.processingFinished.emit(True, "")
        elif self.monitor and self.monitor.check_stop_flag():
            self.set_status("用户已停止。")
            self.processingFinished.emit(False, "用户已停止")
        else:
            self.set_status("处理失败。")
            self.processingFinished.emit(False, error_msg)
