import os
import json
from PySide6.QtCore import QObject, Signal, Slot, Property, QSettings

from ..core.videodownloader import YtDlpInfoWorker, YtDlpDownloadWorker
from ..core.ytdlp_updater import YtDlpVersionManager
from ..core.ytdlp_update_worker import YtDlpCheckUpdateWorker, YtDlpUpdateWorker
from ..logging_config import get_logger

logger = get_logger(__name__)

class VideoDownloaderBridge(QObject):
    # Signals
    analyzeFinished = Signal(str) # JSON of list
    analyzeError = Signal(str)
    
    downloadProgress = Signal(str) # JSON of progress dict
    downloadFinished = Signal()
    downloadError = Signal(str)
    
    versionChecked = Signal(str, str, bool) # local, remote, has_update
    checkUpdateError = Signal(str)
    
    updateProgress = Signal(str)
    updateFinished = Signal(bool, str, str) # success, message, new_version
    updateError = Signal(str)
    
    localVersionChanged = Signal()
    remoteVersionChanged = Signal()
    defaultPathChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("pyMediaTools", "VideoDownloader")
        self.version_manager = YtDlpVersionManager()
        self._local_version = self.version_manager.get_local_version()
        self._remote_version = ""
        self._has_update = False
        
        self.info_worker = None
        self.download_worker = None
        self.check_update_worker = None
        self.update_worker = None
        
        self._default_path = self.settings.value("default_path", os.path.join(os.getcwd(), "Downloads"))

    # --- Properties ---
    @Property(str, notify=defaultPathChanged)
    def defaultPath(self):
        return self._default_path

    @Property(str, notify=localVersionChanged)
    def localVersion(self):
        return self._local_version

    @Property(str, notify=remoteVersionChanged)
    def remoteVersion(self):
        return self._remote_version

    # --- Slots ---
    @Slot(str)
    def setDefaultPath(self, path):
        if path and path != self._default_path:
            self._default_path = path
            self.settings.setValue("default_path", path)
            self.defaultPathChanged.emit()

    @Slot(str)
    def analyzeUrl(self, url):
        url = url.strip()
        if not url: return
        
        # Stop previous if any
        if self.info_worker and self.info_worker.isRunning():
            self.info_worker.terminate()
            
        self.info_worker = YtDlpInfoWorker(url)
        self.info_worker.finished.connect(self._on_info_loaded)
        self.info_worker.error.connect(self.analyzeError.emit)
        self.info_worker.start()

    def _on_info_loaded(self, info):
        entries = list(info.get('entries', [info]))
        # Clean up entries for JSON encoding
        safe_entries = []
        for e in entries:
            safe_entries.append({
                'title': e.get('title', 'Unknown'),
                'duration': e.get('duration', 0),
                'url': e.get('webpage_url') or e.get('url', ''),
            })
        self.analyzeFinished.emit(json.dumps(safe_entries))

    @Slot(str, str)
    def startDownload(self, items_json, options_json):
        """
        items_json: JSON string of list of objects [{"url": "...", "title": "...", "ui_index": 0}, ...]
        options_json: JSON string of object { "out_dir": "...", "audio_only": bool, "ext": "...", "quality": "...", "subtitles": bool, "sub_lang": "...", "concurrency": int }
        """
        try:
            items = json.loads(items_json)
            opts = json.loads(options_json)
        except Exception as e:
            self.downloadError.emit(str(e))
            return
            
        out_dir = opts.pop('out_dir', self._default_path)
        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                self.downloadError.emit(f"无法创建下载目录: {str(e)}")
                return
                
        if self.download_worker and self.download_worker.isRunning():
            self.downloadError.emit("当前已有下载任务正在进行")
            return

        self.download_worker = YtDlpDownloadWorker(items, opts, out_dir)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(self.downloadFinished.emit)
        self.download_worker.error.connect(self.downloadError.emit)
        self.download_worker.start()

    def _on_download_progress(self, data):
        self.downloadProgress.emit(json.dumps(data))

    @Slot()
    def stopDownload(self):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.stop()

    @Slot()
    def checkUpdate(self):
        if self.check_update_worker and self.check_update_worker.isRunning():
            return
            
        self.check_update_worker = YtDlpCheckUpdateWorker()
        self.check_update_worker.version_checked.connect(self._on_version_checked)
        self.check_update_worker.error.connect(self.checkUpdateError.emit)
        self.check_update_worker.start()

    def _on_version_checked(self, info):
        self._local_version = info.get('local_version', self._local_version)
        self._remote_version = info.get('remote_version', '')
        self._has_update = info.get('has_update', False)
        self.versionChecked.emit(self._local_version, self._remote_version, self._has_update)

    @Slot()
    def startUpdate(self):
        if self.download_worker and self.download_worker.isRunning():
            self.updateError.emit("下载中，无法同时更新yt-dlp")
            return
            
        if self.update_worker and self.update_worker.isRunning():
            return
            
        self.update_worker = YtDlpUpdateWorker(update_method='github')
        self.update_worker.progress.connect(self.updateProgress.emit)
        self.update_worker.finished.connect(self._on_update_finished)
        self.update_worker.error.connect(self.updateError.emit)
        self.update_worker.start()

    def _on_update_finished(self, info):
        success = info.get('success', False)
        message = info.get('message', '')
        new_version = info.get('new_version', '')
        
        if success:
            self._local_version = new_version
            
        self.updateFinished.emit(success, message, new_version)
