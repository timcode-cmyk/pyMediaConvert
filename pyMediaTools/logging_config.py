"""
日志配置模块
"""
import logging
from logging.handlers import RotatingFileHandler
from .utils import get_base_dir


def setup_logging(log_level=logging.INFO, filename="pyMediaConvert.log"):
    base = get_base_dir()
    log_path = base / filename

    logger = logging.getLogger()
    logger.setLevel(log_level)

    # avoid duplicate handlers
    if any(isinstance(h, RotatingFileHandler) and h.baseFilename == str(log_path) for h in logger.handlers):
        return logger

    handler = RotatingFileHandler(str(log_path), maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    # 注册全局异常钩子，确保未捕获的异常能写入日志
    import sys
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
    logging.info("Logging initialized with exception hook.")
    return logger


def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        setup_logging()
    return logger
