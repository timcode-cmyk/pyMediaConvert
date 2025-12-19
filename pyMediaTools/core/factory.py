"""Load modes configuration from TOML and map to actual Converter classes.

This exposes a MODES dict compatible with the previous `config.py` format.
"""
from pathlib import Path
import sys

# TOML parser: prefer stdlib tomllib (Python 3.11+), fallback to third-party `toml`.
try:
    import tomllib as _toml
except Exception:  # pragma: no cover - fallback
    try:
        import toml as _toml
    except Exception:
        raise RuntimeError(
            "TOML parser not available. For Python<3.11 install 'toml' (pip install toml)"
        )

from .mediaconvert import (
    LogoConverter,
    AddCustomLogo,
    H264Converter,
    DnxhrConverter,
    PngConverter,
    Mp3Converter,
    WavConverter,
)

CLASS_MAP = {
    'LogoConverter': LogoConverter,
    'AddCustomLogo': AddCustomLogo,
    'H264Converter': H264Converter,
    'DnxhrConverter': DnxhrConverter,
    'PngConverter': PngConverter,
    'Mp3Converter': Mp3Converter,
    'WavConverter': WavConverter,
}


def _load_toml(path: Path):
    data = path.read_bytes()
    # tomllib expects bytes, the toml package expects str
    try:
        return _toml.loads(data.decode() if isinstance(data, (bytes, bytearray)) else data)
    except AttributeError:
        # toml package has loads for str, but might accept bytes on some versions
        return _toml.loads(data.decode())


def _build_modes(toml_data: dict):
    modes = {}
    raw_modes = toml_data.get('modes', {})
    for key, cfg in raw_modes.items():
        class_name = cfg.get('class')
        if not class_name:
            raise ValueError(f"mode '{key}' missing 'class' field in config.toml")
        cls = CLASS_MAP.get(class_name)
        if not cls:
            raise ValueError(f"unknown class '{class_name}' for mode '{key}'")

        params = cfg.get('params') or {}
        output_ext = cfg.get('output_ext') or None
        if isinstance(output_ext, str) and output_ext == '':
            output_ext = None
        support_exts = cfg.get('support_exts')
        if support_exts is not None:
            support_exts = [s.lower() for s in support_exts]

        modes[key] = {
            'class': cls,
            'description': cfg.get('description', ''),
            'output_ext': output_ext,
            'support_exts': support_exts,
            'params': params,
        }
    return modes


# Public API
import os
import logging


def _find_config_path() -> Path | None:
    """Search for config.toml in sensible locations.

    Order of preference:
      - path from env PYMEDIA_CONFIG_PATH or PYMEDIA_CONFIG
      - same directory as this file
      - package root (parent)
      - repository/project root (cwd)
      - any parent directories upwards from this file
    """
    env_path = os.getenv('PYMEDIA_CONFIG_PATH') or os.getenv('PYMEDIA_CONFIG')
    candidates = []
    if env_path:
        candidates.append(Path(env_path))

    base = Path(__file__).parent
    candidates.append(base / 'config.toml')
    candidates.append(base.parent / 'config.toml')
    candidates.append(Path.cwd() / 'config.toml')

    # walk parents of this file
    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / 'config.toml')

    for c in candidates:
        if c and c.exists():
            return c
    return None


_CONFIG_PATH = _find_config_path()
if _CONFIG_PATH is None:
    logging.getLogger(__name__).warning(
        "config.toml not found; searched multiple locations (set PYMEDIA_CONFIG_PATH to override)."
    )
    MODES = {}
else:
    logging.getLogger(__name__).info(f"Loading config from: {_CONFIG_PATH}")
    _TOML = _load_toml(_CONFIG_PATH)
    MODES = _build_modes(_TOML)


def get_modes():
    """Return MODES dict (copy to avoid accidental mutation)."""
    return {k: v.copy() for k, v in MODES.items()}