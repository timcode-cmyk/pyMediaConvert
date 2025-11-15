import sys
from pathlib import Path

def get_base_dir() -> Path:
    """
    返回项目根目录：
    - 开发环境：pyMediaConvert/utils.py 的父目录的父目录
    - 打包环境（Nuitka/frozen）：sys.executable 所在目录
    """
    if getattr(sys, "frozen", False):
        # 打包后可执行文件
        return Path(sys.executable).parent
    else:
        # 开发环境
        return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
BIN_DIR = BASE_DIR / "bin"
ASSET_DIR = BASE_DIR / "assets"

def get_resource_path(*parts) -> Path:
    return BASE_DIR.joinpath(*parts)

def get_ffmpeg_exe() -> str:
    exe_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    return str(BIN_DIR / exe_name)

def get_ffprobe_exe() -> str:
    exe_name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    return str(BIN_DIR / exe_name)