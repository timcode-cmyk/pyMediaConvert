'''utils.py - 通用实用程序函数

    BASE_DIR: Path：项目根目录路径。
    BIN_DIR: Path：内置二进制工具目录 (BASE_DIR / "bin")。
    ASSET_DIR: Path：内置静态资源目录 (BASE_DIR / "assets")。
    get_base_dir() -> Path：跨环境（开发环境、PyInstaller 解包目录 sys._MEIPASS、Nuitka 可执行文件目录）识别项目真实基准路径。
    find_config_path() -> Optional[Path]：按环境变量 PYMEDIA_CONFIG_PATH -> 项目根目录 -> 当前工作目录 -> 父目录链顺序查找只读默认 config.toml。
    get_user_config_dir() -> Path：获取当前平台标准用户配置目录。
    get_user_config_path() -> Path：获取用户个性化配置文件路径 (user_config.json)，支持 PYMEDIA_USER_CONFIG_PATH 覆盖。
    load_default_config() -> dict：只读加载初始化默认 config.toml。
    load_user_config() -> dict：加载用户个性化覆盖配置 (user_config.json)。
    load_project_config(force_reload: bool = False) -> dict：三层合并配置（只读 config.toml < user_config.json < 环境变量覆写）。
    save_project_config(config_dict: dict)：计算与默认配置的差集并写入 user_config.json（绝不修改只读 config.toml）。
    update_user_config(updates: dict) -> dict：增量合并更新用户个性化配置并持久化。
    reset_user_config() -> bool：清除用户个性化覆写配置，恢复出厂默认。
    get_elevenlabs_config() -> dict：快捷获取 ElevenLabs 相关子配置。
    get_resource_path(*parts) -> Path：拼接获取 assets 或其他静态资源的绝对路径。
    get_ffmpeg_exe() -> str：返回当前操作系统平台对应的 ffmpeg 可执行文件绝对路径，并在 Unix 平台确保赋予可执行权限 (+x)。
    get_ffprobe_exe() -> str：返回当前平台对应的 ffprobe 可执行文件绝对路径。
    get_default_download_dir() -> Path：获取默认下载目录（优先读取环境变量与配置，默认回退到系统 Downloads 目录）。
    get_subprocess_creation_flags() -> int：返回跨平台子进程无窗口标志（Windows 返回 CREATE_NO_WINDOW）。
'''

import copy
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

# 只读 TOML 解析器：优先使用 Python 3.11+ 标准库 tomllib，低版本回退第三方 toml
try:
    import tomllib as _toml
except Exception:
    try:
        import toml as _toml
    except Exception:
        _toml = None

_logger = logging.getLogger(__name__)


def get_base_dir() -> Path:
    """
    返回项目根目录：
    - 开发环境：pyMediaTools/utils.py 的父目录的父目录
    - 打包环境 (PyInstaller onefile)：使用 sys._MEIPASS（运行时解包目录）
    - 其他打包器（Nuitka/frozen）：sys.executable 所在目录
    """
    # PyInstaller onefile 运行时会把数据解包到 sys._MEIPASS
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        return Path(meipass)

    if getattr(sys, "frozen", False):
        # 其他打包器：可执行文件所在目录
        return Path(sys.executable).parent
    else:
        # 开发环境
        return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
BIN_DIR = BASE_DIR / "bin"
ASSET_DIR = BASE_DIR / "assets"

# 项目级配置缓存
_PROJECT_CONFIG: Optional[dict] = None


