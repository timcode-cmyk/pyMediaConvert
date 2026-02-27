"""
视频场景切分、截图与分割工具 (FFmpeg 版)

功能:
- 使用 FFmpeg 的 scene 过滤器探测视频中的场景切换点。
- 在每个切换点生成截图。
- 将视频按场景分割成独立的视频文件。
- 可选为输出的视频或图片添加自定义文字水印。
"""

import subprocess
import os
import re
import argparse
from pathlib import Path
from datetime import datetime
from ..utils import get_ffmpeg_exe, get_ffprobe_exe
from ..logging_config import get_logger

logger = get_logger(__name__)


def _get_video_duration(file_path: Path) -> float:
    """使用 ffprobe 安全地获取视频时长"""
    ffprobe_exe = get_ffprobe_exe()
    cmd = [
        ffprobe_exe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.error(f"无法获取视频时长 {file_path}: {e}")
        return 0.0


def get_video_fps(video_path):
    """获取视频帧率，用于计算偏移时间"""
    cmd = [
        get_ffmpeg_exe(), '-i', str(video_path),
        '-an', '-f', 'null', '-'
    ]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    # 从输出中匹配 fps，例如 "23.98 fps"
    match = re.search(r"(\d+(\.\d+)?) fps", result.stderr)
    return float(match.group(1)) if match else 25.0


class SceneCutter:
    def __init__(self, monitor=None):
        self.monitor = monitor
        self.files = []

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
        if not watermark_params:
            return None
        
        # 从 AddCustomLogo 借鉴过滤器构造逻辑
        return (
            f"drawtext=fontfile='{watermark_params['font_path']}':"
            f"text='{watermark_params['text']}':"
            f"fontcolor={watermark_params['font_color']}:"
            f"fontsize={watermark_params['font_size']}:"
            "box=1:boxcolor=black@0.5:boxborderw=10:"
            f"x={watermark_params['x']}:y={watermark_params['y']}"
        )

    def process_video(self, video_path: Path, output_root: Path, threshold=0.3,
                      export_frame=True, frame_offset=10,
                      watermark_params=None, person_id: str = "", rename_lines: list = None):
        
        video_output_dir = output_root / video_path.stem
        video_output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"开始处理: {video_path.name}")
        fps = get_video_fps(video_path)
        video_duration = _get_video_duration(video_path)
        offset_time = frame_offset / fps

        # 1. 场景检测
        cmd_detect = [
            get_ffmpeg_exe(), '-i', str(video_path),
            '-filter_complex', f"select='gt(scene,{threshold})',showinfo",
            '-f', 'null', '-'
        ]
        logger.info(f"正在分析场景 (阈值: {threshold})...")
        process = subprocess.run(cmd_detect, capture_output=True, text=True, encoding='utf-8')
        
        scene_times = [0.0]
        times = re.findall(r"pts_time:([\d\.]+)", process.stderr)
        scene_times.extend([float(t) for t in times])
        logger.info(f"检测到 {len(scene_times)} 个场景分段。")

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

                    cmd_split = [get_ffmpeg_exe(), '-y', '-ss', str(start_t), '-i', str(video_path), '-t', str(duration)]
                    
                    if watermark_filter:
                        # 加水印需要重新编码
                        cmd_split.extend(['-vf', watermark_filter, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac'])
                    else:
                        # 不加水印可直接复制流，速度快
                        cmd_split.extend(['-c', 'copy'])
                    
                    cmd_split.append(str(clip_path))
                    subprocess.run(cmd_split, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    report_line += f" | 视频: {clip_name}"

                # B. 导出静帧
                if export_frame:
                    img_name = f"scene_{scene_idx:03d}.png"
                    img_path = video_output_dir / img_name
                    capture_t = start_t + offset_time
                    
                    cmd_frame = [get_ffmpeg_exe(), '-y', '-ss', str(capture_t), '-i', str(video_path), '-frames:v', '1']
                    if watermark_filter:
                        cmd_frame.extend(['-vf', watermark_filter])
                    cmd_frame.extend(['-q:v', '2', str(img_path)])
                    
                    subprocess.run(cmd_frame, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    report_line += f" | 截图: {img_name}"

                f.write(report_line + "\n")

        logger.info(f"处理完毕，结果保存至: {video_output_dir}")

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


def main():
    parser = argparse.ArgumentParser(description="视频场景切分与自动截图工具 (FFmpeg 版)")
    parser.add_argument("--input", "-i", default=".", help="输入视频文件或目录 (默认: 当前目录)")
    parser.add_argument("--out", "-o", type=Path, default="output", help="保存已处理文件的输出目录")
    parser.add_argument("--threshold", "-t", type=float, default=0.2, help="场景切换阈值 0-1 (默认: 0.2)")
    parser.add_argument("--offset", "-f", type=int, default=10, help="截图帧偏移量 (默认: 10 帧)")
    parser.add_argument("--no-frames", action="store_true", help="不导出静帧截图")

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = args.out
    output_dir.mkdir(parents=True, exist_ok=True)

    cutter = SceneCutter()
    options = {
        "threshold": args.threshold,
        "export_frame": not args.no_frames,
        "frame_offset": args.offset,
        "watermark_params": None
    }

    # 支持单个文件或整个目录批处理
    if input_path.is_file():
        cutter.process_video(input_path, output_dir, **options)
    elif input_path.is_dir():
        cutter.run(input_path, output_dir, **options)
    else:
        print(f"错误: 找不到路径 {args.input}")

if __name__ == "__main__":
    main()