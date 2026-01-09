"""
视频批处理
依赖：ffmpeg, ffprobe 在 PATH 中

许可证声明：
本产品使用了 FFmpeg，其在 LGPL/GPL 下发布。
更多信息请参考项目的 README 文件。
"""
from pathlib import Path
import subprocess
from ..utils import get_ffmpeg_exe, get_ffprobe_exe, get_resource_path
from ..logging_config import get_logger
import sys
# from tqdm import tqdm
from PySide6.QtCore import QProcess, QEventLoop, QCoreApplication, Qt
from abc import ABC, abstractmethod
import re
# import tempfile
# import os
import time
_GLOBAL_ENCODER_CACHE = None

logger = get_logger(__name__)


# 用于存储 app.py 传递进来的 ProgressMonitor 实例
# GlobalProgressMonitor = None

class MediaConverter(ABC):
    """
    视频转换器的抽象基类。负责文件I/O、依赖检查和FFMPEG执行。
    """
    # 默认扩展名
    DEFAULT_SUPPORT_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}

    def __init__(self, support_exts=None, output_ext: str = None, init_checks: bool = True, use_cli: bool = False):
        if support_exts is not None:
            final_exts = support_exts
        else:
            if hasattr(self, 'DEFAULT_SUPPORT_EXTS'):
                final_exts = self.DEFAULT_SUPPORT_EXTS
            else:
                final_exts = MediaConverter.DEFAULT_SUPPORT_EXTS
        self.files = []
        # normalize supported extensions to lowercase for reliable matching
        self.support_exts = {ext.lower() for ext in final_exts}
        self.output_ext = output_ext
        
        # if output_ext:
        #     self.output_ext = output_ext
        # else:
        #     self.output_ext = ".mp4"

        self.available_encoders = {}
        self.use_cli = bool(use_cli)

        # Only run heavy checks if requested (GUI file-count helper will pass init_checks=False)
        if init_checks:
            self._check_ffmpeg_path()
            global _GLOBAL_ENCODER_CACHE
            if _GLOBAL_ENCODER_CACHE is None:
                # 第一次运行：执行探测
                self._detect_hardware_encoders()
                _GLOBAL_ENCODER_CACHE = self.available_encoders
            else:
                # 之后直接用缓存，不再运行 ffmpeg -encoders
                self.available_encoders = _GLOBAL_ENCODER_CACHE
    

    def _check_ffmpeg_path(self):
        """检查捆绑的 ffmpeg 和 ffprobe 文件是否存在"""
        # 注意：这里使用 get_ffmpeg_exe() 返回的路径，在运行时是绝对路径
        ffmpeg_path = Path(get_ffmpeg_exe())
        ffprobe_path = Path(get_ffprobe_exe())
        
        if not ffmpeg_path.exists():
            logger.critical(f"绑定的 ffmpeg 可执行文件未找到: {ffmpeg_path}")
            raise FileNotFoundError(f"ffmpeg not found: {ffmpeg_path}")
        if not ffprobe_path.exists():
            logger.critical(f"绑定的 ffprobe 可执行文件未找到: {ffprobe_path}")
            raise FileNotFoundError(f"ffprobe not found: {ffprobe_path}")

    def _detect_hardware_encoders(self):
        """
        运行 'ffmpeg -encoders' 并解析输出，找出可用的硬件加速编码器。
        
        FFmpeg 输出格式示例:
        V.F... h264                  H.264 / AVC (High Efficiency)
        V..... h264_nvenc            NVIDIA NVENC H.264 Encoder (codec h264)
        """
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
            
            # 正则表达式用于匹配编码器行：
            # 1. 匹配起始标志：六个字符的旗帜 (如 VFS---)
            # 2. 匹配编码器名称 (如 h264_nvenc)
            # 3. 匹配描述
            # 并且只查找带有 'V' (Video) 或 'A' (Audio) 旗帜的行
            encoder_regex = re.compile(r"([VASDEV.]{6})\s+(\S+)\s+(.*)")
            
            for line in result.stdout.splitlines():
                match = encoder_regex.search(line)
                if match:
                    flags = match.group(1)
                    name = match.group(2)
                    description = match.group(3).strip()
                    
                    # 检查 flags，如果第一个字符是 'V' 或 'A' 且不是内置软件编码器
                    # 硬件加速编码器通常名称中包含 'nvenc', 'qsv', 'amf', 'videotoolbox' 等
                    is_hardware = any(hw in name for hw in ['nvenc', 'qsv', 'amf', 'videotoolbox', 'mediacodec'])
                    
                    if ('V' in flags or 'A' in flags) and is_hardware:
                         self.available_encoders[name] = description
                         
            # 调试信息：可以在开发阶段打印找到的编码器
            # print(f"检测到可用硬件编码器: {self.available_encoders}")

        except subprocess.CalledProcessError as e:
            logger.warning(f"无法运行 FFmpeg -encoders: {e.stderr.strip()}")
        except Exception as e:
            logger.exception(f"编码器检测过程中发生未知错误: {e}")

    def _get_video_codec_params(self, force_codec: str = None) -> tuple[str, str, str]:
        """
        根据检测到的可用编码器和优先级，返回最佳的 H.264 编码器和参数。
        
        :param force_codec: 如果指定，则强制使用该编码器（例如 'dnxhd'）。
        :return: (video_codec, preset_key, preset_value)
        """
        # 如果强制指定，则不进行 H.264 硬件检测
        if force_codec:
            return force_codec, None, None

        video_codec = "libx264"
        preset_key = "-preset"
        preset_value = "medium"
        
        # 优先级：VideoToolbox (Mac) -> NVENC (Nvidia) -> QSV (Intel) -> libx264 (CPU)

        # 1. 检查 macOS VideoToolbox
        if "h264_videotoolbox" in self.available_encoders:
            video_codec = "h264_videotoolbox"
            # VideoToolbox 通常使用 -q:v (质量)
            preset_key = "-q:v" 
            preset_value = "70" 
            
        # 2. 检查 NVIDIA
        elif "h264_nvenc" in self.available_encoders:
            video_codec = "h264_nvenc"
            preset_key = "-preset"
            preset_value = "fast" 

        # 3. 检查 Intel QSV
        elif "h264_qsv" in self.available_encoders:
            video_codec = "h264_qsv"
            preset_key = "-preset"
            preset_value = "veryfast"
            
        # 4. 默认 CPU 编码器参数
        else:
            # libx264 使用 -crf 参数，但这不是 preset key，
            # 我们返回 None，让子类知道使用 -crf 20
            preset_key = "-crf"
            preset_value = "20"
        
        return video_codec, preset_key, preset_value

    def find_files(self, directory: Path):
        """
        递归查找支持的文件，支持传入单个文件或目录。
        排除由本工具生成的输出文件（根据 config 中定义的 output_ext）。
        """
        # 避免处理已经是输出后缀的文件（例如 _hailuo.mp4 / _h264.mp4）
        try:
            from .config import MODES
            output_exts = {cfg.get('output_ext').lower() for cfg in MODES.values() if cfg.get('output_ext')}
        except Exception:
            output_exts = set()

        candidates = []
        if directory.is_file():
            p = directory
            if p.suffix.lower() in self.support_exts and not any(p.name.endswith(ext) for ext in output_exts):
                candidates.append(p)
        else:
            # 仅查找目录下的直接文件（不递归进入子目录）
            for p in directory.iterdir():
                if not p.is_file():
                    continue
                if p.suffix.lower() not in self.support_exts:
                    continue
                if any(p.name.endswith(ext) for ext in output_exts):
                    continue
                candidates.append(p)

        # 去重并排序
        unique_sorted = sorted({str(p): p for p in candidates}.items(), key=lambda x: x[0])
        self.files = [p for _, p in unique_sorted]
    
    def get_duration(self, file_path: Path) -> float:
        """使用 QProcess 安全地获取视频时长，防止打包环境下的死锁"""
        ffprobe_exe = get_ffprobe_exe()
        
        args = [
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]

        process = QProcess()
        # 强制不使用缓冲
        env = process.processEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(env)

        process.start(ffprobe_exe, args)
        
        # 给予一定的超时时间，同时保持 UI 刷新
        # 这能解决双击运行时，系统因校验二进制文件导致的瞬间卡顿
        if not process.waitForStarted(5000):
            logger.error("ffprobe 启动失败")
            return 0.0

        # 循环等待结束，同时允许 UI 处理事件
        while process.state() == QProcess.ProcessState.Running:
            QCoreApplication.processEvents()
            if process.waitForFinished(100):
                break

        output = str(process.readAllStandardOutput(), encoding='utf-8').strip()
        
        try:
            return float(output) if output else 0.0
        except ValueError:
            logger.error(f"无法解析时长输出: {output}")
            return 0.0
    
    def _parse_ffmpeg_output(self):
        """实时解析 FFmpeg 的 -progress pipe:1 输出"""
        
        if not self.process:
            return
        
        raw_stdout = self.process.readAllStandardOutput().data()
        # raw_stderr = self.process.readAllStandardError().data()
        # 读取所有输出行 (pipe:1 到 stdout)
        # raw_output = raw_stdout + raw_stderr
        lines = raw_stdout.decode('utf-8', errors='ignore').splitlines()

        current_seconds = self.last_seconds
        
        # 正则表达式用于匹配 time=HH:MM:SS.ms，用于非 pipe:1 的进度解析，但保留 pipe:1 的逻辑
        time_regex = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})") 

        for line in lines:
            if "=" in line:
                try:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()

                    # 解析 time
                    if k == "out_time_us":
                        current_seconds = int(v) / 1_000_000.0
                    elif k == "out_time_ms":
                        current_seconds = int(v) / 1_000.0
                    elif k == "out_time":
                        # 格式如 00:00:05.123
                        parts = v.split(":")
                        if len(parts) == 3:
                            hh, mm, ss = parts
                            current_seconds = int(hh) * 3600 + int(mm) * 60 + float(ss)
                    elif k == "progress" and v == "end":
                        current_seconds = self.total_duration
                        
                    current_seconds = round(current_seconds, 2)
                    
                    # 只有当进度确实前进时才更新
                    if current_seconds > self.last_seconds and current_seconds <= self.total_duration:
                        self.last_seconds = current_seconds
                        # 更新 GUI
                        if self.monitor:
                            self.monitor.update_file_progress(self.last_seconds, self.total_duration, self.current_file_name)

                    if k == "progress" and v == "end":
                        # 进程即将退出，退出解析循环
                        break
                except Exception:
                    # 忽略解析单行错误
                    continue

        # 保持最新的进度
        self.last_seconds = current_seconds

    def _capture_ffmpeg_error(self):
        """捕获 FFmpeg 过程中的警告和错误信息"""
        if not self.process:
            return
            
        # 捕获 stderr 输出并记录日志，FFmpeg 的非进度信息通常在这里
        error_data = str(self.process.readAllStandardError(), encoding='utf-8', errors='ignore')
        if error_data.strip():
            logger.warning(f"FFMPEG 错误/警告: {error_data.strip()}")
          
    def process_ffmpeg(self, cmd: list, duration: float, monitor, input_file_name: str):
        cmd[0] = get_ffmpeg_exe()
        self.monitor = monitor
        self.current_file_name = input_file_name
        self.total_duration = duration
        self.last_seconds = 0.0

        # 修改 1: 确保命令使用 -progress - 且尽可能精简输出
        final_cmd = [c for c in cmd if c not in ["-progress", "pipe:1", "-nostats"]]
        final_cmd.extend(["-progress", "-", "-nostats"])

        self.process = QProcess()
        
        # 修改 2: 强制设置环境变量，确保在 GUI 启动时也生效
        env = self.process.processEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        # env.insert("FFREPORT", "file=ffmpeg_log.txt:level=32") # 可选：输出日志到文件辅助调试
        self.process.setProcessEnvironment(env)

        # 混合输出模式，方便解析
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyRead.connect(self._parse_ffmpeg_output)

        try:
            self.process.start(final_cmd[0], final_cmd[1:])

            if not self.process.waitForStarted():
                raise Exception("FFmpeg 进程启动失败。")
            
            # 修改 3: 这里的循环是解决“双击卡住”的关键
            while self.process.state() == QProcess.ProcessState.Running:
                if self.monitor and self.monitor.check_stop_flag():
                    self.process.terminate()
                    break
                
                # 【核心】：使用 waitForReadyRead 强制让系统内核把管道里的数据“吐”出来
                # 即使 FFmpeg 在缓冲，这个操作也会增加拉取的频率
                if self.process.waitForReadyRead(50):
                    self._parse_ffmpeg_output()
                
                # 保持 UI 响应
                QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
                time.sleep(0.01)

            # 进程结束后再跑一次，确保最后 1% 的数据被读到
            self._parse_ffmpeg_output()

        except Exception as e:
            logger.exception(f"FFMPEG 进程异常: {e}")
            self.process.kill()
            raise e

    @abstractmethod
    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar=None):
        """抽象方法：子类必须实现具体的处理逻辑"""
        pass

    def run(self, input_dir: Path, out_dir: Path, monitor):
        """
        执行批处理
        
        :param input_dir: 输入目录
        :param out_dir: 输出目录
        """
        self.find_files(input_dir)

        if not self.files:
            logger.info("没有找到支持的文件")
            return
        
        # 确保输出目录存在
        out_dir.mkdir(parents=True, exist_ok=True)

        total = len(self.files)

        # 创建总进度条（仅在 CLI 模式下）
        overall_pbar = None
        if self.use_cli:
            try:
                from tqdm import tqdm as _tqdm
                overall_pbar = _tqdm(total=total, desc="总进度", unit="文件")
            except Exception:
                overall_pbar = None

        if monitor:
            monitor.update_overall_progress(0, total, f"准备就绪 ({total} 文件)")

        for idx, file_path in enumerate(self.files, start=1):

            if monitor and monitor.check_stop_flag():
                logger.info("收到停止请求，退出批处理循环。")
                break

            name = file_path.name
            output_path = out_dir / file_path.stem 

            logger.debug(f"总进度 ({idx}/{total})")

            if monitor:
                 # 使用 idx-1 作为当前已完成数
                 monitor.update_overall_progress(idx - 1, total, f"总进度 ({idx-1}/{total})")

            # 获取时长
            duration = self.get_duration(file_path)
            
            # 创建当前文件进度条（仅在 CLI 模式下）
            try:
                # 传递 monitor 实例
                self.process_file(
                    input_path=file_path, 
                    output_path=output_path, 
                    duration=duration, 
                    monitor=monitor # 新增 monitor 传递
                ) 
            except subprocess.CalledProcessError as e:
                # FFMPEG 失败，但我们不中断批处理
                logger.error(f"处理 {name} 失败 (错误码: {e.returncode}): {e.stderr}")
            except Exception as e:
                logger.exception(f"处理 {name} 时发生严重错误: {e}")
            finally:
                # 更新 GUI 总进度
                if monitor:
                    monitor.update_overall_progress(idx, total, f"总进度 ({idx}/{total})")

        current_completed = idx if monitor and monitor.check_stop_flag() else total

        if monitor and monitor.check_stop_flag():
             monitor.update_overall_progress(current_completed, total, "用户已停止转换.")
        else:
             monitor.update_overall_progress(total, total, "所有文件处理完成！")

        # log completion
        logger.info(f"批处理完成: {current_completed}/{total} 文件完成")

        

        if overall_pbar:
            overall_pbar.close()