def get_user_config_dir() -> Path:
    """返回符合当前操作系统规范的用户配置持久化目录。"""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        base = Path(appdata) if appdata else (Path.home() / "AppData" / "Roaming")
    else:
        xdg = os.getenv("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else (Path.home() / ".config")
    return base / "pyMediaTools"


def get_user_config_path() -> Path:
    """获取用户个性化覆写配置文件路径（JSON），支持 PYMEDIA_USER_CONFIG_PATH 环境变量指定。"""
    env_user_cfg = os.getenv("PYMEDIA_USER_CONFIG_PATH")
    if env_user_cfg:
        return Path(env_user_cfg).expanduser()
    return get_user_config_dir() / "user_config.json"


def find_config_path() -> Optional[Path]:
    """搜索项目只读初始化默认配置 config.toml。

    优先顺序：
      - 来自 env PYMEDIA_CONFIG_PATH 或 PYMEDIA_CONFIG 的路径
      - 项目基础 config.toml（由 get_base_dir() 返回）
      - 当前工作目录 config.toml
      - 从该文件向上的任何父目录
    """
    env_path = os.getenv('PYMEDIA_CONFIG_PATH') or os.getenv('PYMEDIA_CONFIG')
    candidates = []
    if env_path:
        candidates.append(Path(env_path))

    candidates.append(BASE_DIR / 'config.toml')
    candidates.append(Path.cwd() / 'config.toml')

    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / 'config.toml')

    for c in candidates:
        if c and c.exists():
            return c
    return None


def _deep_merge(base: dict, override: dict) -> dict:
    """递归深度合并两个字典（不修改原字典，override 优先级更高）。"""
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def _compute_diff(default_cfg: dict, target_cfg: dict) -> dict:
    """计算 target_cfg 相对于 default_cfg 的差集，只保留用户修改过的项。"""
    diff: dict[str, Any] = {}
    for key, val in target_cfg.items():
        if key not in default_cfg:
            diff[key] = copy.deepcopy(val)
        elif isinstance(val, dict) and isinstance(default_cfg[key], dict):
            sub_diff = _compute_diff(default_cfg[key], val)
            if sub_diff:
                diff[key] = sub_diff
        elif val != default_cfg[key]:
            diff[key] = copy.deepcopy(val)
    return diff


def load_default_config() -> dict:
    """只读加载出厂默认配置 config.toml。"""
    cfg_path = find_config_path()
    if not cfg_path:
        return {}

    if _toml is None:
        raise RuntimeError("TOML 解析器不可用。请使用 Python 3.11+ 或安装 'toml'")

    data = cfg_path.read_bytes()
    try:
        return _toml.loads(data.decode('utf-8') if isinstance(data, (bytes, bytearray)) else data)
    except TypeError:
        # tomllib 兼容旧接口：Python < 3.11 或某些版本只接受 str
        return _toml.loads(data.decode('utf-8'))


def load_user_config() -> dict:
    """从系统标准用户配置目录加载个性化自定义覆写配置 (user_config.json)。"""
    user_path = get_user_config_path()
    if not user_path.exists():
        return {}
    try:
        content = user_path.read_text(encoding='utf-8').strip()
        if not content:
            return {}
        loaded = json.loads(content)
        return loaded if isinstance(loaded, dict) else {}
    except Exception as e:
        _logger.warning(f"读取用户个性化配置失败 ({user_path}): {e}")
        return {}


def get_env_override(env_names: tuple[str, ...]) -> Optional[str]:
    """按顺序查找首个非空的环境变量值。"""
    for name in env_names:
        val = os.getenv(name)
        if val is not None and val.strip() != "":
            return val.strip()
    return None


def _apply_env_overrides(cfg: dict) -> dict:
    """应用高优先级的环境变量覆写配置（Layer 3）。"""
    env_mappings = [
        (("PYMEDIA_ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY"), ("elevenlabs", "api_key")),
        (("PYMEDIA_GROQ_API_KEY", "GROQ_API_KEY"), ("groq", "api_key")),
        (("PYMEDIA_GLADIA_API_KEY", "GLADIA_API_KEY"), ("gladia", "api_key")),
        (("PYMEDIA_DOWNLOAD_DIR",), ("download", "default_dir")),
    ]
    for env_names, key_path in env_mappings:
        val = get_env_override(env_names)
        if val is not None:
            curr = cfg
            for part in key_path[:-1]:
                if part not in curr or not isinstance(curr[part], dict):
                    curr[part] = {}
                curr = curr[part]
            curr[key_path[-1]] = val
    return cfg


