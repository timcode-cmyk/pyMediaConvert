import shutil
import sys
from pathlib import Path

import pytest

import pyMediaConvert.utils as utils


def test_get_ffmpeg_exe_prefers_bundled(tmp_path, monkeypatch):
    # Arrange: create a fake bundled ffmpeg
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_ffmpeg = fake_bin / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    fake_ffmpeg.write_text("stub")

    monkeypatch.setattr(utils, "BIN_DIR", fake_bin)

    # Act
    result = utils.get_ffmpeg_exe()

    # Assert
    assert Path(result).resolve() == fake_ffmpeg.resolve()


def test_get_ffmpeg_exe_falls_back_to_path_when_no_bundle(monkeypatch):
    # Arrange: point BIN_DIR to empty tempdir
    fake_bin = Path("/nonexistent_bin_dir_for_test")
    monkeypatch.setattr(utils, "BIN_DIR", fake_bin)

    expected = "/usr/bin/ffmpeg"
    monkeypatch.setattr(shutil, "which", lambda name: expected)

    # Act
    result = utils.get_ffmpeg_exe()

    # Assert
    assert result == expected


def test_get_ffmpeg_exe_returns_bundled_path_when_none_found(monkeypatch):
    fake_bin = Path("/nonexistent_bin_dir_for_test")
    monkeypatch.setattr(utils, "BIN_DIR", fake_bin)

    # No PATH match
    monkeypatch.setattr(shutil, "which", lambda name: None)

    result = utils.get_ffmpeg_exe()

    assert result == str(fake_bin / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"))
