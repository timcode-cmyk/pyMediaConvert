"""
视频场景切分与自动截图工具 (FFmpeg 版)
使用 FFmpeg 的 scene 过滤器探测视频中的场景切换点，并在每个切换点生成一张截图。适用于快速分析视频内容结构，提取关键帧等场景。
依赖: FFmpeg
使用方法:   python vidoecut.py --input /path/to/video.mp4 --out /path/to/output --threshold 0.3 --offset 10
参数说明:
    --input / -i: 输入视频文件或目录 (默认: 当前目录)
    --out / -o: 保存已处理文件的输出目录 (默认: output)
    --threshold / -t: 场景切换阈值 0-1 (默认: 0.3)，数值越小越敏感
    --offset / -f: 截图帧偏移量 (默认: 10)，即在切换点基础上偏移多少帧进行截图，避免黑场等问题
输出结果:
    每个视频会在输出目录下生成一个同名子目录，包含:
    - scene_report.txt: 场景切分报告，包含每个段落的开始时间、持续时间和截图文件名
    - scene_001.png, scene_002.png, ...: 每个场景切换点对应的截图
示例:
    python vidoecut.py -i ./videos -o ./output -t 0.25 -f 5
    这将处理 videos 目录下的所有视频文件，使用 0.25 的场景切换阈值和 5 帧的截图偏移量，结果保存在 output 目录下。
"""


import subprocess
import os
import re
import argparse
from pathlib import Path

def get_video_fps(video_path):
    """获取视频帧率，用于计算偏移时间"""
    cmd = [
        'ffmpeg', '-i', video_path,
        '-an', '-f', 'null', '-'
    ]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    # 从输出中匹配 fps，例如 "23.98 fps"
    match = re.search(r"(\d+(\.\d+)?) fps", result.stderr)
    return float(match.group(1)) if match else 25.0

def run_scene_detection(video_path, output_root, threshold=0.3, frame_offset=10):
    video_path = Path(video_path).resolve()
    # 为每个视频创建独立的子目录
    video_output_dir = output_root / video_path.stem
    video_output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[开始处理] {video_path.name}")
    fps = get_video_fps(str(video_path))
    offset_time = frame_offset / fps

    # 1. 使用 FFmpeg 的 scene 过滤器探测场景切换点
    # 我们将结果输出到 log，不生成实际视频
    cmd_detect = [
        'ffmpeg', '-i', str(video_path),
        '-filter_complex', f"select='gt(scene,{threshold})',showinfo",
        '-f', 'null', '-'
    ]
    
    print(f"正在分析场景 (阈值: {threshold})...")
    process = subprocess.run(cmd_detect, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    
    # 从 showinfo 中提取 pts_time
    # 格式示例: [Parsed_showinfo_1 @ ... ] n:   1 pts: 123456 pts_time:12.3456 ...
    scene_times = [0.0]  # 默认包含开头
    times = re.findall(r"pts_time:([\d\.]+)", process.stderr)
    scene_times.extend([float(t) for t in times])
    
    print(f"检测到 {len(scene_times)} 个场景分段。")

    # 2. 生成报告和截图
    report_path = video_output_dir / "scene_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"视频: {video_path.name}\n帧率: {fps} FPS\n偏移量: {frame_offset} 帧 ({offset_time:.3f}s)\n")
        f.write("-" * 60 + "\n")

        for i, start_t in enumerate(scene_times):
            scene_idx = i + 1
            duration = scene_times[i+1] - start_t if i < len(scene_times) - 1 else -1
            duration_str = f"{duration:.2f}s" if duration > 0 else "至结束"
            
            img_name = f"scene_{scene_idx:03d}.png"
            img_path = video_output_dir / img_name
            
            # 截图：跳转到切换点 + 偏移量
            capture_t = start_t + offset_time
            subprocess.run([
                'ffmpeg', '-y', '-ss', str(capture_t),
                '-i', str(video_path),
                '-frames:v', '1', '-q:v', '2',
                str(img_path)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            f.write(f"段落 {scene_idx:03d}: 开始 {start_t:>7.2f}s | 时长: {duration_str:>8} | 截图: {img_name}\n")
            print(f"  > 已生成场景 {scene_idx:03d} 的截图", end="\r")

    print(f"\n[处理完毕] 结果保存至: {video_output_dir}")

def main():
    parser = argparse.ArgumentParser(description="视频场景切分与自动截图工具 (FFmpeg 版)")
    parser.add_argument("--input", "-i", default=".", help="输入视频文件或目录 (默认: 当前目录)")
    parser.add_argument("--out", "-o", type=Path, default="output", help="保存已处理文件的输出目录")
    parser.add_argument("--threshold", "-t", type=float, default=0.2, help="场景切换阈值 0-1 (默认: 0.3)")
    parser.add_argument("--offset", "-f", type=int, default=10, help="截图帧偏移量 (默认: 10 帧)")
    
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = args.out

    # 支持单个文件或整个目录批处理
    if input_path.is_file():
        run_scene_detection(input_path, output_dir, args.threshold, args.offset)
    elif input_path.is_dir():
        video_extensions = {'.mp4', '.mkv', '.mov', '.avi', '.m4v'}
        for file in input_path.iterdir():
            if file.suffix.lower() in video_extensions:
                run_scene_detection(file, output_dir, args.threshold, args.offset)
    else:
        print(f"错误: 找不到路径 {args.input}")

if __name__ == "__main__":
    main()