import sys
from pathlib import Path

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