class LogoConverter(MediaConverter):
    """
    添加logo并模糊背景
    """
    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        self.x = params.get('x', 10)
        self.y = params.get('y', 10)
        self.logo_w = params.get('logo_w', 100)
        self.logo_h = params.get('logo_h', 100)
        self.target_w = params.get('target_w', 1080)
        self.target_h = params.get('target_h', 1920)
        self.logo_path = get_resource_path(params.get('logo_path'))
        self.force_codec = params.get('video_codec', None)


        super().__init__(support_exts=support_exts, output_ext=output_ext, init_checks=init_checks)

        if not self.logo_path.exists():
            logger.critical(f"Logo 文件未找到: {self.logo_path}")
            raise FileNotFoundError(f"Logo not found: {self.logo_path}")

    def process_file(self, input_path: Path, output_path: Path, duration: float, monitor=None):
        """
        添加logo
        :param input_path: 输入路径
        :param output_path: 输出基本路径 (不含后缀)
        :param duration: 当前文件的总时长 (用于计算百分比)
        """
        output_file_name = f"{output_path}{self.output_ext}" 
        video_codec, preset_key, preset_value = self._get_video_codec_params(self.force_codec)

        # 构造 filter_complex：scale cover -> crop -> 模糊区域 -> overlay logo
        filter_complex = (
            f"[0:v]scale={self.target_w}:{self.target_h}:force_original_aspect_ratio=increase,crop={self.target_w}:{self.target_h},setsar=1[base];"
            f"[base]split=2[bg][tmp];"
            f"[tmp]crop={self.logo_w}:{self.logo_h}:{self.x}:{self.y},boxblur=10[blurred];"
            f"[bg][blurred]overlay={self.x}:{self.y}:format=auto[tmp2];"
            f"[1:v]scale={self.logo_w}:{self.logo_h}[logo];"
            f"[tmp2][logo]overlay={self.x}:{self.y}:format=auto[outv]"
        )

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-hwaccel", "auto",
            "-i", str(input_path), "-i", str(self.logo_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "0:a?", "-c:v", video_codec,
        ]
        # if preset_key == "-crf":
        #      # 软件编码器参数
        #      cmd.extend([preset_key, preset_value])
        # elif preset_key:
        #      # 硬件编码器参数 (如 -preset, -q:v)
        #      cmd.extend([preset_key, preset_value])
            
        cmd.extend([
            # "-c:a", "copy", "-movflags", "+faststart",
            output_file_name
        ])

        name = input_path.name # 确保获取到文件名
        self.process_ffmpeg(cmd, duration, monitor, name)