def load_project_config(force_reload: bool = False) -> dict:
    """加载三层合并配置并缓存：
    Layer 1: 只读出厂默认 config.toml
    Layer 2: 用户自定义持久化配置 (user_config.json)
    Layer 3: 运行时环境变量覆写
    """
    global _PROJECT_CONFIG
    if _PROJECT_CONFIG is not None and not force_reload:
        return _PROJECT_CONFIG

    default_cfg = load_default_config()
    user_cfg = load_user_config()
    merged = _deep_merge(default_cfg, user_cfg)
    merged = _apply_env_overrides(merged)

    _PROJECT_CONFIG = merged
    return _PROJECT_CONFIG


def _write_user_config_file(user_cfg: dict):
    """将用户个性化字典以 UTF-8 JSON 格式安全写入用户配置目录。"""
    user_path = get_user_config_path()
    user_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = user_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(user_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(user_path)


def save_project_config(config_dict: dict):
    """将自定义配置保存至用户配置目录 (user_config.json)，绝不修改只读的 config.toml。"""
    global _PROJECT_CONFIG
    try:
        default_cfg = load_default_config()
        diff_cfg = _compute_diff(default_cfg, config_dict)
        _write_user_config_file(diff_cfg)
        _PROJECT_CONFIG = None
        load_project_config(force_reload=True)
    except Exception as e:
        _logger.exception(f"保存用户个性化配置失败: {e}")


def update_user_config(updates: dict) -> dict:
    """增量合并更新用户个性化配置并立即持久化，返回最新合并配置。"""
    global _PROJECT_CONFIG
    try:
        current_user = load_user_config()
        merged_user = _deep_merge(current_user, updates)
        default_cfg = load_default_config()
        diff_cfg = _compute_diff(default_cfg, _deep_merge(default_cfg, merged_user))
        _write_user_config_file(diff_cfg)
        _PROJECT_CONFIG = None
        return load_project_config(force_reload=True)
    except Exception as e:
        _logger.exception(f"更新用户配置失败: {e}")
        return load_project_config()


def reset_user_config() -> bool:
    """删除用户自定义配置文件，恢复为 config.toml 默认配置。"""
    global _PROJECT_CONFIG
    user_path = get_user_config_path()
    try:
        if user_path.exists():
            user_path.unlink()
        _PROJECT_CONFIG = None
        load_project_config(force_reload=True)
        return True
    except Exception as e:
        _logger.exception(f"重置用户配置失败: {e}")
        return False


def get_elevenlabs_config() -> dict:
    return load_project_config().get('elevenlabs', {}) or {}


def get_resource_path(*parts) -> Path:
    return BASE_DIR.joinpath(*parts)


def get_subprocess_creation_flags() -> int:
    """获取跨平台子进程隐藏窗口标志（Windows 下返回 CREATE_NO_WINDOW，其余平台返回 0）。"""
    if sys.platform == "win32":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _ensure_executable(path: Path):
    try:
        if sys.platform != 'win32' and path.exists():
            mode = path.stat().st_mode
            # add owner execute bit if missing
            if not (mode & 0o100):
                path.chmod(mode | 0o100)
    except Exception:
        # best-effort only
        pass


def get_ffmpeg_exe() -> str:
    exe_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    path = BIN_DIR / exe_name
    _ensure_executable(path)
    return str(path)


def get_ffprobe_exe() -> str:
    exe_name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    path = BIN_DIR / exe_name
    _ensure_executable(path)
    return str(path)


def get_default_download_dir() -> Path:
    """返回默认下载目录"""
    config = load_project_config()
    download_dir = config.get('download', {}).get('default_dir')
    if download_dir:
        return Path(download_dir).expanduser()

    return Path.home() / "Downloads"