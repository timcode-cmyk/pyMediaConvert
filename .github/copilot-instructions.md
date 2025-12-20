# Copilot / Agent instructions for pyMediaConvert

Purpose: give an AI code agent the concise, actionable project knowledge needed to be productive immediately.

- 🚀 Quick entrypoints
  - GUI: `python app.py` (launches PySide6 UI; see `app.py` and `pyMediaTools/ui/`)
  - CLI: `python cli.py -m <mode> -d <input_dir> -o <out_dir>` (modes are keys in `MODES`)
  - Tests: run `pytest -q` from project root (tests live in `tests/`)

- 🔑 Key files & what they mean
  - `config.toml` — primary modes configuration loaded by `pyMediaTools/core/factory.py` (env override: `PYMEDIA_CONFIG_PATH` / `PYMEDIA_CONFIG`).
  - `pyMediaTools/core/factory.py` — maps TOML `modes.*` → converter classes (via `CLASS_MAP`); validate `class` names here.
  - `pyMediaTools/core/config.py` — compatibility fallback with inline defaults if TOML missing.
  - `pyMediaTools/core/mediaconvert.py` — core abstractions:
    - `MediaConverter` base class: file discovery (`find_files`), `process_ffmpeg` (QProcess + `-progress -` parsing), encoder detection (`-encoders`).
    - Concrete converters: `LogoConverter`, `H264Converter`, `Mp3Converter`, etc. Implement `process_file` to add new converters.
  - `pyMediaTools/utils.py` — resource resolution helpers (`get_base_dir`, `BIN_DIR`, `ASSET_DIR`, `get_resource_path`), and binary helpers (`get_ffmpeg_exe`, `get_ffprobe_exe`, `_ensure_executable`).
  - `pyMediaTools/logging_config.py` — RotatingFileHandler, logs are written under `get_base_dir()` (useful for debugging packaged apps).

- 🧩 Important conventions & gotchas (do not change lightly)
  - Modes shape: `{ 'class': <ClassNameStr>, 'params': {...}, 'support_exts': [...], 'output_ext': '_x.mp4' }`. `factory.py` converts the `class` string into an actual class using `CLASS_MAP`.
  - `find_files` only scans the top-level of the input directory (no recursive traversal) and filters out files that already end with configured `output_ext` to avoid reprocessing outputs.
  - Progress parsing: uses FFmpeg `-progress -` (pipe) and QProcess `readyRead` callbacks; prefer emitting `out_time*` and `progress=end` semantics when changing ffmpeg invocation.
  - Monitor API expected by converters (passed as `monitor`):
    - `monitor.update_file_progress(current_seconds, total_seconds, file_name)`
    - `monitor.update_overall_progress(completed, total, message)`
    - `monitor.check_stop_flag()` → boolean to abort
  - Hardware encoder detection: `MediaConverter._detect_hardware_encoders()` runs `ffmpeg -encoders` and looks for names like `nvenc`, `qsv`, `videotoolbox`.

- 🧪 Tests & development workflow
  - Unit tests use `pytest`. Focus on `tests/test_utils.py` for resource resolution and `ffmpeg` retrieval semantics.
  - For integration/debugging run local ffmpeg in `bin/` (project prefers bundled `bin/ffmpeg` and `bin/ffprobe`) — tests may monkeypatch `BIN_DIR`.

- 📦 Packaging / distribution notes
  - Project is packaged with Nuitka in `README.md` examples. Important: include `bin` and `assets` into the bundle (`--include-data-dir=bin=bin`).
  - Runtime path resolution supports PyInstaller onefile (`sys._MEIPASS`) and frozen executables (`sys.executable`). Use `get_base_dir()` to find assets.
  - Ensure embedded ffmpeg/ffprobe are executable on POSIX (`_ensure_executable` attempts to add exec bit).

- 🔍 Debugging tips
  - Logs: check `pyMediaConvert.log` at `get_base_dir()` (rotating handler). Add more logging in `mediaconvert.py` around `process_ffmpeg` and `_parse_ffmpeg_output` when investigating progress issues.
  - FFmpeg errors often surface on stderr; `process_ffmpeg` captures and logs these messages.
  - Packaging gotchas: progress may fail if ffmpeg binary missing or lacks exec permission, or if the app isn't including `bin/`.

- ➕ How to add a new mode (example)
  1. Implement converter subclass in `pyMediaTools/core/mediaconvert.py` with `process_file(self, input_path, output_path, duration, monitor)`.
  2. Add a `[modes.my_mode]` section in `config.toml` (or add to `MODES` fallback in `core/config.py`).
  3. Map the class name in `factory.py` `CLASS_MAP` if you use TOML strings.

- ✅ Keep PRs focused and executable: include a small test if behaviour changes (e.g., `tests/test_*.py`), and describe packaging impact (assets or bin changes).

If anything above is unclear or you want a different focus (more on tests, packaging, or refactor suggestions), tell me which area to expand.  

---
*(Generated from repository scan: `app.py`, `cli.py`, `config.toml`, `pyMediaTools/core/*`, `pyMediaTools/utils.py`, `README.md`, `tests/`.)*