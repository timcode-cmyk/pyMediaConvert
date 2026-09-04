"""
多媒体与硬件工具模块

提供统一直观的接口用于获取视频信息、格式化路径以及探测硬件加速器。
"""
import sys
import subprocess
import re
from pathlib import Path
from PySide6.QtCore import QProcess

from ..utils import get_ffmpeg_exe, get_ffprobe_exe
from ..logging_config import get_logger

logger = get_logger(__name__)

_GLOBAL_ENCODER_CACHE = None


def format_ffmpeg_path(path: str) -> str:
    r"""
    格式化路径以适配 FFmpeg 过滤器 (ass, drawtext)
    - Windows 下需要将 \ 替换为 /，并将 C: 替换为 C\:
    """
    if sys.platform == "win32":
        # 替换反斜杠为正斜杠，并转义冒号
        return path.replace("\\", "/").replace(":", "\\:")
    return path


def verify_encoder_usability(name: str) -> bool:
    """
    通过运行一个极短的空转任务，验证硬件编码器是否真的可用。
    防止出现 FFmpeg 编译支持但系统无硬件/无驱动的情况。
    """
    # 测试命令：产生一个 64x64 的黑块，编码 0.01 秒，输出到空设备
    cmd = [
        get_ffmpeg_exe(),
        "-v", "error",
        "-f", "lavfi",
        "-i", "nullsrc=s=64x64:d=0.01",
        "-c:v", name,
        "-f", "null",
        "-"
    ]
    
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        # 设置 5 秒超时，防止卡死
        subprocess.run(cmd, capture_output=True, check=True, timeout=5, creationflags=creationflags)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        # 记录失败原因
        err_msg = ""
        if isinstance(e, subprocess.CalledProcessError):
            err_msg = e.stderr.decode('utf-8', errors='ignore').strip()
        logger.warning(f"验证编码器可用性失败: {name} -> {err_msg or '超时'}")
        return False
    except Exception:
        return False


def detect_hardware_encoders(force_refresh: bool = False) -> dict:
    """
    运行 'ffmpeg -encoders' 并解析输出，找出可用的硬件加速编码器。
    带有全局缓存机制。
    
    返回可用的编码器字典：{ "h264_nvenc": "描述..." }
    """
    global _GLOBAL_ENCODER_CACHE
    if _GLOBAL_ENCODER_CACHE is not None and not force_refresh:
        return _GLOBAL_ENCODER_CACHE

    available_encoders = {}
    cmd = [get_ffmpeg_exe(), "-encoders"]

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(cmd, 
                                capture_output=True, 
                                text=True, 
                                check=True, 
                                encoding='utf-8', 
                                errors='ignore',
                                creationflags=creationflags)
        
        encoder_regex = re.compile(r"([VASDEV.]{6})\s+(\S+)\s+(.*)")
        
        for line in result.stdout.splitlines():
            match = encoder_regex.search(line)
            if match:
                flags = match.group(1)
                name = match.group(2)
                description = match.group(3).strip()
                
                # 硬件加速编码器通常名称中包含 'nvenc', 'qsv', 'amf', 'videotoolbox', 'mediacodec' 等
                is_hardware = any(hw in name for hw in ['nvenc', 'qsv', 'amf', 'videotoolbox', 'mediacodec'])
                
                if ('V' in flags or 'A' in flags) and is_hardware:
                     if verify_encoder_usability(name):
                         available_encoders[name] = description
                     else:
                         logger.info(f"忽略不可用的硬件编码器: {name}")
                         
    except subprocess.CalledProcessError as e:
        logger.warning(f"无法运行 FFmpeg -encoders: {e.stderr.strip()}")
    except Exception as e:
        logger.exception(f"编码器检测过程中发生未知错误: {e}")

    _GLOBAL_ENCODER_CACHE = available_encoders
    return available_encoders


def get_video_duration(file_path: Path | str, use_qprocess: bool = False, debug: bool = False) -> float:
    """
    获取视频时长。
    
    参数:
    - file_path: 视频文件路径
    - use_qprocess: 是否使用 QProcess (用于防止打包环境或带有UI界面情况下的死锁)
    - debug: 打印调试信息
    """
    ffprobe_exe = get_ffprobe_exe()
    args = [
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]

    if use_qprocess:
        process = QProcess()
        env = process.processEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(env)
        
        process.start(ffprobe_exe, args)
        if not process.waitForStarted(5000):
            logger.error("ffprobe 启动失败 (QProcess)")
            return 0.0

        if not process.waitForFinished(10000):
            logger.error("ffprobe 执行超时 (QProcess)")
            process.kill()
            return 0.0

        if process.exitCode() != 0:
            logger.error(f"ffprobe 运行出错，错误码: {process.exitCode()}")
            return 0.0

        output = str(process.readAllStandardOutput(), encoding='utf-8').strip()
        try:
            return float(output) if output else 0.0
        except ValueError:
            logger.error(f"无法解析时长输出: {output}")
            return 0.0
    else:
        cmd = [ffprobe_exe] + args
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
        
        if debug:
            logger.debug(f"执行 ffprobe 命令获取时长: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, 
                                   encoding='utf-8', creationflags=creationflags)
            duration = float(result.stdout.strip())
            if debug:
                logger.debug(f"视频时长: {duration}s")
            return duration
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"无法获取视频时长 {file_path}: {e}")
            return 0.0


def get_video_fps(video_path: Path | str, debug: bool = False) -> float:
    """获取视频帧率"""
    cmd = [
        get_ffmpeg_exe(), '-i', str(video_path),
        '-an', '-f', 'null', '-'
    ]
    
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
    
    if debug:
        logger.debug(f"执行 ffmpeg 命令获取帧率: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8',
                           creationflags=creationflags)
    
    match = re.search(r"(\d+(\.\d+)?) fps", result.stderr)
    fps = float(match.group(1)) if match else 25.0
    
    if debug:
        logger.debug(f"视频帧率: {fps} FPS")
    
    return fps
