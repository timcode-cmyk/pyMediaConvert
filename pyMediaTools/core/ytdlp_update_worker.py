"""
yt-dlp 异步更新Worker (QThread)
"""

import logging
from PySide6.QtCore import QThread, Signal
from .ytdlp_updater import YtDlpUpdater, YtDlpVersionManager

logger = logging.getLogger(__name__)


class YtDlpCheckUpdateWorker(QThread):
    """版本检查Worker"""
    
    # Signals
    version_checked = Signal(dict)  # {'local': str, 'remote': str, 'has_update': bool}
    error = Signal(str)
    
    def __init__(self, yt_dlp_dir: str = None, timeout: int = 10):
        super().__init__()
        self.manager = YtDlpVersionManager(yt_dlp_dir)
        self.timeout = timeout
    
    def run(self):
        """执行版本检查"""
        try:
            has_update, local_version, remote_version = self.manager.check_update_available(self.timeout)
            
            self.version_checked.emit({
                'has_update': has_update,
                'local_version': local_version,
                'remote_version': remote_version,
                'error': None
            })
            
        except Exception as e:
            logger.error(f"检查更新出错: {e}")
            self.error.emit(f"检查更新失败: {str(e)}")


class YtDlpUpdateWorker(QThread):
    """yt-dlp 更新Worker"""
    
    # Signals
    progress = Signal(str)          # 进度消息
    finished = Signal(dict)         # {'success': bool, 'message': str, 'new_version': str}
    error = Signal(str)
    
    def __init__(self, 
                 yt_dlp_dir: str = None,
                 update_method: str = 'github'):
        """
        初始化更新Worker
        
        Args:
            yt_dlp_dir: yt-dlp目录路径
            update_method: 更新方式 ('github' 或 'pypi')
        """
        super().__init__()
        self.updater = YtDlpUpdater(yt_dlp_dir)
        self.update_method = update_method.lower()
        self._is_running = True
    
    def run(self):
        """执行更新"""
        try:
            if not self._is_running:
                return
            
            self.progress.emit("正在检查本地版本...")
            local_version = self.updater.get_local_version()
            self.progress.emit(f"本地版本: {local_version}")
            
            if not self._is_running:
                return
            
            # 执行备份
            self.progress.emit("正在备份当前版本...")
            backup_path = self.updater.backup_current()
            if backup_path:
                self.progress.emit(f"备份成功: {backup_path}")
            else:
                raise Exception("备份失败，中止更新")
            
            if not self._is_running:
                return
            
            # 执行更新
            if self.update_method == 'pypi':
                self.progress.emit("正在通过PyPI获取最新版本...")
                success, message = self.updater.update_from_pypi()
            else:
                self.progress.emit("正在从GitHub获取最新版本...")
                success, message = self.updater.update_from_github()
            
            if success:
                new_version = self.updater.get_local_version()
                self.progress.emit(f"更新成功！新版本: {new_version}")
                
                self.finished.emit({
                    'success': True,
                    'message': message,
                    'new_version': new_version,
                    'old_version': local_version
                })
            else:
                self.progress.emit(f"更新失败: {message}")
                
                self.finished.emit({
                    'success': False,
                    'message': message,
                    'new_version': None,
                    'old_version': local_version
                })
            
        except Exception as e:
            logger.error(f"更新异常: {e}")
            self.error.emit(f"更新失败: {str(e)}")
    
    def stop(self):
        """停止更新"""
        self._is_running = False


class YtDlpRollbackWorker(QThread):
    """yt-dlp 回滚Worker"""
    
    # Signals
    progress = Signal(str)          # 进度消息
    finished = Signal(dict)         # {'success': bool, 'message': str}
    error = Signal(str)
    
    def __init__(self, yt_dlp_dir: str = None, backup_path: str = None):
        """
        初始化回滚Worker
        
        Args:
            yt_dlp_dir: yt-dlp目录路径
            backup_path: 备份路径，若为None则回滚到最新备份
        """
        super().__init__()
        self.updater = YtDlpUpdater(yt_dlp_dir)
        self.backup_path = backup_path
    
    def run(self):
        """执行回滚"""
        try:
            self.progress.emit("正在回滚...")
            
            if self.backup_path:
                self.progress.emit(f"回滚到: {self.backup_path}")
            else:
                self.progress.emit("回滚到最新备份...")
            
            success = self.updater.rollback(self.backup_path)
            
            if success:
                rolled_back_version = self.updater.get_local_version()
                message = f"回滚成功，版本: {rolled_back_version}"
                self.progress.emit(message)
                
                self.finished.emit({
                    'success': True,
                    'message': message,
                    'version': rolled_back_version
                })
            else:
                self.finished.emit({
                    'success': False,
                    'message': "回滚失败"
                })
            
        except Exception as e:
            logger.error(f"回滚异常: {e}")
            self.error.emit(f"回滚失败: {str(e)}")


# 导出公共接口
__all__ = [
    'YtDlpCheckUpdateWorker',
    'YtDlpUpdateWorker',
    'YtDlpRollbackWorker',
]
