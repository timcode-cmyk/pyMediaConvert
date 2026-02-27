import sys
import os
from pathlib import Path

import pytest

from pyMediaTools import utils


def test_get_base_dir_dev(monkeypatch, tmp_path):
    # Simulate development environment by ensuring not frozen and no _MEIPASS
    monkeypatch.delenv('PYMEDIA_CONFIG_PATH', raising=False)
    monkeypatch.setattr(sys, 'frozen', False, raising=False)
    monkeypatch.delenv('_MEIPASS', raising=False)

    # Re-import to ensure fresh state in case get_base_dir cached
    # not necessary because function doesn't cache, but safe
    base = utils.get_base_dir()
    expected = Path(__file__).resolve().parent.parent / 'pyMediaTools'
    # base should be project root (one level above pyMediaTools/package)
    assert base == expected.parent


def test_get_base_dir_onefile(monkeypatch, tmp_path):
    # simulate PyInstaller onefile by setting _MEIPASS
    fake = tmp_path / "meipass"
    fake.mkdir()
    monkeypatch.setattr(sys, '_MEIPASS', str(fake), raising=False)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)

    base = utils.get_base_dir()
    assert Path(base) == fake


def test_get_base_dir_frozen_dir(monkeypatch, tmp_path):
    monkeypatch.delenv('_MEIPASS', raising=False)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    # arbitrary path with parent
    exe = tmp_path / "bin" / "myexe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, 'executable', str(exe), raising=False)
    monkeypatch.setattr(sys, 'platform', 'linux', raising=False)

    base = utils.get_base_dir()
    assert base == exe.parent


def test_get_base_dir_darwin_app(monkeypatch, tmp_path):
    # build fake .app structure
    app = tmp_path / "MyApp.app"
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    resources.mkdir(parents=True)
    macos.mkdir(parents=True)
    exe = macos / "MyApp"
    exe.write_text('')

    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(exe), raising=False)
    monkeypatch.setattr(sys, 'platform', 'darwin', raising=False)

    base = utils.get_base_dir()
    # Should return Resources directory
    assert Path(base) == resources
