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

# Project-level configuration cache and helpers
_PROJECT_CONFIG = None

def find_config_path() -> Optional[Path]:
    """Search for a project `config.toml`.

    Order of preference:
      - path from env PYMEDIA_CONFIG_PATH or PYMEDIA_CONFIG
      - project base `config.toml` (returned by `get_base_dir()`)
      - current working dir `config.toml`
      - any parent directories upwards from this file
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
    """Load and cache the top-level TOML config as a dict.

    Returns an empty dict if no config found.
    """
    global _PROJECT_CONFIG
    if _PROJECT_CONFIG is not None:
        return _PROJECT_CONFIG
    cfg_path = find_config_path()
    if not cfg_path:
        _PROJECT_CONFIG = {}
        return _PROJECT_CONFIG

    if _toml is None:
        raise RuntimeError("TOML parser not available. Install 'toml' for Python < 3.11")

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