"""
视频批处理
依赖：ffmpeg, ffprobe 在 PATH 中

许可证声明：
本产品使用了 FFmpeg，其在 LGPL/GPL 下发布。
更多信息请参考项目的 README 文件。
"""
from pathlib import Path
import subprocess
from src.utils import get_resource_path, get_ffmpeg_exe, get_ffprobe_exe
from tqdm import tqdm 
import sys
from abc import ABC, abstractmethod

TARGET_W = 1080
TARGET_H = 1920


class MediaConverter(ABC):
    """
    视频转换器的抽象基类。负责文件I/O、依赖检查和FFMPEG执行。
    """
    # 默认扩展名
    DEFAULT_SUPPORT_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webp"}

    def __init__(self, support_exts=None, output_suffix: str = None):
        if support_exts is not None:
            final_exts = support_exts
        else:
            if hasattr(self, 'DEFAULT_SUPPORT_EXTS'):
                final_exts = self.DEFAULT_SUPPORT_EXTS
            else:
                final_exts = MediaConverter.DEFAULT_SUPPORT_EXTS
        self.files = []
        self.support_exts = set(final_exts)
        self.output_suffix = output_suffix if output_suffix else "_processed"
        self._check_ffmpeg_path()

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
            return float(out) if out else 1.0
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

        file_pct = 0.0
        overall_pct = 0.0
        
        # 用于在失败时报告错误
        error_output = []

        try:
            # 实时读取 stdout 上的进度
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                
                # 解析 ffmpeg -progress 的 key=value
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k in ("out_time_ms", "out_time_us"):
                        try:
                            us = int(v)
                            seconds = us / 1_000_000.0
                        except Exception:
                            seconds = 0.0
                        file_pct = min(100.0, (seconds / duration) * 100.0)
                    elif k == "out_time":
                        try:
                            if '.' in ss:
                                ss, _ = ss.split('.', 1)
                                hh, mm, ss = v.split(":")
                                seconds = int(hh) * 3600 + int(mm) * 60 + float(ss)
                                file_pct = min(100.0, (seconds / duration) * 100.0)
                        except Exception:
                            pass
                    elif k == "progress" and v == "end":
                        file_pct = 100.0

                    if file_pct > 0:
                        # 更新 TQDM 进度条
                        file_pbar.n = int(file_pct)
                        file_pbar.refresh()

            # 等待进程结束
            proc.wait()
            # 读取所有剩余的 stderr 输出
            stderr_data = proc.stderr.read()
            if stderr_data:
                error_output.append(stderr_data)

        finally:
            # 确保在任何情况下（即使是异常）进程都被正确处理
            if proc.poll() is None:
                proc.kill()
                # 再次读取 stderr 确保捕获所有信息
                stderr_data = proc.stderr.read()
                if stderr_data:
                    error_output.append(stderr_data)

        file_pbar.n = 100
        file_pbar.refresh()

        # 检查 FFMPEG 是否成功执行
        if proc.returncode != 0:
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

        for idx, file_path in enumerate(self.files, start=1):
            name = file_path.name
            output_path = out_dir / file_path.stem 

            # 打印当前文件信息，并刷新总进度条
            overall_pbar.set_description(f"总进度 ({idx}/{total})")

            # 获取时长
            duration = self.get_duration(file_path)
            
            # 创建当前文件进度条
            file_pbar = tqdm(total=100, desc=f"{name[:30]:<30}", unit="%", leave=False)

            try:
                self.process_file(
                    input_path=file_path, 
                    output_path=output_path, 
                    duration=duration, 
                    file_pbar=file_pbar
                ) 
            except Exception as e:
                print(f"\n处理 {name} 时发生严重错误: {e}", file=sys.stderr)
            finally:
                file_pbar.close() # 确保文件进度条被关闭
                overall_pbar.update(1) # 更新总进度条

        overall_pbar.close()


class LogoConverter(MediaConverter):
    """
    添加logo并模糊背景
    """
    def __init__(self, params: dict, support_exts=None, output_suffix: str = None):
        self.x = params.get('x', 10)
        self.y = params.get('y', 10)
        self.logo_w = params.get('logo_w', 100)
        self.logo_h = params.get('logo_h', 100)
        self.target_w = params.get('target_w')
        self.target_h = params.get('target_h')
        self.logo_path = get_resource_path(params.get('logo_path'))

        super().__init__(support_exts, output_suffix)

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
        output_file_name = f"{output_path}{self.output_suffix}"

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
            "-i", str(input_path), "-i", str(self.logo_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "0:a?", "-c:v", "libx264", "-crf", "20",
            "-preset", "medium", "-c:a", "copy", "-movflags", "+faststart",
            "-progress", "pipe:1", output_file_name
        ]
        
        self.process_ffmpeg(cmd, duration, file_pbar)

class H264Converter(MediaConverter):
    """
    转换为H264
    """
    def __init__(self, support_exts=None, output_suffix: str = None):
        super().__init__(support_exts, output_suffix)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_suffix}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            "-c:v", "libx264", "-crf", "20",
            "-preset", "medium", "-c:a", "copy", "-movflags", "+faststart",
            "-progress", "pipe:1", output_file_name
        ]
        self.process_ffmpeg(cmd, duration, file_pbar)

class DnxhrConverter(MediaConverter):
    """
    转换为DNxHR
    """
    def __init__(self, params: dict, support_exts=None, output_suffix: str = None):
        super().__init__(support_exts, output_suffix)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_suffix}"
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

    def __init__(self, params: dict, support_exts=None, output_suffix: str = None):
        super().__init__(support_exts, output_suffix)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_suffix}"
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

    def __init__(self, params: dict, support_exts=None, output_suffix: str = None):
        super().__init__(support_exts, output_suffix)
        
    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_suffix}"
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

    def __init__(self, params: dict, support_exts=None, output_suffix: str = None):
        super().__init__(support_exts, output_suffix)

    def process_file(self, input_path: Path, output_path: Path, duration: float, file_pbar: tqdm):
        output_file_name = f"{output_path}{self.output_suffix}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
            "-i", str(input_path),
            "-progress", "pipe:1", output_file_name
        ]
        self.process_ffmpeg(cmd, duration, file_pbar)