class AddCustomLogo(MediaConverter):
    """
    添加logo并模糊背景
    """
    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        self.x = params.get('x', 10)
        self.y = params.get('y', 10)
        self.text = params.get('text')
        self.font_color = params.get('font_color')
        self.font_size = params.get('font_size')
        self.font_path = params.get('font_path')


        super().__init__(support_exts=support_exts, output_ext=output_ext, init_checks=init_checks)

        if not get_resource_path(self.font_path).exists():
            logger.critical(f"字体未找到: {self.font_path}")
            raise FileNotFoundError(f"Logo not found: {self.font_path}")

    def process_file(self, input_path: Path, output_path: Path, duration: float, monitor=None):
        """
        添加logo
        :param input_path: 输入路径
        :param output_path: 输出基本路径 (不含后缀)
        :param duration: 当前文件的总时长 (用于计算百分比)
        """
        inpput_ext = input_path.suffix.lower()
        if self.output_ext is None:
            self.output_ext = f"_ai{inpput_ext}"

        output_file_name = f"{output_path}{self.output_ext}" 

        # 构造 filter_complex：
        filter_complex = (
            f"drawtext=fontfile='{self.font_path}':"
            f"text='{self.text}':"
            f"fontcolor={self.font_color}:"
            f"fontsize={self.font_size}:"
            "box=1:boxcolor=black@0.5:boxborderw=10:"
            f"x={self.x}:y={self.y}"
        )

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            "-vf", filter_complex,
            output_file_name
        ]

        name = input_path.name # 确保获取到文件名
        self.process_ffmpeg(cmd, duration, monitor, name)

