"""
视频场景切分、截图与分割工具

核心能力:
- 使用 OpenCV+自适应阈值 的内容检测算法探测场景切换点，兼顾硬切与部分叠化/渐变转场。
- 当运行环境缺少 OpenCV 时，自动回退到 FFmpeg 的 scene 过滤器以保持兼容性。
- 在每个切换点生成截图，并按场景分割成独立视频文件。
- 可选为输出的视频或图片添加自定义文字水印。
- Windows 下隐藏 ffmpeg 进程窗口。
- 支持日志文件记录和调试模式。
"""

import subprocess
import os
import re
import argparse
import sys
from pathlib import Path
from datetime import datetime

from ..utils import get_ffmpeg_exe, get_ffprobe_exe, get_resource_path
from ..logging_config import get_logger

logger = get_logger(__name__)

try:
    import cv2
    import numpy as np
except Exception:  # OpenCV 是可选依赖，加载失败时回退到 FFmpeg 检测
    cv2 = None
    np = None


def get_available_fonts() -> dict:
    """
    扫描 assets 目录，获取所有可用的 TTF 字体文件
    返回字典: {字体名称: 相对路径}
    例如: {"Roboto-Bold": "assets/Roboto-Bold.ttf"}
    """
    fonts = {}
    assets_dir = get_resource_path("assets")
    
    if not assets_dir.exists():
        logger.warning(f"assets 目录不存在: {assets_dir}")
        return fonts
    
    try:
        for font_file in assets_dir.glob("*.ttf"):
            font_name = font_file.stem  # 获取不带扩展名的文件名
            # 返回相对路径
            fonts[font_name] = f"assets/{font_file.name}"
        
        if fonts:
            logger.info(f"发现 {len(fonts)} 个字体: {', '.join(fonts.keys())}")
        else:
            logger.warning("assets 目录中未找到 TTF 字体文件")
    except Exception as e:
        logger.error(f"扫描字体文件时发生错误: {e}")
    
    return fonts


