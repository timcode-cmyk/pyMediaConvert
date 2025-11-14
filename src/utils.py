import sys
import os
from pathlib import Path

def get_base_path() -> Path:
    """获取程序运行时的根目录路径。
    如果是 PyInstaller 打包后的环境，返回临时解压路径 sys._MEIPASS。
    否则，返回当前 Python 文件的目录（开发环境）。
    """
    # 检查是否是冻结（打包）环境
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包环境
        return Path(sys._MEIPASS)
    # 开发环境
    # (修改) 假设 utils.py 在 src/ 目录下，我们希望根目录是 src/ 的上一级
    return Path(__file__).resolve().parent.parent

def get_resource_path(relative_path: str) -> Path:
    """
    根据相对路径获取资源的绝对路径。
    Args:
        relative_path: 相对于项目根目录的相对路径（例如 'src/bin/ffmpeg' 或 'src/assets/vidu.png'）。
    (修改) 现在 relative_path 应该是 'src/assets/vidu.png'
    或者 'src/bin/ffmpeg.exe'
    """
    base_path = get_base_path()
    # (修改) 我们假设 'assets/' 或 'bin/' 已经是 'src/' 的一部分
    # get_base_path() 返回的是项目根目录
    # 传入的 relative_path 应该是 'src/assets/hailuo.png'
    # (更正) 根据您的原始代码，assets/ 和 bin/ 是在 src/ 下的
    # 传入的 relative_path 应该是 'assets/hailuo.png'
    # 那么 get_resource_path 应该返回 base_path / 'src' / relative_path
    # (再次更正) 让我们遵循您 utils.py 的原始逻辑
    # get_base_path() 返回 sys._MEIPASS 或 .../src/
    # get_resource_path('bin/ffmpeg') 返回 .../src/bin/ffmpeg
    # get_resource_path('assets/vidu.png') 返回 .../src/assets/vidu.png
    # 这意味着 get_base_path() 应该返回 .../src/ 目录
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # 打包环境, sys._MEIPASS 是根
        base_path = Path(sys._MEIPASS)
        # 假设打包时 src 目录下的内容被放到了根目录
        # 或者
        # (最可能的) 打包时 src/bin, src/assets 被复制到了
        # sys._MEIPASS/src/bin 和 sys._MEIPASS/src/assets
        return base_path / 'src' / relative_path
    else:
        # 开发环境, __file__ 是 .../src/utils.py
        # parent 是 .../src/
        base_path = Path(__file__).resolve().parent
        return base_path / relative_path

# --- FFmpeg/FFprobe 路径获取逻辑 ---
# (修改) 让 get_resource_path 处理 'bin/' 前缀
def get_ffmpeg_exe() -> str:
    """返回当前平台下 ffmpeg 可执行文件的路径（字符串格式，用于 subprocess）。"""
    if sys.platform == "win32":
        # Windows
        return str(get_resource_path("bin/ffmpeg.exe"))
    elif sys.platform == "darwin":
        # macOS
        return str(get_resource_path("bin/ffmpeg"))
    elif "aarch64" in os.uname().machine:
        # Linux ARM (如 Raspberry Pi, Jetson)
        return str(get_resource_path("bin/ffmpeglinuxarm"))
    else:
        # 默认 Linux (x86-64)
        return str(get_resource_path("bin/ffmpeglinux64"))

def get_ffprobe_exe() -> str:
    """返回 ffprobe 可执行文件的路径（字符串格式，用于 subprocess）。"""
    if sys.platform == "win3n32":
        # Windows
        return str(get_resource_path("bin/ffprobe.exe"))
    # 其他平台统一假设为无后缀名
    # (修改) ffprobe 也可能需要区分 arm
    # 为简单起见，我们假设 ffprobe 和 ffmpeg 的 bin 目录结构一致
    elif sys.platform == "darwin":
        return str(get_resource_path("bin/ffprobe"))
    elif "aarch64" in os.uname().machine:
        return str(get_resource_path("bin/ffprobelinuxarm")) # 假设您也有一个 ffprobearm
    else:
        return str(get_resource_path("bin/ffprobelinux64"))