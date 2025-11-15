import sys
import os
from pathlib import Path

def get_base_path() -> Path:
    """获取程序运行时的根目录路径。"""
    # 检查是否是冻结（打包）环境
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包环境
        return Path(sys._MEIPASS)
    # 开发环境或沙盒环境
    return Path(__file__).resolve().parent.parent

def get_resource_path(relative_path: str) -> Path:
    """
    根据相对路径获取资源的绝对路径。
    Args:
        relative_path: 相对于项目根目录的相对路径。
    """
    # 逻辑保持不变，确保在沙盒环境中正确解析 'bin/ffmpeg' 等路径
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
        return base_path / 'src' / relative_path
    else:
        return Path(relative_path) 

# --- FFmpeg/FFprobe 路径获取逻辑 ---
def get_ffmpeg_exe() -> str:
    """返回当前平台下 ffmpeg 可执行文件的路径（字符串格式，用于 subprocess）。"""
    if sys.platform == "win32":
        return str(get_resource_path("bin/ffmpeg.exe"))
    elif sys.platform == "darwin":
        return str(get_resource_path("bin/ffmpeg"))
    elif "aarch64" in os.uname().machine:
        return str(get_resource_path("bin/ffmpeglinuxarm"))
    else:
        # 默认 Linux (x86-64)
        return str(get_resource_path("bin/ffmpeglinux64"))

def get_ffprobe_exe() -> str:
    """返回 ffprobe 可执行文件的路径（字符串格式，用于 subprocess）。"""
    if sys.platform == "win32":
        return str(get_resource_path("bin/ffprobe.exe"))
    elif sys.platform == "darwin":
        return str(get_resource_path("bin/ffprobe"))
    elif "aarch64" in os.uname().machine:
        return str(get_resource_path("bin/ffprobelinuxarm")) 
    else:
        # 默认 Linux (x86-64)
        return str(get_resource_path("bin/ffprobelinux64"))