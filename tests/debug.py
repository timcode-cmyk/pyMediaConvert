from pathlib import Path
from pyMediaConvert.mediaconvert.config import MODES

mode_key = "h264"                # 或你在 GUI 中选择的模式键
input_dir = Path("/path/to/your/input")  # 替换成你问题目录

mode = MODES.get(mode_key)
print("mode config:", mode_key, mode)
conv = mode['class'](params=mode.get('params', {}), support_exts=mode.get('support_exts'), init_checks=False)
print("converter.support_exts:", conv.support_exts)
print("converter.output_ext:", conv.output_ext)
conv.find_files(input_dir)
print("found files:", len(conv.files))
print("sample files:", conv.files[:20])