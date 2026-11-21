# pyMediaTools 项目结构与编码规范指令

本文档定义 `pyMediaTools` 项目的架构分层、编码准则与开发约束，所有后续维护、重构与新功能开发均须严格遵守。

---

## 1. 项目目录结构与分层职责

```text
pyMediaTools/
├── MediaTools.py               # 唯一应用入口：编码修复、日志初始化、QApplication、模块挂载
├── config.toml                 # 媒体转换模式与全局静态配置
├── assets/                     # 字体、图标、水印图片、预设字幕样式
├── bin/                        # 跨平台内置二进制 (ffmpeg / ffprobe)
├── pyMediaTools/
│   ├── __init__.py             # 包入口导出 setup_logging / get_logger / config
│   ├── logging_config.py       # 全局 RotatingFileHandler 与 sys.excepthook
│   ├── utils.py                # 跨环境路径寻址 (PyInstaller/Nuitka/Dev)、TOML 读写、可执行文件定位
│   ├── core/                   # 核心业务与基础设施层（严禁包含 UI 控件或弹窗）
│   │   ├── config.py / factory.py  # 从 config.toml 动态构建 MODES 映射
│   │   ├── ffmpeg_utils.py         # 统一的 FFmpeg/FFprobe 检测与媒体信息提取
│   │   ├── cjk_tokenizer.py        # CJK 分词工具
│   │   ├── subtitle_builder.py     # 字幕智能断句与构建
│   │   ├── subtitle_writer.py      # SRT/VTT/ASS 字幕导出
│   │   └── ...                     # 各垂直领域核心逻辑 (mediaconvert, videocut, elevenlabs 等)
│   └── ui/                     # PySide6 界面层
│       ├── __init__.py             # 统一导出挂载至主界面的各功能模块 Widget
│       ├── dashboard_shell.py      # 无边框主窗体框架、侧边栏导航、QStackedWidget、主题监听
│       ├── styles.py               # 跨平台动态 QSS 生成器 (apply_common_style)
│       ├── qss_resources.py        # 主框架深/浅色 QSS 资源
│       ├── settings_dialog.py      # 全局设置弹窗
│       └── *_ui.py                 # 各功能模块界面
└── tests/                      # 自动化测试目录 (命名必须为 test_*.py)
```

---

## 2. 强制编码与架构规范

### 2.1 分层与职责单一（SRP）
- **严禁重复造轮子**：FFmpeg 检测与调用统一复用 `pyMediaTools.core.ffmpeg_utils`；CJK 分词统一复用 `cjk_tokenizer`；字幕写入统一复用 `subtitle_writer`。
- **单文件行数上限**：单个 `.py` 文件不应超过 **1000 行**。超过时必须按职责拆分为独立子模块（例如：`*_dialogs.py`、`*_widgets.py`、`*_worker.py`）。
- **清理死代码**：已下线或废弃的功能模块不得以整文件注释的方式长期保留在仓库中。

### 2.2 UI 样式与跨平台一致性
- **统一动态样式**：所有功能模块 Widget 在初始化时必须调用 `apply_common_style(self)`。
- **严禁硬编码颜色与平台字体**：
  - 禁止在 `setStyleSheet()` 中写死 `#333`、`#555`、`#FFFFFF` 等暗色/亮色固定颜色，应使用 `palette(text)`、`palette(mid)`、`palette(highlight)` 或基于 `QPalette.Window.lightness() < 128` 动态计算 `rgba(...)`。
  - 禁止硬编码 `QFont("Segoe UI", ...)`，统一依赖 `styles._get_base_font()` 适配 macOS / Windows / Linux。
- **控件选择器规范**：主操作按钮统一通过 `btn.setObjectName("PrimaryButton")` 匹配 `styles.py` 中的主按钮样式（不得使用未定义的属性选择器）。

### 2.3 异步线程与子进程规范
- **防阻塞**：主 UI 线程禁止任何网络请求（`requests`）、`time.sleep` 或同步子进程阻塞。
- **统一线程模型**：推荐使用 `QObject` Worker + `QThread.moveToThread` 模式；窗口销毁或退出时必须安全停止并等待后台线程结束。
- **Windows 子进程无窗口**：所有调用外部 CLI（`ffmpeg`、`ffprobe`、`yt-dlp`）的 `subprocess.run` 必须传入 `creationflags=get_subprocess_creation_flags()`（Windows 下自动启用 `CREATE_NO_WINDOW`），并指定 `encoding="utf-8", errors="replace"`。

### 2.4 配置、日志与异常处理
- **三层配置体系（严禁写入 `config.toml`）**：
  - `config.toml` 仅作为**只读的初始化出厂默认配置**，任何运行期逻辑严禁修改或写回 `config.toml`。
  - **优先级（低 -> 高）**：
    1. **Layer 1（只读默认）**：`config.toml`（通过标准库 `tomllib` 解析）。
    2. **Layer 2（用户持久化配置）**：系统标准用户配置目录下的 `user_config.json`（由 `utils.get_user_config_path()` 管理，仅保存相对默认值的 diff 差集），以及界面偏好/API Key 的 `QSettings("pyMediaTools", "<ModuleGroup>")`。全局设置保存后应发射信号触发已加载模块热更新（`reload_settings()`）。
    3. **Layer 3（环境变量覆写）**：支持通过 `PYMEDIA_*` 及标准密钥环境变量（如 `PYMEDIA_ELEVENLABS_API_KEY` / `ELEVENLABS_API_KEY`、`PYMEDIA_GROQ_API_KEY` / `GROQ_API_KEY`、`PYMEDIA_GLADIA_API_KEY` / `GLADIA_API_KEY`、`PYMEDIA_DOWNLOAD_DIR`）以最高优先级动态覆写。
- **日志与异常**：禁止使用 `print()` 输出运行日志，统一使用 `get_logger(__name__)`；禁止使用裸 `except:`，必须捕获明确异常并记录上下文。

### 2.5 测试规范
- 所有测试文件必须位于 `tests/` 目录且以 `test_*.py` 命名，使用标准包导入（`from pyMediaTools... import ...`），禁止临时杂乱脚本留在 `tests/` 目录。
- 所有测试依赖（如 `pytest`）应与 `requirements.txt` 保持同步。
