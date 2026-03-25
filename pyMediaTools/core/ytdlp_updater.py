"""
yt-dlp 版本管理和更新模块
功能：版本检测、比对、更新、回滚
"""

import os
import sys
import json
import glob
import logging
import shutil
import subprocess
import requests
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class VersionComparator:
    """版本号比较工具 (支持 YYYY.MM.DD 格式)"""
    
    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, int, int]:
        """解析版本号为元组 (year, month, day)"""
        try:
            parts = version_str.strip().split('.')
            if len(parts) >= 3:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            pass
        return (0, 0, 0)
    
    @staticmethod
    def is_newer(version_a: str, version_b: str) -> bool:
        """判断version_a是否比version_b更新"""
        a = VersionComparator.parse_version(version_a)
        b = VersionComparator.parse_version(version_b)
        return a > b
    
    @staticmethod
    def is_same(version_a: str, version_b: str) -> bool:
        """判断两个版本是否相同"""
        a = VersionComparator.parse_version(version_a)
        b = VersionComparator.parse_version(version_b)
        return a == b


class YtDlpVersionManager:
    """yt-dlp 版本管理器"""
    
    def __init__(self, yt_dlp_dir: str = None):
        """
        初始化版本管理器
        
        Args:
            yt_dlp_dir: yt-dlp源代码目录路径，默认为项目根目录下的yt_dlp
        """
        if yt_dlp_dir is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            yt_dlp_dir = str(project_root / "yt_dlp")
        
        self.yt_dlp_dir = yt_dlp_dir
        self.version_file = os.path.join(yt_dlp_dir, "version.py")
        self.backup_dir = os.path.join(os.path.dirname(yt_dlp_dir), ".yt_dlp_backups")
        self.metadata_file = os.path.join(self.backup_dir, "update_metadata.json")
        
        # 确保备份目录存在
        os.makedirs(self.backup_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _remove_path(self, path: str) -> bool:
        """Remove a file or directory.

        Handles both files and directories and logs any errors.
        Returns ``True`` if the path was removed or did not exist,
        ``False`` if an error occurred.
        """
        try:
            if not os.path.exists(path):
                logger.debug(f"_remove_path: path does not exist: {path}")
                return True

            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            logger.debug(f"_remove_path: removed {path}")
            return True
        except Exception as exc:
            logger.warning(f"_remove_path: failed to remove {path}: {exc}")
            return False
    
    def get_local_version(self) -> Optional[str]:
        """
        获取本地yt_dlp版本
        
        Returns:
            版本号字符串，如 "2026.02.04"，失败返回None
        """
        try:
            if not os.path.exists(self.version_file):
                logger.warning(f"版本文件不存在: {self.version_file}")
                return None
            
            with open(self.version_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 查找 __version__ = 'XXX'
            for line in content.split('\n'):
                if line.startswith('__version__'):
                    # 提取版本号
                    parts = line.split('=')
                    if len(parts) >= 2:
                        version = parts[1].strip().strip("'\"")
                        logger.debug(f"本地yt-dlp版本: {version}")
                        return version
            
            logger.warning("无法从version.py中提取版本号")
            return None
        except Exception as e:
            logger.error(f"获取本地版本失败: {e}")
            return None
    
    def get_remote_version_from_github(self, timeout: int = 10) -> Optional[str]:
        """
        从GitHub获取最新版本
        """
        try:
            url = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
            headers = {'User-Agent': 'Mozilla/5.0 (pyMediaTools)'}
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            
            # 提取版本号
            version = data.get('tag_name', '').lstrip('v')
            if not version:
                version = data.get('name', '').lstrip('v')
            
            if version:
                logger.debug(f"GitHub最新版本: {version}")
                return version
        except Exception as e:
            logger.warning(f"获取GitHub版本失败: {e}")
        return None
    
    def get_remote_version_from_pypi(self, timeout: int = 10) -> Optional[str]:
        """
        从PyPI获取最新版本
        """
        try:
            url = "https://pypi.org/pypi/yt-dlp/json"
            headers = {'User-Agent': 'Mozilla/5.0 (pyMediaTools)'}
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            version = data.get('info', {}).get('version')
            
            if version:
                logger.debug(f"PyPI最新版本: {version}")
                return version
        except Exception as e:
            logger.warning(f"获取PyPI版本失败: {e}")
        return None
    
    def get_remote_version(self, timeout: int = 10) -> Optional[str]:
        """
        获取远程最新版本 (优先GitHub，备选PyPI)
        
        Args:
            timeout: 请求超时时间（秒）
            
        Returns:
            最新版本号，失败返回None
        """
        # 优先尝试GitHub
        version = self.get_remote_version_from_github(timeout)
        if version:
            return version
        
        # 备选PyPI
        version = self.get_remote_version_from_pypi(timeout)
        if version:
            return version
        
        return None
    
    def check_update_available(self, timeout: int = 10) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        检查是否有更新可用
        
        Returns:
            (是否有更新, 本地版本, 远程版本)
        """
        try:
            local_version = self.get_local_version()
            if not local_version:
                return False, None, None
            
            remote_version = self.get_remote_version(timeout)
            if not remote_version:
                return False, local_version, None
            
            has_newer = VersionComparator.is_newer(remote_version, local_version)
            return has_newer, local_version, remote_version
            
        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            return False, None, None
    
    def backup_current(self) -> Optional[str]:
        """
        备份当前yt_dlp目录
        
        Returns:
            备份目录路径，失败返回None
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_version = self.get_local_version() or "unknown"
            backup_name = f"yt_dlp_backup_{current_version}_{timestamp}"
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # 如果yt_dlp目录存在，复制它
            if os.path.exists(self.yt_dlp_dir):
                shutil.copytree(self.yt_dlp_dir, backup_path)
                logger.info(f"备份成功: {backup_path}")
                
                # 记录备份元数据
                self._save_backup_metadata(backup_name, current_version)
                return backup_path
            else:
                logger.warning(f"yt_dlp目录不存在于: {self.yt_dlp_dir}")
                return None
                
        except Exception as e:
            logger.error(f"备份失败: {e}")
            return None
    
    def _save_backup_metadata(self, backup_name: str, version: str):
        """保存备份元数据"""
        try:
            metadata = {}
            if os.path.exists(self.metadata_file):
                try:
                    with open(self.metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                except:
                    pass
            
            metadata[backup_name] = {
                'version': version,
                'timestamp': datetime.now().isoformat(),
                'path': os.path.join(self.backup_dir, backup_name)
            }
            
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.warning(f"保存备份元数据失败: {e}")
    
    def _cleanup_old_backups(self, keep_latest: int = 3) -> int:
        """
        清理旧备份文件，只保留最新的N个
        
        Args:
            keep_latest: 保留的最新备份数量，默认为3
            
        Returns:
            清理的备份数量
        """
        try:
            if not os.path.exists(self.backup_dir):
                return 0
            
            # 列出所有备份目录
            backups = []
            for item in os.listdir(self.backup_dir):
                if item.startswith('yt_dlp_backup_'):
                    item_path = os.path.join(self.backup_dir, item)
                    if os.path.isdir(item_path):
                        # 获取修改时间作为排序键
                        mtime = os.path.getmtime(item_path)
                        backups.append((mtime, item, item_path))
            
            # 按时间排序，最新的在前
            backups.sort(reverse=True)
            
            # 删除超出keep_latest的备份
            deleted_count = 0
            for _, backup_name, backup_path in backups[keep_latest:]:
                try:
                    shutil.rmtree(backup_path)
                    logger.info(f"已删除旧备份: {backup_name}")
                    deleted_count += 1
                    
                    # 从元数据中删除
                    if os.path.exists(self.metadata_file):
                        try:
                            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                            if backup_name in metadata:
                                del metadata[backup_name]
                            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                                json.dump(metadata, f, indent=2, ensure_ascii=False)
                        except Exception as e:
                            logger.warning(f"删除备份元数据失败: {e}")
                except Exception as e:
                    logger.warning(f"删除备份失败 {backup_name}: {e}")
            
            if deleted_count > 0:
                logger.info(f"清理完成，共删除 {deleted_count} 个旧备份")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"清理备份出错: {e}")
            return 0
    
    def _is_yt_dlp_corrupted(self) -> bool:
        """
        检查yt_dlp源代码是否已损坏或不完整
        
        Returns:
            True 表示损坏或不存在，False 表示正常
        """
        try:
            # 检查目录是否存在
            if not os.path.exists(self.yt_dlp_dir):
                logger.warning(f"yt_dlp目录不存在: {self.yt_dlp_dir}")
                return True
            
            # 检查关键文件是否存在
            version_file = os.path.join(self.yt_dlp_dir, 'version.py')
            main_file = os.path.join(self.yt_dlp_dir, '__init__.py')
            
            if not os.path.exists(version_file):
                logger.warning(f"version.py 文件不存在")
                return True
            
            if not os.path.exists(main_file):
                logger.warning(f"__init__.py 文件不存在")
                return True
            
            # 检查version.py是否可读
            local_version = self.get_local_version()
            if not local_version:
                logger.warning(f"无法从version.py中读取版本信息")
                return True
            
            logger.debug(f"yt_dlp源代码验证通过，版本: {local_version}")
            return False
            
        except Exception as e:
            logger.error(f"检查yt_dlp完整性出错: {e}")
            return True

        # """获取最新的备份目录"""
        # try:
        #     backups = [d for d in os.listdir(self.backup_dir) 
        #               if d.startswith('yt_dlp_backup_')]
        #     if backups:
        #         return os.path.join(self.backup_dir, sorted(backups)[-1])
        # except Exception as e:
        #     logger.error(f"获取备份列表失败: {e}")
        # return None
    
    def rollback(self, backup_path: Optional[str] = None) -> bool:
        """
        回滚到备份版本
        
        Args:
            backup_path: 备份路径，若为None则回滚到最新备份
            
        Returns:
            是否成功
        """
        try:
            if backup_path is None:
                backup_path = self.get_latest_backup()
            
            if not backup_path or not os.path.exists(backup_path):
                logger.error(f"备份路径不存在: {backup_path}")
                return False
            
            # 删除当前yt_dlp目录，恢复备份
            if os.path.exists(self.yt_dlp_dir):
                self._remove_path(self.yt_dlp_dir)
            
            shutil.copytree(backup_path, self.yt_dlp_dir)
            logger.info(f"回滚成功")
            return True
            
        except Exception as e:
            logger.error(f"回滚失败: {e}")
            return False
    
    def get_release_info(self, version: str) -> Optional[Dict]:
        """
        获取特定版本的发布信息（更新日志、发布时间等）
        
        Args:
            version: 版本号
            
        Returns:
            发布信息字典
        """
        try:
            url = f"https://api.github.com/repos/yt-dlp/yt-dlp/releases/tags/{version}"
            
            request = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (pyMediaTools)'}
            )
            
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return {
                    'version': version,
                    'published_at': data.get('published_at'),
                    'body': data.get('body'),
                    'download_url': data.get('html_url'),
                }
                
        except Exception as e:
            logger.warning(f"获取发布信息失败: {e}")
            return None


class YtDlpUpdater(YtDlpVersionManager):
    """yt-dlp版本更新器 (继承自版本管理器)"""
    
    def update_from_github(self) -> Tuple[bool, str]:
        """
        从GitHub下载并更新yt-dlp源代码
        
        Returns:
            (是否成功, 消息)
        """
        try:
            # 获取远程版本
            remote_version = self.get_remote_version_from_github()
            if not remote_version:
                return False, "无法获取GitHub上的最新版本"
            
            local_version = self.get_local_version()
            if local_version and not VersionComparator.is_newer(remote_version, local_version):
                return False, f"本地版本 {local_version} 已是最新"
            
            # 检查本地源码是否完整
            is_corrupted = self._is_yt_dlp_corrupted()
            backup_path = None
            
            if not is_corrupted:
                # 本地源码完整，进行备份
                logger.info("正在备份当前版本...")
                backup_path = self.backup_current()
                if not backup_path:
                    logger.warning("备份失败，但将继续进行更新操作...")
            else:
                # 本地源码不存在或损坏，跳过备份
                logger.warning("本地源码不存在或已损坏，将直接下载最新版本...")
                backup_path = None
            
            logger.info(f"正在下载版本 {remote_version}...")
            
            # 下载zip文件
            download_url = f"https://github.com/yt-dlp/yt-dlp/archive/refs/tags/{remote_version}.zip"
            zip_path = os.path.join(self.backup_dir, f"yt_dlp_{remote_version}.zip")
            
            logger.info(f"正在从 {download_url} 下载...")
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"下载完成: {zip_path}")
            
            # 解压并替换
            import zipfile
            temp_extract_dir = os.path.join(self.backup_dir, f"yt_dlp_temp_{remote_version}")
            
            # 先删除临时目录（如果存在）
            if os.path.exists(temp_extract_dir):
                self._remove_path(temp_extract_dir)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
            
            logger.debug(f"解压到临时目录: {temp_extract_dir}")
            
            # 查找yt_dlp源代码目录
            # GitHub zip包的目录结构: yt-dlp-<version>/yt_dlp/
            src_path = None
            
            # 方式1: 直接查找yt-dlp-<version>/yt_dlp目录
            for item in os.listdir(temp_extract_dir):
                item_path = os.path.join(temp_extract_dir, item)
                if os.path.isdir(item_path):
                    yt_dlp_path = os.path.join(item_path, "yt_dlp")
                    if os.path.exists(yt_dlp_path) and os.path.exists(os.path.join(yt_dlp_path, "version.py")):
                        src_path = yt_dlp_path
                        logger.debug(f"找到yt_dlp源目录: {src_path}")
                        break
            
            # 方式2: 递归查找包含version.py的yt_dlp目录
            if not src_path:
                for root, dirs, files in os.walk(temp_extract_dir):
                    if 'version.py' in files and os.path.basename(root) == 'yt_dlp':
                        src_path = root
                        logger.debug(f"通过递归查找到yt_dlp目录: {src_path}")
                        break
            
            if not src_path or not os.path.exists(os.path.join(src_path, 'version.py')):
                # 清理临时目录和zip文件
                if os.path.exists(temp_extract_dir):
                    shutil.rmtree(temp_extract_dir)
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                logger.error(f"未找到有效的yt_dlp源代码目录")
                return False, "下载的文件格式不正确，找不到yt_dlp源目录"
            
            # 替换yt_dlp目录
            if os.path.exists(self.yt_dlp_dir):
                self._remove_path(self.yt_dlp_dir)
            
            shutil.copytree(src_path, self.yt_dlp_dir)
            logger.info(f"成功替换yt_dlp目录")
            
            # 清理临时文件
            if os.path.exists(temp_extract_dir):
                self._remove_path(temp_extract_dir)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            logger.info(f"已清理临时文件")
            
            # 更新成功，清理旧备份（只保留最新的3个）
            logger.info("清理旧备份文件...")
            self._cleanup_old_backups(keep_latest=3)
            
            logger.info(f"更新成功，新版本: {remote_version}")
            return True, f"成功更新到版本 {remote_version}"
            
        except Exception as e:
            logger.error(f"更新失败: {e}")
            
            # 清理临时文件
            try:
                # 尝试清理在scope内的临时变量（来自于本地作用域）
                # 这里我们使用较为通用的方法
                import glob
                temp_dirs = glob.glob(os.path.join(self.backup_dir, "yt_dlp_temp_*"))
                for temp_dir in temp_dirs:
                    if os.path.exists(temp_dir):
                        self._remove_path(temp_dir)
                        logger.debug(f"清理临时目录: {temp_dir}")
            except Exception as cleanup_err:
                logger.warning(f"临时文件清理出错: {cleanup_err}")
            
            # 尝试回滚
            if self.rollback():
                return False, f"更新失败且已回滚: {str(e)}"
            else:
                return False, f"更新失败，回滚也失败: {str(e)}"
    
    def update_from_pypi(self) -> Tuple[bool, str]:
        """
        通过pip更新yt-dlp
        
        Returns:
            (是否成功, 消息)
        """
        try:
            remote_version = self.get_remote_version_from_pypi()
            if not remote_version:
                return False, "无法获取PyPI上的最新版本"
            
            local_version = self.get_local_version()
            if local_version and not VersionComparator.is_newer(remote_version, local_version):
                return False, f"本地版本 {local_version} 已是最新"
            
            # 检查本地源码是否完整
            is_corrupted = self._is_yt_dlp_corrupted()
            backup_path = None
            
            if not is_corrupted:
                # 本地源码完整，进行备份
                logger.info("正在备份当前版本...")
                backup_path = self.backup_current()
                if not backup_path:
                    logger.warning("备份失败，但将继续进行更新操作...")
            else:
                # 本地源码不存在或损坏，跳过备份
                logger.warning("本地源码不存在或已损坏，将直接安装最新版本...")
                backup_path = None
            
            logger.info(f"正在通过pip安装版本 {remote_version}...")
            
            # 使用pip安装
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", f"yt-dlp=={remote_version}", "-U"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"pip安装失败: {result.stderr}")
                self.rollback(backup_path)
                return False, f"pip安装失败: {result.stderr}"
            
            # 安装成功，清理旧备份（只保留最新的3个）
            logger.info("清理旧备份文件...")
            self._cleanup_old_backups(keep_latest=3)
            
            logger.info(f"更新成功，新版本: {remote_version}")
            return True, f"成功通过pip更新到版本 {remote_version}"
            
        except Exception as e:
            logger.error(f"pip更新失败: {e}")
            return False, f"pip更新失败: {str(e)}"


# 导出公共接口
__all__ = [
    'YtDlpVersionManager',
    'YtDlpUpdater',
    'VersionComparator',
]
