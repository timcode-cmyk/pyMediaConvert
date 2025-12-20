import os
from pathlib import Path

import pytest

import pyMediaTools.utils as utils



def test_load_project_config_from_env(tmp_path, monkeypatch):
    cfg_path = tmp_path / "myconfig.toml"
    cfg_path.write_text('[elevenlabs]\napi_key = "testkey"\ndefault_output_format = "mp3_48000_128"\n')
    monkeypatch.setenv('PYMEDIA_CONFIG_PATH', str(cfg_path))

    # reset cache
    utils._PROJECT_CONFIG = None

    cfg = utils.load_project_config()
    assert 'elevenlabs' in cfg
    assert cfg['elevenlabs']['api_key'] == 'testkey'
    assert cfg['elevenlabs']['default_output_format'] == 'mp3_48000_128'


def test_find_config_path_prefers_env(tmp_path, monkeypatch):
    cfg_path = tmp_path / "myconfig.toml"
    cfg_path.write_text('[dummy]\nval=1\n')
    monkeypatch.setenv('PYMEDIA_CONFIG_PATH', str(cfg_path))

    p = utils.find_config_path()
    assert p is not None
    assert Path(p).resolve() == cfg_path.resolve()
