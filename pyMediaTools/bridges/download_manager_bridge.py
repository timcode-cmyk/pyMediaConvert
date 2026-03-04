import os
import json
from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer

from ..core.downloadmanager import DownloadManager
from ..utils import get_default_download_dir
from ..logging_config import get_logger

logger = get_logger(__name__)

class DownloadManagerBridge(QObject):
    # Signals
    tasksUpdated = Signal(str) # JSON string of tasks
    totalProgressChanged = Signal()
    totalSpeedChanged = Signal()
    downloadPathChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = DownloadManager()
        self._download_path = str(get_default_download_dir())
        self._total_progress = 0
        self._total_speed_str = "0 KB/s"
        
        # Start a timer to poll aria2c status
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(1000)

    # --- Properties ---
    @Property(str, notify=downloadPathChanged)
    def downloadPath(self):
        return self._download_path

    @Property(int, notify=totalProgressChanged)
    def totalProgress(self):
        return self._total_progress

    @Property(str, notify=totalSpeedChanged)
    def totalSpeed(self):
        return self._total_speed_str

    # --- Slots ---
    @Slot(str)
    def setDownloadPath(self, path):
        if path:
            self._download_path = path
            self.downloadPathChanged.emit()

    @Slot(int)
    def setConcurrentLimit(self, limit):
        self.manager.change_global_option(limit)

    @Slot(str, bool, result=bool)
    def addNewTask(self, url, use_acceleration):
        url = url.strip()
        if not url:
            return False
        gid = self.manager.add_download(url, self._download_path, use_acceleration)
        return gid is not None

    @Slot(str)
    def pauseTask(self, gid):
        self.manager.pause_task(gid)

    @Slot(str)
    def unpauseTask(self, gid):
        self.manager.unpause_task(gid)

    @Slot(str)
    def removeTask(self, gid):
        self.manager.remove_task(gid)

    @Slot()
    def pauseAll(self):
        self.manager._call_rpc("pauseAll")

    @Slot()
    def unpauseAll(self):
        self.manager._call_rpc("unpauseAll")

    @Slot()
    def purgeDownloadResult(self):
        self.manager._call_rpc("purgeDownloadResult")

    # --- Internal Methods ---
    def _refresh_status(self):
        tasks = self.manager.get_status_all()
        
        if not tasks:
            self._total_progress = 0
            self._total_speed_str = "0 KB/s"
            self.totalProgressChanged.emit()
            self.totalSpeedChanged.emit()
            self.tasksUpdated.emit("[]")
            return

        total_bytes = 0
        completed_bytes = 0
        total_speed = 0

        formatted_tasks = []

        for task in tasks:
            gid = task.get('gid', '')
            status = task.get('status', '')
            
            # Extract filename
            files = task.get('files', [])
            name = "正在解析..."
            if files and files[0].get('path'):
                name = os.path.basename(files[0]['path'])
            elif files and files[0].get('uris'):
                uri = files[0]['uris'][0].get('uri', '')
                name = uri.split('/')[-1].split('?')[0] or "未知任务"
            
            # Extract progression
            try:
                t_len = int(task.get('totalLength', 0))
                c_len = int(task.get('completedLength', 0))
                speed = int(task.get('downloadSpeed', 0))
            except (ValueError, TypeError):
                t_len, c_len, speed = 0, 0, 0
            
            total_bytes += t_len
            completed_bytes += c_len
            total_speed += speed

            progress_pct = int(c_len / t_len * 100) if t_len > 0 else 0
            size_str = f"{t_len/1024/1024:.2f} MB"
            speed_str = f"{speed/1024:.1f} KB/s"

            formatted_tasks.append({
                "gid": gid,
                "name": name,
                "progress": progress_pct,
                "size": size_str,
                "speed": speed_str,
                "status": status
            })

        # Update totals
        if total_bytes > 0:
            self._total_progress = int(completed_bytes / total_bytes * 100)
        else:
            self._total_progress = 0
            
        if total_speed > 1024 * 1024:
            self._total_speed_str = f"{total_speed/1024/1024:.2f} MB/s"
        else:
            self._total_speed_str = f"{total_speed/1024:.1f} KB/s"

        self.totalProgressChanged.emit()
        self.totalSpeedChanged.emit()
        self.tasksUpdated.emit(json.dumps(formatted_tasks))

    def cleanup(self):
        self._timer.stop()
        self.manager.stop_server()
