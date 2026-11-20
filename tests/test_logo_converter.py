import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyMediaTools.core.mediaconvert import LogoConverter
from pyMediaTools.core.factory import _build_modes


class TestLogoConverter(unittest.TestCase):
    def test_logoconverter_single_legacy(self):
        params = {
            "x": 10,
            "y": 20,
            "logo_w": 50,
            "logo_h": 60,
            "target_w": 200,
            "target_h": 100,
            "logo_path": "assets/hailuoDream.png",
        }
        conv = LogoConverter(params)
        self.assertEqual(len(conv.logos), 1)
        entry = conv.logos[0]
        self.assertEqual(entry["x"], 10)
        self.assertEqual(entry["y"], 20)
        self.assertEqual(entry["w"], 50)
        self.assertEqual(entry["h"], 60)
        self.assertEqual(Path(entry["path"]).name, "hailuoDream.png")
        self.assertEqual(conv.target_w, 200)
        self.assertEqual(conv.target_h, 100)

    def test_logoconverter_multiple(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            f1 = tmp_path / "l1.png"
            f2 = tmp_path / "l2.png"
            f1.write_text("")
            f2.write_text("")

            with patch(
                "pyMediaTools.core.mediaconvert.get_resource_path",
                side_effect=lambda p: Path(p),
            ):
                params = {
                    "target_w": 100,
                    "target_h": 100,
                    "logos": [
                        {"x": 1, "y": 2, "logo_w": 10, "logo_h": 20, "logo_path": str(f1)},
                        {"x": 3, "y": 4, "logo_w": 5, "logo_h": 6, "logo_path": str(f2), "blur": False},
                    ],
                }
                conv = LogoConverter(params)
                self.assertEqual(len(conv.logos), 2)

                recorded = {}

                def fake_proc(cmd, duration, monitor, name):
                    recorded["cmd"] = cmd

                conv.process_ffmpeg = fake_proc
                conv.process_file(Path("in.mp4"), Path("out"), duration=1.0)

                self.assertEqual(recorded["cmd"].count("-i"), 3)
                self.assertIn(str(f1), recorded["cmd"])
                self.assertIn(str(f2), recorded["cmd"])
                cmdstr = " ".join(recorded["cmd"])
                self.assertEqual(cmdstr.count("boxblur"), 1)
                self.assertIn("gt(iw/ih", cmdstr)
                self.assertIn("crop=100:100", cmdstr)

    def test_factory_loads_dream_mode(self):
        toml_data = {
            "modes": {
                "dream": {
                    "class": "LogoConverter",
                    "params": {
                        "logos": [
                            {"x": 0, "y": 0, "logo_path": "a.png", "logo_w": 10, "logo_h": 10},
                            {"x": 5, "y": 5, "logo_path": "b.png", "logo_w": 20, "logo_h": 20, "blur": False},
                        ]
                    },
                }
            }
        }
        modes = _build_modes(toml_data)
        self.assertIn("dream", modes)
        self.assertIsInstance(modes["dream"]["params"]["logos"], list)
        self.assertEqual(len(modes["dream"]["params"]["logos"]), 2)
        self.assertIs(modes["dream"]["params"]["logos"][1].get("blur"), False)


if __name__ == "__main__":
    unittest.main()
