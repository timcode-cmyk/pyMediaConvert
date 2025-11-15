"""
视频批处理 CLI
依赖：ffmpeg, ffprobe 在 PATH 中

许可证声明：
本产品使用了 FFmpeg，其在 LGPL/GPL 下发布。
更多信息请参考项目的 README 文件。
"""
from pathlib import Path
import argparse
import config

def main():
    parser = argparse.ArgumentParser(description="视频批处理工具 (使用 FFmpeg)")
    parser.add_argument("--dir", "-d", default=".", help="要处理的视频所在目录（默认当前目录）")
    parser.add_argument("--out", "-o", type=Path, default="output", help="保存已处理文件的输出目录")
    parser.add_argument("--mode", "-m", type=str, choices=config.MODES.keys(), required=True, help="处理模式")
    parser.add_argument("--ext", "-e", type=str, default=None, help="覆盖默认的扩展名 (例如: .mp4,.mov)")
    args = parser.parse_args()

    work_dir = Path(args.dir).expanduser().resolve()
    out_dir = work_dir / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
        
    if not work_dir.is_dir():
        parser.error(f"输入目录未找到: {args.dir}")

    mode_config = config.MODES.get(args.mode)
    if not mode_config:
        parser.error(f"未知的模式: {args.mode}")
        return
    
    ConverterClass = mode_config['class']
    params = mode_config.get('params', {})
    output_ext = mode_config.get('output_ext')
    if args.ext:
        support_exts = args.ext.split(',')
    else:
        support_exts = mode_config.get('support_exts')
    try:
        converter = ConverterClass(
            params=params,
            support_exts=support_exts,
            output_ext=output_ext
        )
    except SystemExit:
        print(f"初始化模式 '{args.mode}' 失败，请检查配置。")
        return
    except Exception as e:
        print(f"实例化转换器时发生错误: {e}")
        return
    

    # 运行
    converter.run(
        input_dir=work_dir,
        out_dir=out_dir,
    )

if __name__ == "__main__":
    main()