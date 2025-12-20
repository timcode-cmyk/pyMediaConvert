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


def get_aria2c_exe() -> str:
    """Return aria2c executable path (bundled in BIN_DIR or system PATH).

    Prefers bundled `bin/aria2c`, falls back to PATH if not found.
    """
    exe_name = "aria2c.exe" if sys.platform == "win32" else "aria2c"
    path = BIN_DIR / exe_name
    if path.exists():
        _ensure_executable(path)
        return str(path)

    # fallback to system path (which may be e.g. /usr/local/bin/aria2c)
    from shutil import which
    found = which(exe_name)
    if found:
        return found

    # return bundled path even if missing so callers can surface a better error
    return str(path)


def get_aria2_rpc_port() -> int:
    """返回 aria2 RPC 端口号（从配置或默认值）"""
    config = load_project_config()
    return config.get('download', {}).get('rpc_port', 6800)


def get_aria2_rpc_secret() -> str:
    """返回 aria2 RPC secret（从配置或默认值）"""
    config = load_project_config()
    return config.get('download', {}).get('rpc_secret', '')


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