from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from pyMediaTools.ui.elevenlabs_ui import ElevenLabsWidget, QuotaWorker


def ensure_qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


class TestElevenLabsWidget(unittest.TestCase):
    def setUp(self):
        ensure_qapp()

    def test_get_current_api_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ELEVENLABS_API_KEY", None)
            os.environ.pop("PYMEDIA_ELEVENLABS_API_KEY", None)
            widget = ElevenLabsWidget()
            try:
                widget.key_input.setText("")
                self.assertEqual(widget.get_current_api_key(), "")

                os.environ["ELEVENLABS_API_KEY"] = "env_key"
                self.assertEqual(widget.get_current_api_key(), "env_key")

                widget.key_input.setText("field_key")
                self.assertEqual(widget.get_current_api_key(), "field_key")
            finally:
                widget.cleanup()
                widget.close()
                widget.deleteLater()
                ensure_qapp().processEvents()

    def test_refresh_quota_only_skips_if_no_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ELEVENLABS_API_KEY", None)
            os.environ.pop("PYMEDIA_ELEVENLABS_API_KEY", None)
            widget = ElevenLabsWidget()
            try:
                widget.key_input.setText("")
                created = []

                class DummyWorker:
                    def __init__(self, key):
                        created.append(key)

                    def quota_info(self):
                        pass

                with patch("pyMediaTools.ui.elevenlabs_ui.QuotaWorker", DummyWorker):
                    widget.refresh_quota_only()
                    self.assertEqual(created, [])
                    self.assertIn("未设置API Key", widget.quota_label.text())
            finally:
                widget.cleanup()
                widget.close()
                widget.deleteLater()
                ensure_qapp().processEvents()

    def test_load_voices_no_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ELEVENLABS_API_KEY", None)
            os.environ.pop("PYMEDIA_ELEVENLABS_API_KEY", None)
            widget = ElevenLabsWidget()
            try:
                widget.key_input.setText("")
                widget.load_voices(show_errors=False)
                self.assertFalse(hasattr(widget, "model_worker"))
                self.assertFalse(hasattr(widget, "voice_worker"))
            finally:
                widget.cleanup()
                widget.close()
                widget.deleteLater()
                ensure_qapp().processEvents()


if __name__ == "__main__":
    unittest.main()
