"""
aria2下载管理器
"""
import subprocess
import json
import sys
import urllib.request
import time
import atexit
from typing import Dict, List, Optional
from ..utils import get_aria2c_exe, get_aria2_rpc_port, get_aria2_rpc_secret, get_default_download_dir
from pyMediaTools import get_logger

logger = get_logger(__name__)

class DownloadManager:
    def __init__(self):
        self.port = get_aria2_rpc_port()
        self.secret = get_aria2_rpc_secret()
        self.process = None
        self._start_aria2c()
        atexit.register(self.stop_server)

    def _start_aria2c(self):
        """启动 aria2c 并配置初始参数"""
        cmd = [
            get_aria2c_exe(),
            f"--rpc-listen-port={self.port}",
            "--enable-rpc=true",
            "--rpc-allow-origin-all=true",
            f"--rpc-secret={self.secret}" if self.secret else "",
            "--max-concurrent-downloads=4", # 默认同时下载4个
            "--continue=true",              # 断点续传
            "--max-connection-per-server=16", # 每个服务器最大连接
            "--split=16",                   # 单文件分块数
            "--daemon=false"
        ]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            self.process = subprocess.Popen(
                [c for c in cmd if c],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags
            )
            logger.info(f"aria2c 核心已启动，端口: {self.port}")
        except Exception as e:
            logger.error(f"启动 aria2c 失败: {e}")

    def _call_rpc(self, method: str, params: list = None):
        url = f"http://localhost:{self.port}/jsonrpc"
        auth_token = f"token:{self.secret}" if self.secret else None
        
        rpc_params = []
        if auth_token:
            rpc_params.append(auth_token)
        if params:
            rpc_params.extend(params)

        payload = {
            "jsonrpc": "2.0",
            "id": "pyMedia",
            "method": f"aria2.{method}",
            "params": rpc_params
        }
        try:
            req = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode('utf-8'), 
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=1) as response:
                return json.loads(response.read()).get('result')
        except Exception:
            return None

    def add_download(self, url: str, save_dir: str, use_acceleration: bool):
        """添加下载任务，可配置是否开启分块加速"""
        options = {
            "dir": save_dir,
            "split": "16" if use_acceleration else "1",
            "max-connection-per-server": "16" if use_acceleration else "1"
        }
        return self._call_rpc("addUri", [[url], options])

    def pause_task(self, gid: str):
        return self._call_rpc("pause", [gid])

    def unpause_task(self, gid: str):
        return self._call_rpc("unpause", [gid])

    def remove_task(self, gid: str):
        """停止并移除任务"""
        # 先尝试停止活跃任务，若已停止则移除历史
        res = self._call_rpc("forceRemove", [gid])
        if res is None:
            res = self._call_rpc("removeDownloadResult", [gid])
        return res

    def change_global_option(self, max_concurrent: int):
        """动态修改全局设置（如最大同时下载数）"""
        return self._call_rpc("changeGlobalOption", [{"max-concurrent-downloads": str(max_concurrent)}])

    def get_status_all(self):
        """获取所有任务：正在下载、等待中、已停止"""
        active = self._call_rpc("tellActive") or []
        waiting = self._call_rpc("tellWaiting", [0, 100]) or []
        stopped = self._call_rpc("tellStopped", [0, 100]) or []
        return active + waiting + stopped

    def stop_server(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1)
            except Exception:
                pass
            finally:
                self.process = None
                logger.info("aria2c 核心已关闭")