'''utils.py - 通用实用程序函数

    BASE_DIR: Path：项目根目录路径。
    BIN_DIR: Path：内置二进制工具目录 (BASE_DIR / "bin")。
    ASSET_DIR: Path：内置静态资源目录 (BASE_DIR / "assets")。
    get_base_dir() -> Path：跨环境（开发环境、PyInstaller 解包目录 sys._MEIPASS、Nuitka 可执行文件目录）识别项目真实基准路径。
    find_config_path() -> Optional[Path]：按环境变量 PYMEDIA_CONFIG_PATH -> 项目根目录 -> 当前工作目录 -> 父目录链顺序查找 config.toml。
    load_project_config() -> dict：加载并全局缓存 config.toml 配置字典。
    save_project_config(config_dict: dict)：将更新后的配置字典写回 config.toml。
    get_elevenlabs_config() -> dict：快捷获取 ElevenLabs 相关子配置。
    get_resource_path(*parts) -> Path：拼接获取 assets 或其他静态资源的绝对路径。
    get_ffmpeg_exe() -> str：返回当前操作系统平台对应的 ffmpeg 可执行文件绝对路径，并在 Unix 平台确保赋予可执行权限 (+x)。
    get_ffprobe_exe() -> str：返回当前平台对应的 ffprobe 可执行文件绝对路径。
    get_default_download_dir() -> Path：获取默认下载目录（优先读取配置文件，默认回退到系统 Downloads 目录）。
'''

import sys
import os
from pathlib import Path
from typing import Optional

# TOML parser: prefer stdlib tomllib (Python 3.11+), fallback to third-party `toml`.
try:
    import tomllib as _toml
except Exception:
    try:
        import toml as _toml
    except Exception:
        _toml = None


def get_base_dir() -> Path:
    """
    返回项目根目录：
    - 开发环境：pyMediaConvert/utils.py 的父目录的父目录
    - 打包环境 (PyInstaller onefile)：使用 sys._MEIPASS（运行时解包目录）
    - 其他打包器（Nuitka/frozen）：sys.executable 所在目录
    """
    # PyInstaller onefile 运行时会把数据解包到 sys._MEIPASS
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        return Path(meipass)

    if getattr(sys, "frozen", False):
        # 其他打包器：可执行文件所在目录
        return Path(sys.executable).parent
    else:
        # 开发环境
        return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
BIN_DIR = BASE_DIR / "bin"
ASSET_DIR = BASE_DIR / "assets"

# 项目级配置缓存和帮助程序
_PROJECT_CONFIG = None

def find_config_path() -> Optional[Path]:
    """搜索项目“config.toml”。

    优先顺序：
      -来自 env PYMEDIA_CONFIG_PATH 或 PYMEDIA_CONFIG 的路径
      -项目基础 `config.toml` （由 `get_base_dir()` 返回）
      -当前工作目录`config.toml`
      -从该文件向上的任何父目录
    """
    env_path = os.getenv('PYMEDIA_CONFIG_PATH') or os.getenv('PYMEDIA_CONFIG')
    candidates = []
    if env_path:
        candidates.append(Path(env_path))

    candidates.append(BASE_DIR / 'config.toml')
    candidates.append(Path.cwd() / 'config.toml')

    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / 'config.toml')

    for c in candidates:
        if c and c.exists():
            return c
    return None


def load_project_config() -> dict:
    """将顶级 TOML 配置加载并缓存为字典。

    如果未找到配置，则返回一个空字典。
    """
    global _PROJECT_CONFIG
    if _PROJECT_CONFIG is not None:
        return _PROJECT_CONFIG
    cfg_path = find_config_path()
    if not cfg_path:
        _PROJECT_CONFIG = {}
        return _PROJECT_CONFIG

    if _toml is None:
        raise RuntimeError("TOML 解析器不可用。为 Python < 3.11 安装“toml”")

    data = cfg_path.read_bytes()
    try:
        _PROJECT_CONFIG = _toml.loads(data.decode() if isinstance(data, (bytes, bytearray)) else data)
    except Exception:
        # toml package expects str on some platforms
        _PROJECT_CONFIG = _toml.loads(data.decode())
    return _PROJECT_CONFIG

def save_project_config(config_dict: dict):
    """将配置字典保存回 config.toml"""
    global _PROJECT_CONFIG
    _PROJECT_CONFIG = config_dict
    cfg_path = find_config_path()
    if not cfg_path:
        # 若没找到现有配置，默认写入基础目录
        cfg_path = BASE_DIR / 'config.toml'
        
    if _toml is None:
        import logging
        logging.getLogger(__name__).error("TOML parser not available. Cannot save config.")
        return
        
    try:
        with open(cfg_path, 'w', encoding='utf-8') as f:
            _toml.dump(config_dict, f)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception(f"配置保存失败: {e}")


def get_elevenlabs_config() -> dict:
    return load_project_config().get('elevenlabs', {}) or {}


def get_resource_path(*parts) -> Path:
    return BASE_DIR.joinpath(*parts)

def _ensure_executable(path: Path):
    try:
        if sys.platform != 'win32' and path.exists():
            mode = path.stat().st_mode
            # add owner execute bit if missing
            if not (mode & 0o100):
                path.chmod(mode | 0o100)
    except Exception:
        # best-effort only
        pass


def get_ffmpeg_exe() -> str:
    exe_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    path = BIN_DIR / exe_name
    _ensure_executable(path)
    return str(path)


def get_ffprobe_exe() -> str:
    exe_name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    path = BIN_DIR / exe_name
    _ensure_executable(path)
    return str(path)


def get_default_download_dir() -> Path:
    """返回默认下载目录"""
    config = load_project_config()
    download_dir = config.get('download', {}).get('default_dir')
    if download_dir:
        return Path(download_dir).expanduser()
    
    # 默认使用用户下载目录
    if sys.platform == "win32":
        return Path.home() / "Downloads"
    else:
        return Path.home() / "Downloads"