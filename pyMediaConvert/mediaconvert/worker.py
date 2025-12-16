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
from tqdm import tqdm
from abc import ABC, abstractmethod
import re
import tempfile
import os
import time

logger = get_logger(__name__)


# 用于存储 app.py 传递进来的 ProgressMonitor 实例
GlobalProgressMonitor = None

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
        self.output_ext = output_ext if output_ext else ".mp4"

        self.available_encoders = {}
        self.use_cli = bool(use_cli)

        # Only run heavy checks if requested (GUI file-count helper will pass init_checks=False)
        if init_checks:
            self._check_ffmpeg_path()
            self._detect_hardware_encoders()
    

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
        try:
            result = subprocess.run(cmd, 
                                    capture_output=True, 
                                    text=True, 
                                    check=True, 
                                    encoding='utf-8', 
                                    errors='ignore')
            
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
    
    def get_duration(self, path: Path) -> float:
        """
        使用ffmpore获取时长
        """
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
            return round(float(out), 2) if out else 1.0
        except Exception:
            return 1.0
          
    def process_ffmpeg(self, cmd: list, duration: float, file_pbar: tqdm, input_file_name: str):
        """
        执行 FFMPEG 命令并解析 -progress 输出。
        修复了 Nuitka 打包后因管道缓冲导致进度条不刷新的问题。
        """
        cmd[0] = get_ffmpeg_exe()

        last_seconds = 0.0
        error_output = []
        stopped_by_user = False

        # 构造命令：使用 stdout (pipe:1) 输出进度
        # 移除原命令可能存在的 -progress 或 pipe:1，防止重复
        final_cmd = [c for c in cmd if c != "-progress" and c != "pipe:1"]
        final_cmd.extend(["-progress", "pipe:1"])

        proc = None
        try:
            # 关键修改 1: 移除 text=True, bufsize=1, encoding='utf-8'
            # 关键修改 2: 添加 stdin=subprocess.DEVNULL (防止 ffmpeg 在后台等待输入导致卡死)
            # 使用二进制模式启动进程
            proc = subprocess.Popen(
                final_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, 
            )

            # 关键修改 3: 使用二进制 readline() 循环
            while True:
                # readline 在二进制模式下读取直到 \n，通常不受全缓冲影响（只要发送方发送了 \n）
                raw_line = proc.stdout.readline()
                
                # 如果读到空字节且进程已结束，则跳出
                if not raw_line:
                    if proc.poll() is not None:
                        break
                    continue

                # 手动解码，忽略解码错误以保证稳定性
                line = raw_line.decode('utf-8', errors='ignore').strip()
                
                if not line:
                    continue

                # --- 停止检查 ---
                if GlobalProgressMonitor and GlobalProgressMonitor.check_stop_flag():
                    logger.info("用户请求停止，终止 FFMPEG 进程")
                    try:
                        if proc.poll() is None:
                            proc.kill()
                            stopped_by_user = True
                            # 稍微等待一下确保进程退出
                            try:
                                proc.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                pass
                    except Exception as e:
                        logger.exception(f"终止 FFMPEG 进程时出错: {e}")
                    break

                # --- 解析逻辑 (与之前相同) ---
                seconds = 0.0
                if "=" in line:
                    try:
                        k, v = line.split("=", 1)
                        # 清理可能的空白字符
                        k = k.strip()
                        v = v.strip()

                        if k == "out_time_us":
                            seconds = int(v) / 1_000_000.0
                        elif k == "out_time_ms":
                            seconds = int(v) / 1_000.0
                        elif k == "out_time":
                            # 格式如 00:00:05.123
                            parts = v.split(":")
                            if len(parts) == 3:
                                hh, mm, ss = parts
                                seconds = int(hh) * 3600 + int(mm) * 60 + float(ss)
                        elif k == "progress" and v == "end":
                            seconds = duration
                        
                        seconds = round(seconds, 2)
                        
                        # 只有当进度确实前进时才更新，减少信号发射频率
                        if seconds > last_seconds and seconds <= duration:
                            delta_seconds = seconds - last_seconds
                            
                            # 只有增量大于 0 才更新
                            if delta_seconds > 0:
                                if file_pbar:
                                    file_pbar.update(delta_seconds)
                                last_seconds = seconds
                                
                                # 更新 GUI
                                if GlobalProgressMonitor:
                                    name = (getattr(file_pbar, 'desc', '') or '').strip('🎬 ')
                                    # 此时 input_file_name 是可用的，优先使用
                                    display_name = input_file_name if input_file_name else name
                                    GlobalProgressMonitor.update_file_progress(last_seconds, duration, display_name.strip())

                        if k == "progress" and v == "end":
                            break
                    except ValueError:
                        continue
                    except Exception:
                        # 防止解析单行出错导致整个循环崩溃
                        continue

            # 等待进程完全结束
            proc.wait()
            
            # 读取错误输出 (如果有)
            stderr_data = proc.stderr.read()
            if stderr_data:
                # 二进制转文本
                decoded_err = stderr_data.decode('utf-8', errors='ignore')
                if decoded_err.strip():
                    error_output.append(decoded_err)

        except Exception as e:
            logger.exception(f"处理 FFMPEG 进程失败: {e}")
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
            raise e

        finally:
            # 确保清理
            if proc and proc.poll() is None and not stopped_by_user:
                try:
                    proc.kill()
                    stderr_data = proc.stderr.read()
                    if stderr_data:
                        error_output.append(stderr_data.decode('utf-8', errors='ignore'))
                except Exception:
                    pass

        # 确保进度条走完
        if file_pbar:
            remain = duration - file_pbar.n
            if remain > 0:
                file_pbar.update(remain)
        
        if GlobalProgressMonitor:
            GlobalProgressMonitor.update_file_progress(duration, duration, input_file_name)

        # 检查返回值
        if proc.returncode != 0 and not stopped_by_user:
            full_error = "\n".join(error_output).strip()
            raise subprocess.CalledProcessError(
                proc.returncode,
                cmd,
                output=None,
                stderr=full_error
            )

    @abstractmethod
    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        """抽象方法：子类必须实现具体的处理逻辑"""
        pass

    def run(self, input_dir: Path, out_dir: Path):
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

        if GlobalProgressMonitor:
            GlobalProgressMonitor.update_overall_progress(0, total, f"准备就绪 ({total} 文件)")

        for idx, file_path in enumerate(self.files, start=1):

            if GlobalProgressMonitor and GlobalProgressMonitor.check_stop_flag():
                logger.info("收到停止请求，退出批处理循环。")
                break

            name = file_path.name
            output_path = out_dir / file_path.stem 

            # 打印当前文件信息，并刷新总进度条
            if overall_pbar:
                try:
                    overall_pbar.set_description(f"总进度 ({idx}/{total})")
                except Exception:
                    logger.debug("无法设置 overall_pbar 描述。可能是终端不可用。")
            else:
                # 在 GUI 模式下记录信息，GUI 将通过 monitor 接收更新
                logger.debug(f"总进度 ({idx}/{total})")

            if GlobalProgressMonitor:
                 # 使用 idx-1 作为当前已完成数
                 GlobalProgressMonitor.update_overall_progress(idx - 1, total, f"总进度 ({idx-1}/{total})")

            # 获取时长
            duration = self.get_duration(file_path)
            
            # 创建当前文件进度条（仅在 CLI 模式下）
            file_pbar = None
            if self.use_cli:
                try:
                    from tqdm import tqdm as _tqdm
                    file_pbar = _tqdm(total=duration, desc=f"🎬 {name[:30]:<30}", unit="s", leave=False, dynamic_ncols=True)
                except Exception:
                    file_pbar = None

            try:
                self.process_file(
                    input_path=file_path, 
                    output_path=output_path, 
                    duration=duration, 
                    file_pbar=file_pbar
                ) 
            except subprocess.CalledProcessError as e:
                # FFMPEG 失败，但我们不中断批处理
                logger.error(f"处理 {name} 失败 (错误码: {e.returncode}): {e.stderr}")
            except Exception as e:
                logger.exception(f"处理 {name} 时发生严重错误: {e}")
            finally:
                if file_pbar:
                    file_pbar.close() # 确保文件进度条被关闭
                if overall_pbar:
                    overall_pbar.update(1) # 更新总进度条 (即使失败也算处理完成)
                # 更新 GUI 总进度
                if GlobalProgressMonitor:
                    GlobalProgressMonitor.update_overall_progress(idx, total, f"总进度 ({idx}/{total})")

        current_completed = overall_pbar.n if overall_pbar else total

        if GlobalProgressMonitor and GlobalProgressMonitor.check_stop_flag():
             GlobalProgressMonitor.update_overall_progress(current_completed, total, "用户已停止转换.")
        else:
             GlobalProgressMonitor.update_overall_progress(total, total, "所有文件处理完成！")

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

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
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
        self.process_ffmpeg(cmd, duration, file_pbar, name)