def _get_video_duration(file_path: Path, debug: bool = False) -> float:
    """使用 ffprobe 安全地获取视频时长"""
    ffprobe_exe = get_ffprobe_exe()
    cmd = [
        ffprobe_exe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    
    # Windows 下隐藏 cmd 窗口
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


def get_video_fps(video_path, debug: bool = False):
    """获取视频帧率，用于计算偏移时间"""
    cmd = [
        get_ffmpeg_exe(), '-i', str(video_path),
        '-an', '-f', 'null', '-'
    ]
    
    # Windows 下隐藏 cmd 窗口
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
    
    if debug:
        logger.debug(f"执行 ffmpeg 命令获取帧率: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8',
                           creationflags=creationflags)
    # 从输出中匹配 fps，例如 "23.98 fps"
    match = re.search(r"(\d+(\.\d+)?) fps", result.stderr)
    fps = float(match.group(1)) if match else 25.0
    
    if debug:
        logger.debug(f"视频帧率: {fps} FPS")
    
    return fps


class SceneCutter:
    def __init__(self, monitor=None, debug: bool = False, log_dir: Path = None, font_name: str = None):
        self.monitor = monitor
        self.files = []
        self.debug = debug
        self.log_dir = log_dir
        self.font_name = font_name
        
        # 加载可用的字体
        self.available_fonts = get_available_fonts()
        
        # 验证选择的字体是否存在
        if self.font_name and self.font_name not in self.available_fonts:
            logger.warning(f"字体 '{self.font_name}' 未找到，可用字体: {', '.join(self.available_fonts.keys())}")
            self.font_name = None
        
        if self.debug and self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"调试模式已启用，日志将保存至: {self.log_dir}")

    def _log_command(self, cmd: list, log_file: Path = None):
        """记录 FFmpeg 命令到日志文件（调试用）"""
        if not self.debug:
            return
        
        cmd_str = " ".join(str(c) for c in cmd)
        logger.debug(f"执行命令: {cmd_str}")
        
        if log_file and self.log_dir:
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().isoformat()}] 命令: {cmd_str}\n")
            except Exception as e:
                logger.warning(f"无法写入调试日志: {e}")

    def _execute_ffmpeg_command(self, cmd: list, debug_log_file: Path = None) -> tuple[bool, str]:
        """
        执行FFmpeg命令并捕获错误
        返回: (success, stderr_output)
        """
        # Windows 下隐藏 cmd 窗口
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
        
        self._log_command(cmd, debug_log_file)
        
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                creationflags=creationflags,
                check=False  # 不自动抛异常，手动检查返回码
            )
            
            # 记录详细输出
            if self.debug and debug_log_file:
                with open(debug_log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().isoformat()}] 返回码: {process.returncode}\n")
                    if process.stdout:
                        f.write(f"STDOUT: {process.stdout[:500]}\n")
                    if process.stderr:
                        f.write(f"STDERR: {process.stderr[:500]}\n")
            
            if process.returncode != 0:
                error_msg = process.stderr or process.stdout or "未知错误"
                logger.error(f"FFmpeg 命令失败 (返回码: {process.returncode}): {error_msg[:200]}")
                return False, error_msg
            
            return True, process.stderr
            
        except Exception as e:
            logger.exception(f"执行FFmpeg命令时发生异常: {e}")
            if debug_log_file:
                with open(debug_log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().isoformat()}] 异常: {str(e)}\n")
            return False, str(e)

    # === 场景检测相关辅助方法 ===

    def _detect_scenes_ffmpeg(
        self,
        video_path: Path,
        threshold: float,
        debug_log_file: Path | None = None,
    ) -> list[float]:
        """
        使用 FFmpeg 的 scene 过滤器进行场景检测，作为 OpenCV 不可用时的回退方案。

        返回值:
            已包含 0.0 起始点的时间戳列表（单位: 秒），未做帧对齐。
        """
        cmd_detect = [
            get_ffmpeg_exe(), '-i', str(video_path),
            '-filter_complex', f"select='gt(scene,{threshold})',showinfo",
            '-f', 'null', '-',
        ]

        logger.info(f"正在使用 FFmpeg scene 过滤器分析场景 (阈值: {threshold})...")
        success, stderr_output = self._execute_ffmpeg_command(cmd_detect, debug_log_file)

        if not success:
            logger.error(f"FFmpeg 场景检测失败: {stderr_output[:200]}")
            return [0.0]

        scene_times = [0.0]
        times = re.findall(r"pts_time:([\d\.]+)", stderr_output)
        scene_times.extend([float(t) for t in times])

        if self.debug and debug_log_file:
            with open(debug_log_file, "a", encoding="utf-8") as f:
                f.write("FFmpeg 场景检测结果 (未对齐):\n")
                f.write(f"  检测到 {len(scene_times)} 个分段\n")
                f.write(f"  原始时间点: {scene_times}\n\n")

        return scene_times

    def _detect_scenes_opencv(
        self,
        video_path: Path,
        threshold: float,
        fps: float,
        debug_log_file: Path | None = None,
    ) -> list[float]:
        """
        使用 OpenCV 基于帧内容的自适应检测算法进行场景切分。

        设计要点:
        - 采用帧间灰度均值差作为快速内容变化指标，兼顾性能和鲁棒性。
        - 使用指数滑动平均 (EMA) 自适应基线，适应整段视频亮度/对比度变化。
        - “敏感度”由 threshold 控制，输入区间 0~1，内部映射为倍数因子。
          0.2 左右为较合适的默认值，与原 UI 含义保持一致。
        - 对于叠化/渐变转场，虽然单帧差值不一定极高，但在一个短时间窗口内
          会出现连续高值，算法通过聚合和去抖处理，将其合并为单一场景边界。
        """
        if cv2 is None or np is None:
            raise RuntimeError("OpenCV 未安装，无法使用基于 OpenCV 的场景检测。")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频文件: {video_path}")

        # 将 UI 中的 [0,1] 阈值映射到一个合理的灵敏度区间:
        # 数值越小越敏感；这里将其映射到 [1.5, 4.0] 的倍数因子。
        sensitivity = max(0.0, min(1.0, threshold))
        factor_min, factor_max = 1.5, 4.0
        factor = factor_max - (factor_max - factor_min) * sensitivity  # threshold 越大越不敏感

        ema_score = None
        alpha = 0.15  # EMA 衰减系数
        frame_index = 0
        prev_gray = None
        raw_candidates: list[float] = [0.0]

        # 用于处理渐变/叠化: 连续高分帧聚合
        high_span_start = None
        high_span_peak_score = 0.0
        high_span_peak_frame = None

        if self.debug and debug_log_file:
            with open(debug_log_file, "a", encoding="utf-8") as f:
                f.write("OpenCV 场景检测开始...\n")
                f.write(f"  sensitivity(threshold): {threshold}\n")
                f.write(f"  factor: {factor}\n")
                f.write("\n")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                # 下采样以加速计算
                h, w = gray.shape
                scale = 320.0 / max(w, h)
                if scale < 1.0:
                    gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

                if prev_gray is None:
                    prev_gray = gray
                    frame_index += 1
                    continue

                diff = cv2.absdiff(gray, prev_gray)
                score = float(diff.mean())

                if ema_score is None:
                    ema_score = score
                else:
                    ema_score = (1 - alpha) * ema_score + alpha * score

                # 当前帧被视为“高变化”帧的条件
                dynamic_threshold = ema_score * factor
                is_high = score > dynamic_threshold

                if is_high:
                    if high_span_start is None:
                        high_span_start = frame_index
                        high_span_peak_score = score
                        high_span_peak_frame = frame_index
                    else:
                        if score > high_span_peak_score:
                            high_span_peak_score = score
                            high_span_peak_frame = frame_index
                else:
                    # 一个高变化窗口结束，聚合为一个候选切点
                    if high_span_start is not None and high_span_peak_frame is not None:
                        cut_time = high_span_peak_frame / fps
                        raw_candidates.append(cut_time)
                        if self.debug and debug_log_file:
                            with open(debug_log_file, "a", encoding="utf-8") as f:
                                f.write(
                                    f"[OpenCV] 高变化窗口: {high_span_start}->{frame_index}, "
                                    f"peak_frame={high_span_peak_frame}, time={cut_time:.3f}s, "
                                    f"score={high_span_peak_score:.3f}, ema={ema_score:.3f}, "
                                    f"dyn_th={dynamic_threshold:.3f}\n"
                                )
                    high_span_start = None
                    high_span_peak_score = 0.0
                    high_span_peak_frame = None

                prev_gray = gray
                frame_index += 1
        finally:
            cap.release()

        # 视频结尾仍在高变化窗口内时，也需要记一次切点
        if high_span_start is not None and high_span_peak_frame is not None:
            cut_time = high_span_peak_frame / fps
            raw_candidates.append(cut_time)

        # 对候选时间做去抖和去重: 同一秒内最多保留一个切点，避免连环检测
        raw_candidates = sorted(set(raw_candidates))
        merged: list[float] = []
        min_gap = max(1.0 / fps, 0.4)  # 至少 0.4 秒间隔
        for t in raw_candidates:
            if not merged:
                merged.append(t)
                continue
            if t - merged[-1] >= min_gap:
                merged.append(t)

        if self.debug and debug_log_file:
            with open(debug_log_file, "a", encoding="utf-8") as f:
                f.write("\nOpenCV 场景检测完成:\n")
                f.write(f"  原始候选点: {raw_candidates}\n")
                f.write(f"  合并后切点: {merged}\n\n")

        # 确保起始点始终为 0.0
        if not merged or merged[0] != 0.0:
            merged = [0.0] + merged

        return merged

    def _detect_scenes(
        self,
        video_path: Path,
        threshold: float,
        fps: float,
        debug_log_file: Path | None = None,
    ) -> list[float]:
        """
        场景检测统一入口:
        - 首选 OpenCV 算法，以提升对叠化/渐变等复杂转场的识别能力。
        - 出现任何异常或 OpenCV 不可用时，自动回退到 FFmpeg 实现。
        """
        # 优先尝试 OpenCV
        if cv2 is not None and np is not None:
            try:
                return self._detect_scenes_opencv(video_path, threshold, fps, debug_log_file)
            except Exception as e:
                logger.exception(f"OpenCV 场景检测失败，回退到 FFmpeg scene 过滤器: {e}")

        # 回退到 FFmpeg 实现
        return self._detect_scenes_ffmpeg(video_path, threshold, debug_log_file)


    def find_files(self, directory: Path):
        """递归查找支持的视频文件"""
        video_extensions = {'.mp4', '.mkv', '.mov', '.avi', '.m4v', '.webm'}
        candidates = []
        if directory.is_file() and directory.suffix.lower() in video_extensions:
            candidates.append(directory)
        elif directory.is_dir():
            for p in directory.iterdir():
                if p.is_file() and p.suffix.lower() in video_extensions:
                    candidates.append(p)
        
        self.files = sorted(list(set(candidates)))

    def _build_watermark_filter(self, watermark_params):
        """
        构建水印过滤器
        watermark_params 中应包含:
        - font_name: 字体名称（从assets目录中选择）
        - text: 水印文本
        - font_color: 字体颜色
        - font_size: 字体大小
        - x: X 坐标
        - y: Y 坐标
        """
        if not watermark_params:
            return None
        
        # 获取字体名称并查找对应的相对路径
        font_name = watermark_params.get('font_name')
        if not font_name or font_name not in self.available_fonts:
            logger.warning(f"水印字体未指定或不存在: {font_name}")
            return None
        
        # 获取相对路径（如 assets/Roboto-Bold.ttf）
        font_relative_path = self.available_fonts[font_name]
        # print(f"使用水印字体: {font_name} -> {font_relative_path}")
        # 构建 FFmpeg 过滤器，使用相对路径
        return (
            f"drawtext=fontfile='{font_relative_path}':"
            f"text='{watermark_params['text']}':"
            f"fontcolor={watermark_params['font_color']}:"
            f"fontsize={watermark_params['font_size']}:"
            "box=1:boxcolor=black@0.5:boxborderw=10:"
            f"x={watermark_params['x']}:y={watermark_params['y']}"
        )

    def _align_to_frame(self, times: list[float], fps: float) -> list[float]:
        """将一组时间戳四舍五入到最接近的帧边界。
        若 fps<=0 或者 times 为空，原样返回。"""
        if fps <= 0 or not times:
            return times
        return [round(t * fps) / fps for t in times]

    def process_video(self, video_path: Path, output_root: Path, threshold=0.2,
                      export_frame=True, frame_offset=0,
                      watermark_params=None, person_id: str = "", rename_lines: list = None):
        
        video_output_dir = output_root / video_path.stem
        video_output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"开始处理: {video_path.name}")
        fps = get_video_fps(video_path, debug=self.debug)
        video_duration = _get_video_duration(video_path, debug=self.debug)
        # offset_time 仅用于截图；视频片段的起止时间使用场景检测结果并且会对齐到最接近的帧，
        # 以避免出现 "下一场景画面残留" 的情况。
        offset_time = frame_offset / fps

        # 调试日志文件路径
        debug_log_file = None
        if self.debug and self.log_dir:
            debug_log_file = self.log_dir / f"{video_path.stem}_debug.log"
            with open(debug_log_file, "w", encoding="utf-8") as f:
                f.write(f"=== 场景切分调试日志 ===\n")
                f.write(f"视频: {video_path.name}\n")
                f.write(f"时长: {video_duration}s\n")
                f.write(f"帧率: {fps:.2f} FPS\n")
                f.write(f"阈值: {threshold}\n")
                f.write(f"生成时间: {datetime.now().isoformat()}\n")
                f.write("=" * 50 + "\n\n")

        # 1. 场景检测 (优先使用 OpenCV，自适应回退到 FFmpeg)
        logger.info(f"正在分析场景 (阈值: {threshold})...")
        scene_times = self._detect_scenes(video_path, threshold, fps, debug_log_file)
        # 对检测结果进行帧对齐
        scene_times = self._align_to_frame(scene_times, fps)
        logger.info(f"检测到 {len(scene_times)} 个场景分段（已帧对齐）。")
        
        if self.debug and debug_log_file:
            with open(debug_log_file, "a", encoding="utf-8") as f:
                f.write(f"场景检测结果:\n")
                f.write(f"  检测到 {len(scene_times)} 个分段\n")
                f.write(f"  帧对齐后时间点: {scene_times}\n\n")

        rename_lines = rename_lines or []
        # 2. 生成报告和产物
        report_path = video_output_dir / "scene_report.txt"
        watermark_filter = self._build_watermark_filter(watermark_params)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"视频: {video_path.name}\n帧率: {fps:.2f} FPS\n阈值: {threshold}\n")
            f.write("-" * 60 + "\n")

            total_scenes = len(scene_times)
            for i, start_t in enumerate(scene_times):
                if self.monitor and self.monitor.check_stop_flag():
                    logger.info("收到停止请求，中断当前文件处理。")
                    break
                
                if self.monitor:
                    progress = (i / total_scenes) * 100
                    self.monitor.update_file_progress(progress, 100, f"场景 {i+1}/{total_scenes}")

                scene_idx = i + 1
                end_t = scene_times[i+1] if i < len(scene_times) - 1 else video_duration
                duration = end_t - start_t
                duration_str = f"{duration:.2f}s"

                report_line = f"段落 {scene_idx:03d}: 开始 {start_t:>7.2f}s | 时长: {duration_str:>8}"

                # A. 分割视频
                if duration > 0.1: # 忽略过短片段
                    # --- New Naming Logic ---
                    date_str = datetime.now().strftime("%Y%m%d")
                    
                    # Sanitize custom name
                    custom_name = ""
                    if rename_lines and i < len(rename_lines):
                        raw_name = rename_lines[i].strip()
                        if raw_name:
                            # Keep first 30 chars, remove invalid filename chars
                            sanitized = re.sub(r'[\\/*?:"<>|]', "", raw_name[:30])
                            custom_name = f"_{sanitized}"

                    person_id_str = f"_{re.sub(r'[\\/*?:\"<>|]', '', person_id.strip())}" if person_id else ""

                    clip_name = f"{date_str}{person_id_str}{custom_name}_{scene_idx:03d}.mp4"
                    clip_path = video_output_dir / clip_name

                    # 为了保证帧级精度，把 -ss 放在输入之后，同时让 ffmpeg 进行精确寻帧。
                    # 仅在不需要水印时才尝试直接复制流，否则重新编码。
                    cmd_split = [get_ffmpeg_exe(), '-y', '-i', str(video_path), '-ss', str(start_t), '-t', str(duration)]
                    if watermark_filter:
                        cmd_split.extend(['-vf', watermark_filter, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac'])
                    else:
                        cmd_split.extend(['-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac'])
                    cmd_split.append(str(clip_path))
                    
                    # 执行FFmpeg命令
                    success, output = self._execute_ffmpeg_command(cmd_split, debug_log_file)
                    
                    # 验证输出文件是否存在
                    if success and clip_path.exists():
                        report_line += f" | 视频: {clip_name}"
                        if self.debug and debug_log_file:
                            with open(debug_log_file, "a", encoding="utf-8") as f:
                                f.write(f"场景 {scene_idx}: 视频分割完成 -> {clip_name} (大小: {clip_path.stat().st_size} 字节)\n")
                    else:
                        report_line += f" | 视频分割失败: {clip_name}"
                        if self.debug and debug_log_file:
                            with open(debug_log_file, "a", encoding="utf-8") as f:
                                f.write(f"场景 {scene_idx}: 视频分割失败 -> {clip_name}\n")
                        logger.error(f"视频分割失败: {clip_name}")

                # B. 导出静帧
                if export_frame:
                    img_name = f"scene_{scene_idx:03d}.png"
                    img_path = video_output_dir / img_name
                    capture_t = start_t + offset_time
                    
                    cmd_frame = [get_ffmpeg_exe(), "-y", "-hide_banner", "-nostats", "-loglevel", "error", '-ss',str(capture_t), '-i', str(video_path), '-frames:v', '1']
                    if watermark_filter:
                        cmd_frame.extend(['-vf', watermark_filter])
                    cmd_frame.extend(['-q:v', '2', str(img_path)])
                    
                    # 执行FFmpeg命令
                    success, output = self._execute_ffmpeg_command(cmd_frame, debug_log_file)
                    
                    # 验证输出文件是否存在
                    if success and img_path.exists():
                        report_line += f" | 截图: {img_name}"
                        if self.debug and debug_log_file:
                            with open(debug_log_file, "a", encoding="utf-8") as f:
                                f.write(f"场景 {scene_idx}: 截图生成完成 -> {img_name} (大小: {img_path.stat().st_size} 字节)\n")
                    else:
                        report_line += f" | 截图生成失败: {img_name}"
                        if self.debug and debug_log_file:
                            with open(debug_log_file, "a", encoding="utf-8") as f:
                                f.write(f"场景 {scene_idx}: 截图生成失败 -> {img_name}\n")
                        logger.error(f"截图生成失败: {img_name}")

                f.write(report_line + "\n")

        logger.info(f"处理完毕，结果保存至: {video_output_dir}")
        if self.debug and debug_log_file:
            logger.info(f"调试日志已保存至: {debug_log_file}")


    def run(self, input_path: Path, output_dir: Path, **kwargs):
        self.find_files(input_path)
        total_files = len(self.files)

        if self.monitor:
            self.monitor.update_overall_progress(0, total_files, f"准备就绪 ({total_files} 文件)")

        for idx, file_path in enumerate(self.files):
            if self.monitor and self.monitor.check_stop_flag():
                logger.info("收到停止请求，退出批处理。")
                break

            if self.monitor:
                self.monitor.update_overall_progress(idx, total_files, f"({idx}/{total_files}) 正在处理 {file_path.name}")

            try:
                self.process_video(file_path, output_dir, **kwargs)
            except Exception as e:
                logger.exception(f"处理 {file_path.name} 时发生错误: {e}")

            if self.monitor:
                self.monitor.update_overall_progress(idx + 1, total_files, f"({idx+1}/{total_files})")

        if self.monitor:
            if self.monitor.check_stop_flag():
                self.monitor.update_overall_progress(idx, total_files, "用户已停止")
            else:
                self.monitor.update_overall_progress(total_files, total_files, "所有文件处理完成！")



# def main():
#     parser = argparse.ArgumentParser(description="视频场景切分与自动截图工具 (FFmpeg 版)")
#     parser.add_argument("--input", "-i", default=".", help="输入视频文件或目录 (默认: 当前目录)")
#     parser.add_argument("--out", "-o", type=Path, default="output", help="保存已处理文件的输出目录")
#     parser.add_argument("--threshold", "-t", type=float, default=0.2, help="场景切换阈值 0-1 (默认: 0.2)")
#     parser.add_argument("--offset", "-f", type=int, default=10, help="截图帧偏移量 (默认: 10 帧)")
#     parser.add_argument("--no-frames", action="store_true", help="不导出静帧截图")
#     parser.add_argument("--debug", "-d", action="store_true", help="启用调试模式并记录日志")
#     parser.add_argument("--log-dir", "-l", type=Path, default=None, help="调试日志保存目录 (默认: 输出目录下的 logs)")
#     parser.add_argument("--list-fonts", action="store_true", help="列出所有可用的字体并退出")
#     parser.add_argument("--font", type=str, default=None, help="选择水印字体名称 (使用 --list-fonts 查看可用字体)")
#     parser.add_argument("--watermark-text", type=str, default=None, help="水印文本")
#     parser.add_argument("--watermark-size", type=int, default=30, help="水印字体大小 (默认: 30)")
#     parser.add_argument("--watermark-color", type=str, default="white", help="水印颜色 (默认: white)")
#     parser.add_argument("--watermark-pos", type=str, default="bottom_right", 
#                         help="水印位置 (left_top/top_center/right_top/left_center/center/right_center/left_bottom/bottom_center/right_bottom, 默认: bottom_right)")

#     args = parser.parse_args()

#     # 配置日志目录
#     input_path = Path(args.input)
#     output_dir = args.out
#     output_dir.mkdir(parents=True, exist_ok=True)

#     log_dir = args.log_dir if args.log_dir else (output_dir / "logs")
    
#     if args.debug:
#         log_dir.mkdir(parents=True, exist_ok=True)
#         logger.info(f"调试模式已启用，日志将保存至: {log_dir}")

#     # 初始化 SceneCutter 并加载可用字体
#     cutter = SceneCutter(debug=args.debug, log_dir=log_dir if args.debug else None, font_name=args.font)
    
#     # 列出可用字体并退出
#     if args.list_fonts:
#         print("\n=== 可用的字体列表 ===")
#         if cutter.available_fonts:
#             for idx, font_name in enumerate(cutter.available_fonts.keys(), 1):
#                 font_path = cutter.available_fonts[font_name]
#                 print(f"{idx}. {font_name}")
#                 print(f"   路径: {font_path}")
#         else:
#             print("未找到可用的字体文件。")
#             print(f"请在 {get_resource_path('assets')} 目录中放置 TTF 字体文件。")
#         return

#     # 构建水印参数
#     watermark_params = None
#     if args.watermark_text and args.font:
#         # 位置映射
#         position_map = {
#             "left_top": ("10", "10"),
#             "top_center": ("(w-text_w)/2", "10"),
#             "right_top": ("W-tw-10", "40"),
#             "left_center": ("10", "(h-text_h)/2"),
#             "center": ("(w-text_w)/2", "(h-text_h)/2"),
#             "right_center": ("w-text_w-10", "(h-text_h)/2"),
#             "left_bottom": ("10", "h-text_h-10"),
#             "bottom_center": ("(w-text_w)/2", "h-text_h-10"),
#             "bottom_right": ("W-tw-10", "h-text_h-10"),
#         }
        
#         x, y = position_map.get(args.watermark_pos, position_map["bottom_right"])
        
#         watermark_params = {
#             "font_name": args.font,
#             "text": args.watermark_text,
#             "font_color": args.watermark_color,
#             "font_size": args.watermark_size,
#             "x": x,
#             "y": y
#         }
#         logger.info(f"启用水印: 文本='{args.watermark_text}' 字体='{args.font}' 位置={args.watermark_pos}")
#     elif args.watermark_text or args.font:
#         logger.warning("启用水印需要同时指定 --font 和 --watermark-text 参数")

#     options = {
#         "threshold": args.threshold,
#         "export_frame": not args.no_frames,
#         "frame_offset": args.offset,
#         "watermark_params": watermark_params
#     }

#     # 支持单个文件或整个目录批处理
#     if input_path.is_file():
#         cutter.process_video(input_path, output_dir, **options)
#     elif input_path.is_dir():
#         cutter.run(input_path, output_dir, **options)
#     else:
#         print(f"错误: 找不到路径 {args.input}")



# if __name__ == "__main__":
#     main()