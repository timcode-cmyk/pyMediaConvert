# Copilot / Agent instructions for pyMediaConvert

Purpose: concise, actionable knowledge to get an AI coding agent productive quickly.

## 🚀 Quick entrypoints
- GUI: `python app.py` (starts PySide6 app; widgets live under `pyMediaTools/ui/` — see `MediaConverterWidget`, `DownloaderWidget`, `VideoDownloaWidget`, `ElevenLabsWidget`).
- CLI: `python cli.py -m <mode> -d <input_dir> -o <out_dir>` (modes come from `config.MODES`).
- Tests: `pytest -q` from project root (unit tests in `tests/`; many integration-style tests are commented out due to binary deps).

## 🏗 Big-picture architecture
- Core responsibility: discover input files, run FFmpeg-based conversions, report progress to a Monitor (GUI or CLI).
- Main layers:
  - UI layer: `pyMediaTools/ui/` (PySide6 widgets, progress/stop UI)
  - Orchestration: `pyMediaTools/core/mediaconvert.py` (MediaConverter + concrete converters)
  - Config: `pyMediaTools/core/factory.py` (loads `config.toml` into `MODES`); `pyMediaTools/core/config.py` provides fallback defaults
  - Utilities: `pyMediaTools/utils.py` (path resolution, BIN/ASSET dirs, ffmpeg/ffprobe helpers)
- Why this structure: decouple UI from converter logic so converters can run in CLI, GUI, or tests with the same Monitor API.

## 🔑 Key files (read first)
- `pyMediaTools/core/mediaconvert.py` — implement/modify converters here. Key behaviors to respect:
  - `find_files()` only scans top-level of an input dir (not recursive) and skips files already matching `output_ext`.
  - `process_ffmpeg(cmd, duration, monitor, name)` uses `QProcess`, merges channels, enforces `-progress -` and parses `out_time*` + `progress=end` lines; uses `waitForReadyRead()` + `processEvents()` to avoid deadlocks in packaged apps.
  - `_detect_hardware_encoders()` calls `ffmpeg -encoders` and caches results in `_GLOBAL_ENCODER_CACHE` (clear in tests if needed).
- `pyMediaTools/core/factory.py` — maps TOML `class` strings to actual classes via `CLASS_MAP`. Validate any new `class` names here.
- `pyMediaTools/utils.py` — `get_base_dir()` supports dev, PyInstaller (`sys._MEIPASS`), and frozen executables; `BIN_DIR` / `ASSET_DIR` conventions; `get_ffmpeg_exe()` always returns bundled path (and tries to ensure exec bit).
- `pyMediaTools/logging_config.py` — RotatingFileHandler; logs go to `get_base_dir()/pyMediaConvert.log`.

## ✅ Important conventions & gotchas
- Config discovery order: env `PYMEDIA_CONFIG_PATH`/`PYMEDIA_CONFIG` → project `config.toml` (via `get_base_dir`) → cwd `config.toml` → parent directories. `load_project_config()` caches result—tests may need to reset `_PROJECT_CONFIG`.
- Monitor API (use exactly):
  - `monitor.update_file_progress(current_seconds, total_seconds, file_name)`
  - `monitor.update_overall_progress(completed, total, message)`
  - `monitor.check_stop_flag()` → boolean (should be polled to stop processing)
- FFmpeg integration:
  - Prefer `-progress -` and parse `out_time`, `out_time_ms`, `out_time_us` and `progress=end` lines. Avoid relying only on stderr time= parsing.
  - `process_ffmpeg` enforces `-nostats` and `-progress -` and uses `QProcess.waitForReadyRead()` for stable progress reading in packaged apps.
- Packaging notes: always include `bin/` and `assets/` in bundled builds (`--include-data-dir=bin=bin`, `--include-data-dir=assets=assets` for Nuitka); ensure executability on POSIX (`chmod +x`).

## 🧪 Testing and development tips
- Unit tests: run `pytest -q`. Many tests are integration-like and may be commented out because they require `ffmpeg` in `BIN_DIR`.
- Monkeypatching advice:
  - To fake bundled binaries, monkeypatch `pyMediaTools.utils.BIN_DIR` to point at a tmpdir and create `ffmpeg`/`ffprobe` stubs.
  - To reload config during tests, reset `pyMediaTools.utils._PROJECT_CONFIG = None` or monkeypatch `find_config_path()`.
  - Clear `_GLOBAL_ENCODER_CACHE` between tests when testing encoder detection logic.
- CI-friendly tests: prefer mocking subprocess calls (e.g., mocking `subprocess.run` for `-encoders`) instead of invoking real ffmpeg.

## 🔧 How to add a mode (quick)
1. Implement converter in `pyMediaTools/core/mediaconvert.py` by adding a subclass and implementing `process_file(self, input_path, output_path, duration, monitor)`.
2. Add a `[modes.my_mode]` section to `config.toml` or add to `MODES` fallback in `pyMediaTools/core/config.py` for tests/workflow.
3. If using TOML `class` names, add mapping to `CLASS_MAP` in `pyMediaTools/core/factory.py`.

## 💡 Implementation notes for contributors
- Prefer `get_resource_path()` for asset lookups so packaging works (it uses `get_base_dir()`).
- Respect `monitor.check_stop_flag()` so UI stop is responsive.
- Keep CLI-mode differences in mind (`use_cli=True` enables tqdm-based overall progress bars).

---
If anything is missing or you want more detail (examples, tests to add, or packaging specifics), tell me which section to expand and I’ll iterate. ✨
*