class H264Converter(MediaConverter):
    """
    转换为H264
    """
    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        self.force_codec = params.get('video_codec', None)

        super().__init__(support_exts=support_exts, output_ext=output_ext, init_checks=init_checks)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
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
        self.process_ffmpeg(cmd, duration, file_pbar, name)

class DnxhrConverter(MediaConverter):
    """
    转换为DNxHR
    """
    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        self.video_codec = params.get('video_codec', None)

        super().__init__(support_exts, output_ext, init_checks=init_checks)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            "-c:v", "dnxhd", "-profile:v", self.video_codec, "-c:a", "pcm_s16le",
            output_file_name
        ]
        name = input_path.name # 确保获取到文件名
        self.process_ffmpeg(cmd, duration, file_pbar, name)

class PngConverter(MediaConverter):
    """
    转换为PNG
    """

    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        super().__init__(support_exts, output_ext, init_checks=init_checks)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            "-c:v", "png", "-pix_fmt", "rgba",
            output_file_name
        ]
        name = input_path.name # 确保获取到文件名
        self.process_ffmpeg(cmd, duration, file_pbar, name)

class Mp3Converter(MediaConverter):
    """
    转换为MP3
    """

    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        super().__init__(support_exts, output_ext, init_checks=init_checks)
        
    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            output_file_name
        ]
        name = input_path.name # 确保获取到文件名
        self.process_ffmpeg(cmd, duration, file_pbar, name)

class WavConverter(MediaConverter):
    """
    转换为Wav
    """

    def __init__(self, params: dict, support_exts=None, output_ext: str = None, init_checks: bool = True):
        super().__init__(support_exts, output_ext, init_checks=init_checks)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            output_file_name
        ]
        name = input_path.name # 确保获取到文件名
        self.process_ffmpeg(cmd, duration, file_pbar, name)


