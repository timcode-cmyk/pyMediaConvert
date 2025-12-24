# Copilot / Agent instructions for pyMediaConvert

Purpose: concise, actionable knowledge to get an AI coding agent productive quickly.

## 🚀 Quick entrypoints
- GUI: `python app.py` — starts the PySide6 app. Widgets live under `pyMediaTools/ui/` (look at `MediaConverterWidget`, `DownloaderWidget`, `VideoDownloaWidget`, `ElevenLabsWidget`).
- CLI: `python cli.py -m <mode> -d <input_dir> -o <out_dir>` — modes are defined from `config.MODES` (see `config.toml` and `pyMediaTools/core/config.py`).
- Tests: `pytest -q` from repo root. Note: many integration-style tests that exercise real binaries are commented out or require `ffmpeg` in `BIN_DIR`.
- Requirements: see `requirements.txt` (minimal) and `requirementsall.txt` (full/dev extras).

## 🏗 Big-picture architecture
- Goal: discover input files, run FFmpeg-based conversions, and report progress to a Monitor (GUI or CLI) while keeping converters testable and packagable.
- Layers:
  - UI: `pyMediaTools/ui/` (PySide6 widgets). Keep UI thin — it uses a Monitor interface.
  - Orchestration: `pyMediaTools/core/mediaconvert.py` (MediaConverter + concrete converters). Converters implement `process_file(...)` and call `process_ffmpeg(...)`.
  - Config & wiring: `pyMediaTools/core/factory.py` (maps TOML `class` names to concrete classes via `CLASS_MAP`) and `pyMediaTools/core/config.py` (fallbacks and canonical `MODES`).
  - Utilities: `pyMediaTools/utils.py` (paths, asset/bin helpers, `get_ffmpeg_exe()`, `get_base_dir()` which supports dev, PyInstaller and frozen executables).
- Design rationale: decouple conversion logic from presentation so converters work in CLI, GUI and tests with one Monitor API.

## 🔑 Key files and quick notes
- `pyMediaTools/core/mediaconvert.py`
  - `find_files()` scans only the top-level of an input dir and ignores files already matching `output_ext`.
  - `process_ffmpeg(cmd, duration, monitor, name)` uses `QProcess`, merges stdout/stderr, enforces `-nostats -progress -`, parses `out_time*` and `progress=end` and calls `monitor.update_file_progress(...)`.
  - `_detect_hardware_encoders()` calls `ffmpeg -encoders` and caches results in `_GLOBAL_ENCODER_CACHE` (tests should clear this when needed).
- `pyMediaTools/core/factory.py` — add new converter `class` names here (validate mapping to avoid silent misconfigs).
- `pyMediaTools/core/elevenlabs.py` — integration points with ElevenLabs; check API usage patterns and credentials handling.
- `pyMediaTools/utils.py` — use `get_resource_path()` for bundled asset lookups; `BIN_DIR` and `ASSET_DIR` are the canonical locations for binaries and assets (ffmpeg, ffprobe, aria2c live in `bin/`).
- `pyMediaTools/logging_config.py` — logs to `get_base_dir()/pyMediaConvert.log` via RotatingFileHandler.

## ✅ Project conventions & gotchas (must follow)
- Config discovery: env `PYMEDIA_CONFIG_PATH` / `PYMEDIA_CONFIG` → project `config.toml` (via `get_base_dir()`) → cwd `config.toml` → parent dirs. `load_project_config()` caches the result — to re-read during tests reset `_PROJECT_CONFIG`.
- Monitor API (use exactly these calls):
  - `monitor.update_file_progress(current_seconds, total_seconds, file_name)`
  - `monitor.update_overall_progress(completed, total, message)`
  - `monitor.check_stop_flag()` → boolean (poll to support stop)
- FFmpeg: always prefer `-progress -` parsing (fields: `out_time`, `out_time_ms`, `out_time_us`, `progress=end`) instead of relying on stderr time= lines; `process_ffmpeg` deliberately uses `waitForReadyRead()` and `processEvents()` to avoid deadlocks in packaged builds.
- Packaging: include `bin/` and `assets/` in packaged builds (Nuitka example: `--include-data-dir=bin=bin --include-data-dir=assets=assets`); ensure exec bits are set on POSIX (`chmod +x`). See `dist-nuitka/` for build artifacts and examples.

## 🧪 Tests & how to make them reliable
- Preferred: unit tests mock subprocess and FFmpeg outputs (avoid calling real ffmpeg in CI).
- To simulate bundled binaries in tests: monkeypatch `pyMediaTools.utils.BIN_DIR` to a tmpdir and create executable stubs named `ffmpeg`/`ffprobe` (small scripts that emit expected progress lines).
- To reload config during tests: set `pyMediaTools.utils._PROJECT_CONFIG = None` or monkeypatch `find_config_path()`.
- When testing encoder detection, clear `_GLOBAL_ENCODER_CACHE` to avoid cross-test leakage.
- Many integration tests are commented out for maintainability — add small unit tests around parsing and Monitor calls when possible.

## 🔧 Typical tasks & where to change things
- Add a new converter: implement a subclass in `pyMediaTools/core/mediaconvert.py` and implement `process_file(...)`, then add a `[modes.my_mode]` entry to `config.toml` and ensure the TOML `class` string maps in `pyMediaTools/core/factory.py`.
- Change FFmpeg behavior: update `process_ffmpeg()` and add tests that assert parsing of `-progress -` output (simulate with stub ffmpeg script).
- Add UI elements: put widgets under `pyMediaTools/ui/` and name them consistently (e.g., `XxxWidget`), then wire to existing monitors.

## ⚙️ Build & Dev workflow (quick checklist)
- Start GUI: `python app.py` (for live dev). Use PySide tools to inspect widgets.
- CLI conversions: `python cli.py -m <mode> -d <in_dir> -o <out_dir>`.
- Run tests: `pytest -q` (or `pytest tests/my_test.py -q`).
- Packaging: inspect `dist-nuitka/` for example outputs; follow `--include-data-dir=bin=bin --include-data-dir=assets=assets` and ensure exec bits.
- Logs: check `pyMediaConvert.log` at `get_base_dir()` for runtime issues.

---
If you'd like, I can:
- Trim this further to 20–30 lines for a short quick-reference card ✅
- Add a small checklist for reviewers that verifies Monitor calls and `-progress` parsing ✅
Tell me which you'd prefer and I’ll iterate. ✨
