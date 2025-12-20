
from pyMediaTools.logging_config import setup_logging, get_logger
from pyMediaTools.core import config


__all__ = [
    "setup_logging",
    "get_logger",
    "config",
]

class AppContext:
    def __init__(self):
        # 程序启动时只读一次
        self.modes = self.load_config_from_toml() 

    def load_config_from_toml(self):
        # 尝试多处导入以兼容不同的项目结构
        candidates = [
            'pyMediaTools.core.factory',
            'pyMediaTools.core.config',
        ]
        for mod in candidates:
            try:
                module = __import__(mod, fromlist=['MODES'])
                modes = getattr(module, 'MODES', None)
                if modes:
                    return modes
            except Exception:
                continue
        return {}