class H264Converter(MediaConverter):
    """
    转换为H264
    """
    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        self.force_codec = params.get('video_codec', None)

        super().__init__(support_exts=support_exts, output_ext=output_ext, init_checks=init_checks)

    def process_file(self, input_path: Path, output_path: Path, duration: float, monitor=None):
        output_file_name = f"{output_path}{self.output_ext}"
        video_codec, preset_key, preset_value = self._get_video_codec_params(self.force_codec)
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-hwaccel", "auto",
            "-i", str(input_path),
            "-c:v", video_codec,
        ]
        # if preset_key == "-crf":
        #      cmd.extend([preset_key, preset_value])
        # elif preset_key:
        #      cmd.extend([preset_key, preset_value])
        
        cmd.extend([
            "-c:a", "copy", "-movflags", "+faststart",
            output_file_name
        ])
        name = input_path.name # 确保获取到文件名
        self.process_ffmpeg(cmd, duration, monitor, name)

class DnxhrConverter(MediaConverter):
    """
    转换为DNxHR
    """
    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        self.video_codec = params.get('video_codec', None)

        super().__init__(support_exts, output_ext, init_checks=init_checks)

    def process_file(self, input_path: Path, output_path: Path, duration: float, monitor=None):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            "-c:v", "dnxhd", "-profile:v", self.video_codec, "-c:a", "pcm_s16le",
            output_file_name
        ]
        name = input_path.name # 确保获取到文件名
        self.process_ffmpeg(cmd, duration, monitor, name)

class PngConverter(MediaConverter):
    """
    转换为PNG
    """

    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        super().__init__(support_exts, output_ext, init_checks=init_checks)

    def process_file(self, input_path: Path, output_path: Path, duration: float, monitor=None):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            "-c:v", "png", "-pix_fmt", "rgba",
            output_file_name
        ]
        name = input_path.name # 确保获取到文件名
        self.process_ffmpeg(cmd, duration, monitor, name)

class Mp3Converter(MediaConverter):
    """
    转换为MP3
    """

    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        super().__init__(support_exts, output_ext, init_checks=init_checks)
        
    def process_file(self, input_path: Path, output_path: Path, duration: float, monitor=None):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            output_file_name
        ]
        name = input_path.name # 确保获取到文件名
        self.process_ffmpeg(cmd, duration, monitor, name)

class WavConverter(MediaConverter):
    """
    转换为Wav
    """

    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        super().__init__(support_exts, output_ext, init_checks=init_checks)

    def process_file(self, input_path: Path, output_path: Path, duration: float, monitor):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            output_file_name
        ]
        name = input_path.name # 确保获取到文件名
        self.process_ffmpeg(cmd, duration, monitor, name)
