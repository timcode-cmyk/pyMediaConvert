"""
配置文件
定义所有可用的处理模式及其参数。
"""

import worker
from src.utils import get_resource_path

# 模式配置
#
# 结构:
# 'mode_name': {
# 'class': 对应的 worker.py 中的转换器类,
# 'description': (用于GUI) 模式的简短描述,
# 'output_suffix': 输出文件的后缀名 (例如: '_hailuo.mp4'),
# 'support_exts': 支持的输入扩展名列表 (None 会使用类的默认值),
# 'params': {
# # 传递给转换器类 __init__ 的特定参数
# # 对于 LogoConverter: 'x', 'y', 'logo_w', 'logo_h', 'logo_path'
# }
# }
#
MODES = {
    'hailuo': {
        'class': worker.LogoConverter,
        'description': "添加海螺 Logo (竖屏)",
        'output_suffix': "_hailuo.mp4",
        'support_exts': [".mp4"],
        'params': {
            'x': 590, 'y': 1810,
            'logo_w': 475, 'logo_h': 90,
            'logo_path': "assets/hailuo.png"
            }
        },
    'vidu': {
        'class': worker.LogoConverter,
        'description': "添加 Vidu Logo (竖屏)",
        'output_suffix': "_vidu.mp4",
        'support_exts': [".mp4"],
        'params': {
            'x': 700, 'y': 1810,
            'logo_w': 360, 'logo_h': 90,
            'target_w': 1080, 'target_h': 1920,
            'logo_path': "assets/vidu.png"
            }
        },
    'veo': {
        'class': worker.LogoConverter,
        'description': "添加 Veo Logo (竖屏)",
        'output_suffix': "_veo.mp4",
        'support_exts': [".mp4"],
        'params': {
            'x': 700, 'y': 1810,
            'logo_w': 360, 'logo_h': 90,
            'target_w': 1080, 'target_h': 1920,
            'logo_path': "assets/Veo.png"
            }
        },
    'dream': {
        'class': worker.LogoConverter,
        'description': "添加 Dream Logo (竖屏)",
        'output_suffix': "_veo.mp4",
        'support_exts': [".mp4"],
        'params': {
            'x': 700, 'y': 1810,
            'logo_w': 360, 'logo_h': 90,
            'target_w': 1080, 'target_h': 1920,
            'logo_path': "assets/Dream.png"
            }
        },

    'h264': {
        'class': worker.H264Converter,
        'description': "转换为 H.264 (MP4)",
        'output_suffix': "_h264.mp4",
        'support_exts': None, # 使用类默认值
        'params': {}
        },
    'dnxhr': {
        'class': worker.DnxhrConverter,
        'description': "转换为 DNxHR (MOV)",
        'output_suffix': "_dnxhr.mov",
        'support_exts': None, # 使用类默认值
        'params': {}
        },
    'png': {
        'class': worker.PngConverter,
        'description': "图片转换为 PNG",
        'output_suffix': "_processed.png",
        'support_exts': None, # 使用类默认值
        'params': {}
        },
    'mp3': {
        'class': worker.Mp3Converter,
        'description': "音频转换为 MP3",
        'output_suffix': "_processed.mp3",
        'support_exts': None, # 使用类默认值
        'params': {}
        },
    'wav': {
        'class': worker.WavConverter,
        'description': "音频转换为 WAV",
        'output_suffix': "_processed.wav",
        'support_exts': None, # 使用类默认值
        'params': {}
        }
    }