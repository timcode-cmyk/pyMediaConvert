#!/usr/bin/env python3
"""
yt-dlp 备份处理改进 - 单元测试
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyMediaTools.core.ytdlp_updater import YtDlpVersionManager


class TestBackupImprovements(unittest.TestCase):
    def test_is_yt_dlp_corrupted(self):
        """测试源码完整性检查（在临时目录中安全隔离运行）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = YtDlpVersionManager()
            missing_dir = os.path.join(tmpdir, "missing_yt_dlp")
            manager.yt_dlp_dir = missing_dir
            self.assertTrue(manager._is_yt_dlp_corrupted())

            # 创建一个损坏的 yt_dlp 目录（缺关键文件）
            os.makedirs(missing_dir, exist_ok=True)
            self.assertTrue(manager._is_yt_dlp_corrupted())

    def test_cleanup_old_backups(self):
        """测试旧备份清理功能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = YtDlpVersionManager()
            manager.backup_dir = tmpdir
            manager.metadata_file = os.path.join(tmpdir, "update_metadata.json")

            backup_names = [
                "yt_dlp_backup_2026.02.10_20250216_120530",
                "yt_dlp_backup_2026.02.04_20250215_143200",
                "yt_dlp_backup_2026.01.20_20250214_100000",
                "yt_dlp_backup_2026.01.10_20250213_090000",
                "yt_dlp_backup_2025.12.20_20250212_080000",
            ]

            metadata = {}
            for name in backup_names:
                backup_path = os.path.join(tmpdir, name)
                os.makedirs(backup_path)
                Path(backup_path, "version.py").write_text(
                    f"__version__ = '{name.split('_')[3]}'\n", encoding="utf-8"
                )
                metadata[name] = {
                    "version": name.split("_")[3],
                    "timestamp": "2025-02-16T00:00:00",
                    "path": backup_path,
                }

            Path(manager.metadata_file).write_text(
                json.dumps(metadata, indent=2), encoding="utf-8"
            )

            deleted = manager._cleanup_old_backups(keep_latest=3)
            remaining_backups = [
                d for d in os.listdir(tmpdir) if d.startswith("yt_dlp_backup_")
            ]
            updated_metadata = json.loads(
                Path(manager.metadata_file).read_text(encoding="utf-8")
            )

            self.assertEqual(deleted, 2)
            self.assertEqual(len(remaining_backups), 3)
            self.assertEqual(len(updated_metadata), 3)


if __name__ == "__main__":
    unittest.main()
