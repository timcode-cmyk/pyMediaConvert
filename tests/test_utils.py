import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyMediaTools import utils


class TestUtils(unittest.TestCase):
    def test_get_base_dir_dev(self):
        with patch.dict(os.environ, {}, clear=False), \
             patch.object(sys, "frozen", False, create=True):
            os.environ.pop("PYMEDIA_CONFIG_PATH", None)
            if hasattr(sys, "_MEIPASS"):
                delattr(sys, "_MEIPASS")
            base = utils.get_base_dir()
            expected = Path(__file__).resolve().parent.parent
            self.assertEqual(base, expected)

    def test_get_base_dir_onefile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake = Path(tmpdir) / "meipass"
            fake.mkdir()
            with patch.object(sys, "_MEIPASS", str(fake), create=True), \
                 patch.object(sys, "frozen", True, create=True):
                base = utils.get_base_dir()
                self.assertEqual(Path(base), fake)

    def test_get_base_dir_frozen_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exe = Path(tmpdir) / "bin" / "myexe"
            exe.parent.mkdir(parents=True)
            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "executable", str(exe)), \
                 patch.object(sys, "platform", "linux"):
                if hasattr(sys, "_MEIPASS"):
                    delattr(sys, "_MEIPASS")
                base = utils.get_base_dir()
                self.assertEqual(base, exe.parent)

    def test_get_base_dir_darwin_app(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = Path(tmpdir) / "MyApp.app"
            macos = app / "Contents" / "MacOS"
            resources = app / "Contents" / "Resources"
            resources.mkdir(parents=True)
            macos.mkdir(parents=True)
            exe = macos / "MyApp"
            exe.write_text("")

            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "executable", str(exe)), \
                 patch.object(sys, "platform", "darwin"):
                if hasattr(sys, "_MEIPASS"):
                    delattr(sys, "_MEIPASS")
                base = utils.get_base_dir()
                self.assertEqual(Path(base), resources)

    def test_layered_config_readonly_toml_and_user_diff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            user_cfg_file = Path(tmpdir) / "user_config.json"
            toml_path = utils.find_config_path()
            self.assertIsNotNone(toml_path)
            orig_toml_bytes = toml_path.read_bytes()

            with patch.dict(os.environ, {"PYMEDIA_USER_CONFIG_PATH": str(user_cfg_file)}, clear=False):
                default_cfg = utils.load_default_config()
                updated = utils.update_user_config({"elevenlabs": {"srt_max_chars": 44}})
                self.assertEqual(updated["elevenlabs"]["srt_max_chars"], 44)
                self.assertTrue(user_cfg_file.exists())

                saved_diff = json.loads(user_cfg_file.read_text(encoding="utf-8"))
                self.assertEqual(saved_diff, {"elevenlabs": {"srt_max_chars": 44}})

                full_copy = copy.deepcopy(updated)
                full_copy["groq"]["model"] = "custom-model"
                utils.save_project_config(full_copy)
                self.assertEqual(toml_path.read_bytes(), orig_toml_bytes)

                with patch.dict(os.environ, {"PYMEDIA_GROQ_API_KEY": "env_secret"}, clear=False):
                    env_cfg = utils.load_project_config(force_reload=True)
                    self.assertEqual(env_cfg["groq"]["api_key"], "env_secret")

                self.assertTrue(utils.reset_user_config())
                self.assertFalse(user_cfg_file.exists())
                utils.load_project_config(force_reload=True)


if __name__ == "__main__":
    unittest.main()
