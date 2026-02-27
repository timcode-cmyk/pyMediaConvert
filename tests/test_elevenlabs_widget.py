from __future__ import annotations

import os
import pytest

from PySide6.QtWidgets import QApplication

from pyMediaTools.ui.elevenlabs_ui import ElevenLabsWidget, QuotaWorker


def ensure_qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_get_current_api_key(tmp_path, monkeypatch, tmp_path_factory):
    """get_current_api_key should return value from input, config or env."""
    ensure_qapp()
    widget = ElevenLabsWidget()

    # no key anywhere
    widget.key_input.setText("")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    # config is empty by default
    assert widget.get_current_api_key() == ""

    # environment variable takes precedence
    monkeypatch.setenv("ELEVENLABS_API_KEY", "env_key")
    assert widget.get_current_api_key() == "env_key"
    # input field overrides
    widget.key_input.setText("field_key")
    assert widget.get_current_api_key() == "field_key"


def test_refresh_quota_only_skips_if_no_key(monkeypatch):
    """When no API key is configured, refresh_quota_only should not create a worker.
    """
    ensure_qapp()
    widget = ElevenLabsWidget()
    widget.key_input.setText("")
    # keep config/env empty
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    created = []
    class DummyWorker:
        def __init__(self, key):
            created.append(key)
        def quota_info(self):
            pass
    monkeypatch.setattr('pyMediaTools.ui.elevenlabs_ui.QuotaWorker', DummyWorker)

    widget.refresh_quota_only()
    assert created == []
    # UI should reflect missing key
    assert "未设置API Key" in widget.quota_label.text()


def test_load_voices_no_key(monkeypatch):
    """load_voices should bail when there is no key and not create any workers."""
    ensure_qapp()
    widget = ElevenLabsWidget()
    widget.key_input.setText("")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    widget.load_voices(show_errors=False)
    assert not hasattr(widget, 'model_worker')
    assert not hasattr(widget, 'voice_worker')

