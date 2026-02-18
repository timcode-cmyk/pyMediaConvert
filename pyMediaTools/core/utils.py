"""
项目工具函数

包含 PyInstaller 打包环境兼容的路径解析函数。
"""
import os
import sys
from pathlib import Path

# TOML parser: prefer stdlib tomllib (Python 3.11+), fallback to third-party `toml`.
try:
    import tomllib as _toml
except ImportError:
    try:
        import toml as _toml
    except ImportError:
        raise RuntimeError(
            "TOML parser not available. For Python<3.11 install 'toml' (pip install toml)"
        )


def _get_bundle_dir():
    """
    获取程序运行时的根目录。
    - 在开发环境中，返回项目根目录。
    - 在 PyInstaller 打包后，返回可执行文件所在的目录。
    """
    if getattr(sys, 'frozen', False):
        # 程序被打包
        return Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(os.path.dirname(sys.executable))
    else:
        # 正常开发环境
        # 从当前文件 (__file__) 向上追溯两级: pyMediaTools/utils.py -> pyMediaTools -> project_root
        return Path(__file__).parent.parent.parent


def get_resource_path(relative_path: str) -> Path:
    """
    获取资源的绝对路径，兼容开发和打包环境。
    """
    base_path = _get_bundle_dir()
    return base_path / relative_path


def get_ffmpeg_exe() -> str:
    """获取 ffmpeg 可执行文件路径"""
    name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    return str(get_resource_path(f"bin/{name}"))


def get_ffprobe_exe() -> str:
    """获取 ffprobe 可执行文件路径"""
    name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    return str(get_resource_path(f"bin/{name}"))


def get_aria2c_exe() -> str:
    """获取 aria2c 可执行文件路径"""
    name = "aria2c.exe" if sys.platform == "win32" else "aria2c"
    return str(get_resource_path(f"bin/{name}"))


def find_config_path() -> Path | None:
    """查找 config.toml 文件"""
    path = get_resource_path("config.toml")
    return path if path.exists() else None


def load_project_config() -> dict:
    """加载项目配置文件 config.toml"""
    config_path = find_config_path()
    if config_path and config_path.exists():
        with open(config_path, "rb") as f:
            return _toml.load(f)
    return {}


def get_default_download_dir() -> Path:
    """获取默认下载目录"""
    return Path.home() / "Downloads"


def get_aria2_rpc_port() -> int:
    """获取 aria2 RPC 端口"""
    cfg = load_project_config().get('aria2', {})
    return int(cfg.get('rpc_port', 6800))


def get_aria2_rpc_secret() -> str | None:
    """获取 aria2 RPC 密钥"""
    cfg = load_project_config().get('aria2', {})
    return cfg.get('rpc_secret')