"""
视频批处理
依赖：ffmpeg, ffprobe 在 PATH 中

许可证声明：
本产品使用了 FFmpeg，其在 LGPL/GPL 下发布。
更多信息请参考项目的 README 文件。
"""
from pathlib import Path
import subprocess
from utils import get_resource_path, get_ffmpeg_exe, get_ffprobe_exe
from tqdm import tqdm 
import sys
from abc import ABC, abstractmethod
import re

# 用于存储 app.py 传递进来的 ProgressMonitor 实例
GlobalProgressMonitor = None

class MediaConverter(ABC):
    """
    视频转换器的抽象基类。负责文件I/O、依赖检查和FFMPEG执行。
    """
    # 默认扩展名
    DEFAULT_SUPPORT_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}

    def __init__(self, support_exts=None, output_ext: str = None):
        if support_exts is not None:
            final_exts = support_exts
        else:
            if hasattr(self, 'DEFAULT_SUPPORT_EXTS'):
                final_exts = self.DEFAULT_SUPPORT_EXTS
            else:
                final_exts = MediaConverter.DEFAULT_SUPPORT_EXTS
        self.files = []
        self.support_exts = set(final_exts)
        self.output_ext = output_ext if output_ext else ".mp4"

        self.available_encoders = {}

        self._check_ffmpeg_path()
        self._detect_hardware_encoders()
    

    def _check_ffmpeg_path(self):
        """检查捆绑的 ffmpeg 和 ffprobe 文件是否存在"""
        # 注意：这里使用 get_ffmpeg_exe() 返回的路径，在运行时是绝对路径
        ffmpeg_path = Path(get_ffmpeg_exe())
        ffprobe_path = Path(get_ffprobe_exe())
        
        if not ffmpeg_path.exists():
            print(f"致命错误：捆绑的 ffmpeg 可执行文件未找到: {ffmpeg_path}", file=sys.stderr)
            sys.exit(1)
        if not ffprobe_path.exists():
            print(f"致命错误：捆绑的 ffprobe 可执行文件未找到: {ffprobe_path}", file=sys.stderr)
            sys.exit(1)

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
            tqdm.write(f"⚠️ 无法运行 FFmpeg -encoders。错误: {e.stderr.strip()}")
        except Exception as e:
            tqdm.write(f"⚠️ 编码器检测过程中发生未知错误: {e}")

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
        遍历文件
        """
        self.files = sorted([p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in self.support_exts])
    
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
          
    def process_ffmpeg(self, cmd: list, duration: float, file_pbar: tqdm):
        """
        执行 FFMPEG 命令并解析 -progress 输出。
        
        :param cmd: 要执行的 FFMPEG 命令 (list[str])
        :param duration: 当前文件的总时长 (用于计算百分比)
        :param file_pbar: TQDM 实例 (total=100)，用于更新文件进度
        """
        # FFMPEG -progress pipe:1 会将进度发到 stdout
        # FFMPEG -loglevel error 会将错误发到 stderr
        # stderr=subprocess.PIPE 将捕获错误
        cmd[0] = get_ffmpeg_exe()

        proc = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,  # 单独捕获 stderr
            text=True, 
            bufsize=1,
            encoding='utf-8' # 确保文本模式
        )

        # file_pct = 0.0
        # overall_pct = 0.0
        last_seconds = 0.0
        
        # 用于在失败时报告错误
        error_output = []

        try:
            # 实时读取 stdout 上的进度
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                seconds = 0.0
                # --- 停止检查 ---
                if GlobalProgressMonitor and GlobalProgressMonitor.check_stop_flag():
                    tqdm.write("ℹ️ 转换被用户中断。终止 FFMPEG 进程...")
                    break # 跳出循环，进入 finally 块并终止 FFMPEG
                # 解析 ffmpeg -progress 的 key=value
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k in ("out_time_ms", "out_time_us"):
                        try:
                            us = int(v)
                            seconds = us / 1_000_000.0
                        except Exception:
                            seconds = 0.0
                        # file_pct = min(100.0, (seconds / duration) * 100.0)
                    elif k == "out_time":
                        try:
                            # if '.' in ss:
                                # ss, _ = ss.split('.', 1)
                            hh, mm, ss = v.split(":")
                            seconds = int(hh) * 3600 + int(mm) * 60 + float(ss)
                                # file_pct = min(100.0, (seconds / duration) * 100.0)
                        except Exception:
                            pass
                    elif k == "progress" and v == "end":
                        seconds = duration
                        
                    seconds = round(seconds, 2)

                    # if file_pct > 0:
                    #     # 更新 TQDM 进度条
                    #     file_pbar.n = int(file_pct)
                    #     file_pbar.refresh()
                    if seconds > last_seconds and seconds <= duration:
                        delta_seconds = seconds - last_seconds
                        
                        file_pbar.update(delta_seconds)
                        
                        last_seconds = seconds

                        if GlobalProgressMonitor:
                            name = file_pbar.desc.strip('🎬 ')
                            GlobalProgressMonitor.update_file_progress(seconds, duration, name.strip())
                        
                    if k == "progress" and v == "end":
                        break

            # 等待进程结束
            proc.wait()
            # 读取所有剩余的 stderr 输出
            stderr_data = proc.stderr.read()
            if stderr_data:
                error_output.append(stderr_data)

        finally:
            # 确保在任何情况下（即使是异常）进程都被正确处理
            if proc.poll() is None or (GlobalProgressMonitor and GlobalProgressMonitor.check_stop_flag()):
                proc.kill()
                tqdm.write(f"进程 {proc.pid} 已被终止.")
                # 再次读取 stderr 确保捕获所有信息
                stderr_data = proc.stderr.read()
                if stderr_data:
                    error_output.append(stderr_data)

        # file_pbar.n = 100
        # file_pbar.refresh()
        file_pbar.update(duration - file_pbar.n)

        # 检查 FFMPEG 是否成功执行
        if proc.returncode != 0 and (not GlobalProgressMonitor or not GlobalProgressMonitor.check_stop_flag()):
            full_error = "\n".join(error_output).strip()
            # 抛出一个更信息化的异常
            raise subprocess.CalledProcessError(
                proc.returncode,
                cmd,
                output=None, # stdout 已被我们消耗
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
            print("没有找到支持的文件")
            return
        
        # 确保输出目录存在
        out_dir.mkdir(parents=True, exist_ok=True)

        total = len(self.files)

        # 创建总进度条
        overall_pbar = tqdm(total=total, desc="总进度", unit="文件")

        if GlobalProgressMonitor:
            GlobalProgressMonitor.update_overall_progress(0, total, f"准备就绪 ({total} 文件)")

        for idx, file_path in enumerate(self.files, start=1):

            if GlobalProgressMonitor and GlobalProgressMonitor.check_stop_flag():
                tqdm.write("ℹ️ 收到停止请求，退出批处理循环。")
                break

            name = file_path.name
            output_path = out_dir / file_path.stem 

            # 打印当前文件信息，并刷新总进度条
            overall_pbar.set_description(f"总进度 ({idx}/{total})")

            if GlobalProgressMonitor:
                 # 使用 idx-1 作为当前已完成数
                 GlobalProgressMonitor.update_overall_progress(idx - 1, total, f"总进度 ({idx-1}/{total})")

            # 获取时长
            duration = self.get_duration(file_path)
            
            # 创建当前文件进度条
            file_pbar = tqdm(total=duration, desc=f"🎬 {name[:30]:<30}", unit="s", leave=False, dynamic_ncols=True)

            try:
                self.process_file(
                    input_path=file_path, 
                    output_path=output_path, 
                    duration=duration, 
                    file_pbar=file_pbar
                ) 
            except subprocess.CalledProcessError as e:
                # FFMPEG 失败，但我们不中断批处理
                tqdm.write(f"\n❌ 处理 {name} 失败 (错误码: {e.returncode}): {e.stderr}", file=sys.stderr)
            except Exception as e:
                tqdm.write(f"\n❌ 处理 {name} 时发生严重错误: {e}", file=sys.stderr)
            finally:
                file_pbar.close() # 确保文件进度条被关闭
                overall_pbar.update(1) # 更新总进度条 (即使失败也算处理完成)

        current_completed = overall_pbar.n

        if GlobalProgressMonitor and GlobalProgressMonitor.check_stop_flag():
             GlobalProgressMonitor.update_overall_progress(current_completed, total, "用户已停止转换.")
        else:
             GlobalProgressMonitor.update_overall_progress(total, total, "所有文件处理完成！")

        

        overall_pbar.close()


class LogoConverter(MediaConverter):
    """
    添加logo并模糊背景
    """
    def __init__(self, params: dict, support_exts=None, output_ext: str = None):
        self.x = params.get('x', 10)
        self.y = params.get('y', 10)
        self.logo_w = params.get('logo_w', 100)
        self.logo_h = params.get('logo_h', 100)
        self.target_w = params.get('target_w', 1080)
        self.target_h = params.get('target_h', 1920)
        self.logo_path = get_resource_path(params.get('logo_path'))

        super().__init__(support_exts=support_exts, output_ext=output_ext)

        if not self.logo_path.exists():
            print(f"错误：Logo 文件未找到: {self.logo_path}", file=sys.stderr)
            sys.exit(1)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        """
        添加logo
        :param input_path: 输入路径
        :param output_path: 输出基本路径 (不含后缀)
        :param duration: 当前文件的总时长 (用于计算百分比)
        """
        output_file_name = f"{output_path}{self.output_ext}" 
        video_codec, preset_key, preset_value = self._get_video_codec_params()

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
            "-progress", "pipe:1", output_file_name
        ])

        self.process_ffmpeg(cmd, duration, file_pbar)

class H264Converter(MediaConverter):
    """
    转换为H264
    """
    def __init__(self, params: dict, support_exts=None, output_ext: str = None):
        super().__init__(support_exts=support_exts, output_ext=output_ext)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_ext}"
        video_codec, preset_key, preset_value = self._get_video_codec_params()
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
            "-progress", "pipe:1", output_file_name
        ])
        self.process_ffmpeg(cmd, duration, file_pbar)

class DnxhrConverter(MediaConverter):
    """
    转换为DNxHR
    """
    def __init__(self, params: dict, support_exts=None, output_ext: str = None):
        super().__init__(support_exts, output_ext)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            "-c:v", "dnxhd", "-profile:v", "dnxhr_hq", "-c:a", "pcm_s16le",
            "-progress", "pipe:1", output_file_name
        ]
        self.process_ffmpeg(cmd, duration, file_pbar)

class PngConverter(MediaConverter):
    """
    转换为PNG
    """
    DEFAULT_SUPPORT_EXTS = {".jpg", ".bmp", ".png", ".webp", ".tiff"}

    def __init__(self, params: dict, support_exts=None, output_ext: str = None):
        super().__init__(support_exts, output_ext)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            "-c:v", "png", "-pix_fmt", "rgba",
            "-progress", "pipe:1", output_file_name
        ]
        self.process_ffmpeg(cmd, duration, file_pbar)

class Mp3Converter(MediaConverter):
    """
    转换为MP3
    """
    DEFAULT_SUPPORT_EXTS = ['.mp3', '.wav', '.flac', '.ogg', '.mpeg', '.m4a', '.aiff']

    def __init__(self, params: dict, support_exts=None, output_ext: str = None):
        super().__init__(support_exts, output_ext)
        
    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            "-progress", "pipe:1", output_file_name
        ]
        self.process_ffmpeg(cmd, duration, file_pbar)

class WavConverter(MediaConverter):
    """
    转换为Wav
    """
    DEFAULT_SUPPORT_EXTS = ['.mp3', '.wav', '.flac', '.ogg', '.mpeg', '.m4a', '.aiff']

    def __init__(self, params: dict, support_exts=None, output_ext: str = None):
        super().__init__(support_exts, output_ext)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_ext}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            "-progress", "pipe:1", output_file_name
        ]
        self.process_ffmpeg(cmd, duration, file_pbar)


