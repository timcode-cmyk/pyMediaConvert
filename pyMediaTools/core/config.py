"""
配置文件（兼容层）
现在配置默认从 `config.toml` 加载（见 `factory.py`），但保留内联默认值以防 TOML 缺失或解析失败。
"""

try:
    # 首选从 toml + factory 加载，使得配置可在运行时修改
    from .factory import MODES  # type: ignore
except Exception:
    # 兼容回退（与原来相同），以避免引入破坏性更改
    from ..core.mediaconvert import (
        LogoConverter,
        AddCustomLogo,
        H264Converter,
        DnxhrConverter,
        PngConverter,
        Mp3Converter,
        WavConverter
    )

    # 模式配置
    MODES = {
        'hailuo': {
            'class': LogoConverter,
            'description': "添加 Dream+Hailuo Logo (竖屏)",
            'output_ext': "_hailuo.mp4",
            'support_exts': [".mp4"],
            'params': {
                'x': 590, 'y': 1810,
                'logo_w': 475, 'logo_h': 90,
                'target_w': 1080, 'target_h': 1920,
                'logo_path': "assets/hailuo.png"
                }
            },
        'vidu': {
            'class': LogoConverter,
            'description': "添加 Dream+Vidu Logo (竖屏)",
            'output_ext': "_vidu.mp4",
            'support_exts': [".mp4"],
            'params': {
                'x': 700, 'y': 1810,
                'logo_w': 360, 'logo_h': 90,
                'target_w': 1080, 'target_h': 1920,
                'logo_path': "assets/vidu.png"
                }
            },
        'veo': {
            'class': LogoConverter,
            'description': "添加 Dream+Veo Logo (竖屏)",
            'output_ext': "_veo.mp4",
            'support_exts': [".mp4"],
            'params': {
                'x': 700, 'y': 1810,
                'logo_w': 360, 'logo_h': 90,
                'target_w': 1080, 'target_h': 1920,
                'logo_path': "assets/Veo.png"
                }
            },
        'heygen': {
            'class': LogoConverter,
            'description': "添加 Dream+HegGen Logo (竖屏)",
            'output_ext': "_veo.mp4",
            'support_exts': [".mp4"],
            'params': {
                'x': 700, 'y': 1810,
                'logo_w': 360, 'logo_h': 90,
                'target_w': 1080, 'target_h': 1920,
                'logo_path': "assets/HeyGen.png"
                }
            },
        'dream': {
            'class': LogoConverter,
            'description': "添加 Dreamina Logo (竖屏)",
            'output_ext': "_veo.mp4",
            'support_exts': [".mp4"],
            'params': {
                'x': 700, 'y': 1810,
                'logo_w': 360, 'logo_h': 90,
                'target_w': 1080, 'target_h': 1920,
                'logo_path': "assets/Dream.png"
                }
            },
        'image': {
            'class': AddCustomLogo,
            'description': "添加 ImageFromAI",
            'output_ext': None,
            'support_exts': [".mp4", ".png", ".jpg", ".jpeg"],
            'params': {
                'x': "W-tw-10", 'y': 40,
                'font_path': "assets/Roboto-Bold.ttf",
                'font_size': "24",
                'font_color': "white",
                'text': "AI Created",
                
                }
            },

        'h264': {
            'class': H264Converter,
            'description': "转换为 H.264 (MP4)",
            'output_ext': "_h264.mp4",
            'support_exts': [".mov", ".avi", ".mkv", ".mp4", ".webm"], 
            'params': {}
            },
        'x264': {
            'class': H264Converter,
            'description': "转换为 H.264 (压缩)",
            'output_ext': "_x264.mp4",
            'support_exts': [".mov", ".avi", ".mkv", ".mp4", ".webm"], 
            'params': {
                'video_codec': 'libx264',
                'preset_key': '-crf',
                'preset_value': '20'
            }
            },
        'dnxhr': {
            'class': DnxhrConverter,
            'description': "转换为 DNxHR (MOV)",
            'output_ext': "_dnxhr.mov",
            'support_exts': [".mp4", ".avi", ".mkv", ".mov", ".webm"], 
            'params': {
                'video_codec': 'dnxhr_hq',
            }
            },
        'dnxhr_hqx': {
            'class': DnxhrConverter,
            'description': "转换为 DNxHR (10bit MOV)",
            'output_ext': "_dnxhr.mov",
            'support_exts': [".mp4", ".avi", ".mkv", ".mov", ".webm"], 
            'params': {
                'video_codec': 'dnxhr_hqx',
            }
            },
        'png': {
            'class': PngConverter,
            'description': "图片转换为 PNG",
            'output_ext': "_processed.png",
            'support_exts': [".jpg", ".bmp", ".png", ".webp", ".tiff"], 
            'params': {}
            },
        'mp3': {
            'class': Mp3Converter,
            'description': "音频转换为 MP3",
            'output_ext': "_processed.mp3",
            'support_exts': ['.mp3', '.wav', '.flac', '.ogg', '.mpeg', '.m4a', '.aiff'], 
            'params': {}
            },
        'wav': {
            'class': WavConverter,
            'description': "音频转换为 WAV",
            'output_ext': "_processed.wav",
            'support_exts': ['.mp3', '.wav', '.flac', '.ogg', '.mpeg', '.m4a', '.aiff', '.mp4', '.avi', '.mkv', '.mov', '.webm'], 
            'params': {}
            }
        }