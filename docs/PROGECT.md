# 4. 全项目模块、类与函数接口详尽文档

---

## 4.1 根目录与基础配置模块

### 1. [MediaTools.py](file:///Users/tim/Documents/shell/pyMediaConvert/MediaTools.py) (程序主入口)
- **职责**：桌面端主应用程序启动入口，负责 UTF-8 输出重定向、全局日志捕获、Nuitka 打包指令配置、Qt 样式初始化与主窗口挂载。
- **全局变量**：
  - `__version__ = "1.16.2"`：当前应用版本号。
- **函数定义**：
  - `create_main_window() -> DashboardWindow`
    - **功能**：初始化所有业务功能 Widget 并组装成包含 6 个标签页的元组列表 `modules`。
    - **返回**：已配置模块的 `DashboardWindow` 实例。

### 2. [pyMediaTools/__init__.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/__init__.py)
- **类 `AppContext`**：
  - `__init__(self)`：初始化应用上下文。
  - `load_config_from_toml(self) -> dict`：兼容性加载转换模式字典。

### 3. [pyMediaTools/logging_config.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/logging_config.py) (日志配置)
- **函数定义**：
  - `setup_logging(log_level=logging.INFO, filename="pyMediaConvert.log") -> logging.Logger`
    - **功能**：配置全局 `RotatingFileHandler`（单文件最大 5MB，保留 3 份备份），并挂载 `sys.excepthook` 全局异常钩子，捕获未处理崩溃。
  - `get_logger(name: str) -> logging.Logger`
    - **功能**：按模块名获取 Logger 实例，如尚未初始化则自动触发 `setup_logging()`。

### 4. [pyMediaTools/utils.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/utils.py) (通用底层工具)
- **函数与常量定义**：
  - `BASE_DIR: Path`：项目根目录路径。
  - `BIN_DIR: Path`：内置二进制工具目录 (`BASE_DIR / "bin"`)。
  - `ASSET_DIR: Path`：内置静态资源目录 (`BASE_DIR / "assets"`)。
  - `get_base_dir() -> Path`：跨环境（开发环境、PyInstaller 解包目录 `sys._MEIPASS`、Nuitka 可执行文件目录）识别项目真实基准路径。
  - `find_config_path() -> Optional[Path]`：按环境变量 `PYMEDIA_CONFIG_PATH` -> 项目根目录 -> 当前工作目录 -> 父目录链顺序查找 `config.toml`。
  - `load_project_config() -> dict`：加载并全局缓存 `config.toml` 配置字典。
  - `save_project_config(config_dict: dict)`：将更新后的配置字典写回 `config.toml`。
  - `get_elevenlabs_config() -> dict`：快捷获取 ElevenLabs 相关子配置。
  - `get_resource_path(*parts) -> Path`：拼接获取 assets 或其他静态资源的绝对路径。
  - `get_ffmpeg_exe() -> str`：返回当前操作系统平台对应的 `ffmpeg` 可执行文件绝对路径，并在 Unix 平台确保赋予可执行权限 (`+x`)。
  - `get_ffprobe_exe() -> str`：返回当前平台对应的 `ffprobe` 可执行文件绝对路径。
  - `get_default_download_dir() -> Path`：获取默认下载目录（优先读取配置文件，默认回退到系统 Downloads 目录）。

---

## 4.2 核心业务逻辑层 (`pyMediaTools/core/`)

### 1. [config.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/config.py) & [factory.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/factory.py) (模式配置工厂)
- **职责**：将 `config.toml` 中的 `[modes.*]` 转码规则映射为对应的转换器类实例。
- **类映射表 `CLASS_MAP`**：包含 `LogoConverter`, `AddCustomLogo`, `AddAssText`, `H264Converter`, `DnxhrConverter`, `PngConverter`, `Mp3Converter`, `WavConverter`, `VideoTooboxConverter`。
- **函数定义**：
  - `_load_toml(path: Path) -> dict`：跨版本解析 TOML 数据。
  - `_build_modes(toml_data: dict) -> dict`：解析配置节点，校验类合法性，构造 `MODES` 映射字典。
  - `get_modes() -> dict`：获取当前转码模式字典的深拷贝。

---

### 2. [mediaconvert.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/mediaconvert.py) (多媒体批量转码引擎)

#### 抽象基类 `MediaConverter(ABC)`
所有转码处理器的父类，封装了文件检索、FFmpeg 硬件探测与管道进度解析。
- **属性**：
  - `files: list[Path]`：待处理的文件列表。
  - `support_exts: set[str]`：支持的输入后缀名集合。
  - `output_ext: str`：输出后缀名。
  - `available_encoders: dict`：当前机器支持的硬件编码器。
- **核心方法**：
  - `_check_ffmpeg_path()`：校验 bin 目录下 ffmpeg/ffprobe 存在性。
  - `_format_ffmpeg_path(path: str) -> str`：转义路径供 FFmpeg 滤镜参数使用。
  - `_verify_encoder_usability(name: str) -> bool`：执行 0.01s 空转测试，验证硬编驱动真实可用性。
  - `_detect_hardware_encoders()`：执行 `ffmpeg -encoders` 正则匹配 NVENC/VideoToolbox/QSV/AMF 编码器。
  - `_get_video_codec_params(force_codec: str = None) -> tuple[str, str, str]`：智能判定最佳编码器及预设。
  - `_get_extra_codec_args(video_codec: str) -> list[str]`：生成针对指定硬件编码器的比特率/CQ 质量参数。
  - `find_files(directory: Path)`：递归检索输入路径下匹配后缀的文件，自动过滤已生成的目标文件。
  - `get_duration(file_path: Path) -> float`：使用 `QProcess` 调用 ffprobe 安全获取音视频总时长（秒）。
  - `_parse_ffmpeg_output()`：实时解析 FFmpeg `-progress -` 管道输出（`out_time_us` / `out_time_ms`），通过 `monitor` 驱动界面进度条。
  - `process_ffmpeg(cmd: list, duration: float, monitor, input_file_name: str)`：启动 QProcess 执行命令，并利用 `QCoreApplication.processEvents()` 维持 GUI 响应与中断响应。
  - `@abstractmethod process_file(input_path: Path, output_path: Path, duration: float, monitor=None)`：子类具体实现的转码逻辑。
  - `run(input_dir: Path, out_dir: Path, monitor)`：批处理调度主循环。

#### 派生转换器类
1. **`LogoConverter(MediaConverter)`**：
   - 复杂的视频缩放、模糊遮罩、Logo 图层及文本/ASS 水印叠加器（通过构建复杂 `-filter_complex` 实现多图层画中画与毛玻璃模糊）。
2. **`AddCustomLogo(MediaConverter)`**：
   - 单纯在视频/图片上通过 `drawtext` 滤镜添加 AI 标识文本。
3. **`AddAssText(MediaConverter)`**：
   - 使用 `ass=` 滤镜将 `.ass` 字幕硬压入视频。
4. **`H264Converter(MediaConverter)`**：
   - 转换为标准 MP4 (H.264)，音频直通 `copy`，开启 `-movflags +faststart`。
5. **`DnxhrConverter(MediaConverter)`**：
   - 专业剪辑中间格式转码（DNxHR HQ / HQX 10bit MOV，PCM S16LE 音频）。
6. **`PngConverter(MediaConverter)`**：
   - 图片格式转 RGBA PNG。
7. **`Mp3Converter(MediaConverter)` & `WavConverter(MediaConverter)`**：
   - 音频抽取与转码为 MP3 / WAV。
8. **`VideoTooboxConverter(MediaConverter)`**：
   - macOS 专用的 `h264_videotoolbox` 高性能硬件加速转码器。

---

### 3. [vidoecut.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/vidoecut.py) (场景切分与分割核心)
- **独立辅助函数**：
  - `get_available_ass_files() -> dict`：扫描 `assets/` 下全部 `.ass` 文件。
  - `get_available_fonts() -> dict`：扫描 `assets/` 下全部 `.ttf` 字体文件。
  - `_get_video_duration(file_path: Path, debug: bool = False) -> float`：ffprobe 时长获取。
  - `get_video_fps(video_path, debug: bool = False) -> float`：获取视频实际 FPS。

- **核心类 `SceneCutter`**：
  - `__init__(self, monitor=None, debug: bool = False, log_dir: Path = None, font_name: str = None)`
  - `_detect_scenes(video_path: Path, threshold: float, fps: float, debug_log_file: Path | None) -> list[float]`
    - **算法**：利用 OpenCV 读取视频帧 -> 缩放到 320px 灰度图 -> 计算相邻帧绝对差值均值 (`cv2.absdiff().mean()`) -> 阈值判定与波峰聚合（识别硬切与叠化转场）-> 过滤短于 0.5s 碎片。
  - `_align_to_frame(times: list[float], fps: float) -> list[float]`：将时间戳精确对齐到视频帧边界，避免切片首尾残留下一场景画面。
  - `_build_watermark_filter(watermark_params) -> str | None`：动态构造 drawtext 或 ass 水印滤镜字符串。
  - `process_video(video_path: Path, output_root: Path, threshold=0.2, export_video=True, export_frame=True, frame_offset=0, watermark_params=None, person_id: str = "", rename_lines: list = None)`
    - **处理流程**：分析场景时间戳 -> 输出 `scene_report.txt` -> 无损/硬件编码截取子视频片段 -> 根据偏移量导出代表性静帧 PNG。
  - `run(input_path: Path, output_dir: Path, **kwargs)`：目录级批量场景分割入口。

---

### 4. [whisper_transcription.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/whisper_transcription.py) (语音识别与文案对齐)
- **常量定义**：
  - `GLADIA_UPLOAD_URL`, `GLADIA_TRANSCRIPTION_URL`：Gladia v2 接口端点。
  - `LANGUAGE_OPTIONS` / `TRANSLATE_TARGET_LANGUAGES`：支持语言字典。
- **函数定义**：
  - `extract_audio_with_ffmpeg(media_path: str, output_wav: str, sample_rate: int = 16000, progress_callback=None) -> str`
    - **功能**：提取 16kHz、16-bit PCM、单声道标准 WAV。
  - `split_wav_into_chunks(wav_path: str, max_bytes: int, tmp_dir: str) -> list`：超长音频切块处理（防单次上传超限）。
  - `_gladia_upload_audio(wav_path: str, api_key: str) -> str`：上传音频至 Gladia 存储。
  - `_gladia_submit_transcription(audio_url: str, api_key: str, language: str) -> str`：提交 ASR 任务并获取轮询 `result_url`。
  - `_gladia_poll_result(result_url: str, api_key: str, progress_callback, timeout) -> dict`：异步轮询直到状态为 `done`。
  - `_extract_words_from_gladia(result_data: dict, time_offset: float) -> list[dict]`：从响应中多层降级解析词级时间戳 (`utterances[].words[]` -> 字符级线性插值)。
  - `align_transcript_with_script(whisper_words: list, user_script: str) -> list[dict]`
    - **核心算法**：利用 `difflib.SequenceMatcher` 对比 ASR 识别词与用户输入的精准参考文本，纠正 ASR 错别字，并对缺失词进行时间戳线性插值。
  - `build_segments_with_builder(aligned_words: list, config: dict) -> list[dict]`：调用 `SubtitleSegmentBuilder` 结合标点、气口停顿与行长限制重新分段。
  - `export_srt(segments: list, output_path: str) -> str`：导出标准 SRT 字幕文件。
  - `export_vtt(segments: list, output_path: str) -> str`：导出 WebVTT 字幕文件。
  - `export_ass(segments: list, output_path: str) -> str`：导出基础样式 ASS 字幕。
  - `export_fcpxml(segments: list, output_path: str, fps: float) -> str`：导出 Final Cut Pro XML (v1.11)。
  - `segments_to_srt_text(segments: list) -> str`：转换分段为 SRT 文本供 UI 预览。
- **Worker 类 `WhisperWorker(QObject)`**：
  - `run()`：后台运行提取音频 -> Gladia API 转录 -> 文本对齐 -> 字幕构建的完整流水线。

---

### 5. [elevenlabs.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/elevenlabs.py) (ElevenLabs TTS & 字幕处理)
- **常量定义**：
  - `LANGUAGE_CODES`：支持的 30+ 种语言定义。
  - `EMOTION_OPTIONS`：20+ 种情绪定义（含中文名、说明、Emoji 图标）。
  - `EMOTION_DISPLAY_MAP` / `DISPLAY_TO_EMOTION_MAP`：情绪名称与显示标签的双向映射字典。
- **Worker 线程类**：
  1. **`QuotaWorker(QThread)`**：
     - 请求 `GET /v1/user` 获取当前账户的字符用量与上限。
  2. **`TTSWorker(QThread)`**：
     - 请求 `POST /v1/text-to-speech/{voice_id}/with-timestamps` 生成配音，解析返回的 `alignment` 字符时间戳，级联触发 `SubtitleSegmentBuilder` 生成标准字幕、逐词字幕、Groq 智能翻译及 FCPXML 生成。
  3. **`SFXWorker(QThread)`**：
     - 请求 `POST /v1/sound-generation` 生成音效 MP3 文件。
  4. **`ModelListWorker(QThread)`**：
     - 请求 `GET /v1/models` 动态加载可用 TTS 模型及其特性支持参数。
  5. **`VoiceListWorker(QThread)`**：
     - 请求 `GET /v1/voices` 获取个人账户已添加的声音列表。
  6. **`LibrarySearchWorker(QThread)` & `LibraryAddWorker(QThread)`**：
     - 搜索 ElevenLabs 官方共享声音库并添加到个人音色列表。

---

### 6. [subtitle_builder.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/subtitle_builder.py) & [cjk_tokenizer.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/cjk_tokenizer.py) & [subtitle_writer.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/subtitle_writer.py) (字幕算法套件)

#### `SubtitleSegmentBuilder`
- **算法职责**：解决多语言（印尼语长词、印地语/中文碎标点）字幕智能断句换行问题。
- **方法**：
  - `build_segments(chars, char_starts, char_ends, word_level, words_per_line, ignore_line_length) -> list[dict]`
  - `_build_segments_standard(...)`：根据句末标点、气口停顿（`gap >= pause_threshold`）、字符数上限（`max_chars_per_line`）进行三级决策分段，并执行短句合并。
  - `_build_segments_word_level(...)`：逐词或固定词数换行模式。
  - `_post_process_segments(segments) -> list[dict]`：后处理修复未闭合括号、句首孤立标点修正、超长段落 1.8 倍强制兜底切分。

#### `CJKTokenizer`
- **方法**：
  - `is_cjk(char: str) -> bool`：判断是否属于汉字 Unicode 编码范围。
  - `tokenize_by_cjk(chars, char_starts, char_ends) -> list[dict]`：将字符与时间戳混合序列正确聚合为单词与独立标点。
  - `smart_join(word_objects) -> str`：智能拼接（CJK 字间无空格，西文单词间自动补全单空格，修复括号/冒号间距）。
  - `group_words(word_objects, words_per_line, sentence_enders, pause_threshold) -> list`：按词数与气口分组。

#### `SubtitleWriter`
- **方法**：
  - `write_srt(filename: str, segments: list)`：将字典分段安全写入标准 `.srt` 文本文件。
  - `_format_time(seconds: float) -> str`：秒转 `HH:MM:SS,mmm`。

---

### 7. [SrtsToFcpxml.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/SrtsToFcpxml.py) (FCPXML 样式渲染引擎)
- **职责**：将 SRT 字幕转换为带有高级富文本样式（字体、字号、加粗、描边、阴影、背景框、关键词高亮）的 Apple Final Cut Pro XML。
- **函数定义**：
  - `split_text_by_keywords(text: str, keywords: list[str]) -> list[tuple[str, bool]]`：根据 Groq 分析出的关键词拆分句子片段并标记是否高亮。
  - `get_Fraction_time(time_ms, fps=30) -> str`：将毫秒时间戳转换为 FCP 要求的精确时间分数字符串（如 `150/30s`）。
  - `get_style_attributes(style_dict, prefix, subtitle_setting) -> dict`：解析并格式化颜色与文字排版样式。
  - `SrtsToFcpxml(source_srt, trans_srts, save_path, seamless_fcpxml, xml_style_settings, video_settings)`：构建 XML DOM 树并序列化为 `.fcpxml` 文件。

---

### 8. [groq_analysis.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/groq_analysis.py) & [translation_manager.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/translation_manager.py) & [translation_worker.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/translation_worker.py) (LLM 语义分析与翻译)
- **[groq_analysis.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/groq_analysis.py)**：
  - `extract_keywords(text: str, api_key: str, model: str) -> list[str]`：调用 Groq API（JSON Mode）自动提取文案中的核心关键词用于字幕高亮。
  - `generate_emotion_for_sentence(text: str, api_key: str, model: str) -> str`：调用 Groq 智能识别文案语境并在句子关键位置嵌入 `[Happy]`, `[Sad]` 等 ElevenLabs 情绪标签。
  - `EmotionAnalysisWorker(QThread)`：执行情绪分析的异步 Worker。
- **[translation_manager.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/translation_manager.py)**：
  - 类 `TranslationManager`：支持分批打包（`batch_size=20`）、带编号前缀保护对齐、速率限制（429）指数退避重试的批量翻译管理器。
- **[translation_worker.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/translation_worker.py)**：
  - 类 `TranslationWorker(QObject)`：后台将短字幕段落拼装为完整句子，调用 `TranslationManager` 翻译后映射回字幕时间段。

---

### 9. [videodownloader.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/videodownloader.py) & [ytdlp_updater.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/ytdlp_updater.py) & [ytdlp_update_worker.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/core/ytdlp_update_worker.py) (下载与版本管理)
- **`videodownloader.py`**：
  - `YtDlpLogger`：将 yt-dlp 日志重定向到标准 logging。
  - `YtDlpInfoWorker(QThread)`：解析单个 URL 或播放列表元数据（标题、时长、子列表）。
  - `YtDlpDownloadWorker(QThread)`：使用 `ThreadPoolExecutor` 支持 1~8 线程并发下载、速度与 ETA 计算、自动提取音频/嵌入字幕及格式合并。
- **`ytdlp_updater.py`**：
  - `VersionComparator`：版本号比较工具（支持 YYYY.MM.DD 格式）。
  - `YtDlpVersionManager`：管理本地 `yt_dlp` 目录版本检测与 GitHub/PyPI 远端版本比对。
  - `YtDlpUpdater`：负责下载最新源码 zip、解压替换、自动备份至 `.yt_dlp_backups/` 及一键版本回滚。
- **`ytdlp_update_worker.py`**：
  - `YtDlpCheckUpdateWorker`, `YtDlpUpdateWorker`, `YtDlpRollbackWorker`：更新各阶段的 QThread 封装。

---

## 4.3 界面与交互层 (`pyMediaTools/ui/`)

### 1. [dashboard_shell.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/dashboard_shell.py) (主窗口骨架)
- **类 `SidebarButton(QPushButton)`**：侧边栏导航按钮，支持 `active` 自定义 QSS 属性联动。
- **类 `WindowControlButton(QPushButton)`**：macOS 风格红黄绿交通灯控制按钮。
- **类 `UpdateDialog(QDialog)` & `UpdateCheckWorker(QThread)`**：GitHub Release 在线更新提示对话框与异步检查线程。
- **类 `DashboardWindow(QMainWindow)`**：
  - 采用无边框设计 (`FramelessWindowHint`) 与透明背景；
  - 内部左侧为侧边栏导航，右侧为 `QStackedWidget` 承载各功能 Tab；
  - `switch_module(index: int)`：页面平滑切换；
  - `init_stylesheet_listener()`：监听系统主题变化并动态应用样式。

### 2. [media_tools_ui.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/media_tools_ui.py) (工作台 UI)
- **类 `DropLineEdit(QLineEdit)`**：支持文件拖拽填入路径的单行文本框。
- **类 `ProgressMonitor(QObject)`**：多线程进度监控调度器（发射单文件进度 `file_progress` 与总进度 `overall_progress`）。
- **类 `ConversionWorker(QObject)`**：负责在独立 QThread 中调用 `MediaConverter` 转码。
- **类 `LogoConfigWidget(QFrame)`**：单个 Logo 水印卡片，支持点击勾选启用与背景模糊开关。
- **类 `MediaConverterWidget(QWidget)`**：
  - 工作台主页面：输入/输出目录选择、转码模式下拉框联动、预设 Logo 平台多选卡片区（Dreamina、Gemini、Vidu、Veo 等）、双进度条展示与控制。

### 3. [elevenlabs_ui.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/elevenlabs_ui.py) & [elevenlabs_widgets.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/elevenlabs_widgets.py) & [elevenlabs_dialogs.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/elevenlabs_dialogs.py) (配音 UI)
- **[elevenlabs_widgets.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/elevenlabs_widgets.py)**：
  - `EmotionTagButton`：可直接拖拽至文案框的情绪标签按钮。
  - `EmotionSyntaxHighlighter`：文案框中 `[Happy]` 等情绪标签的语法高亮渲染器。
  - `EmotionHighlightTextEdit`：支持情绪标签拖放定位与高亮的文本编辑器。
  - `EmotionTagManager`：分组管理（情绪、呼吸停顿语气）标签面板。
  - `SubtitlePreviewLabel`：绘制带描边、阴影、背景框效果的实时字幕预览控件。
- **[elevenlabs_dialogs.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/elevenlabs_dialogs.py)**：
  - `VoiceSettingsDialog`：声音稳定性、相似度提升、风格强度、语速滑块调节。
  - `SubtitleSettingsDialog`：源语言/翻译/高亮三种状态下的字体、颜色、描边、阴影、背景高级样式编辑器。
  - `VoiceLibraryDialog`：官方声音共享库浏览、搜索与试听添加窗口。
- **[elevenlabs_ui.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/elevenlabs_ui.py) (`ElevenLabsWidget`)**：
  - 配音界面总成：API Key 与配额查询、模型选择（v2/v3）、音色下拉与试听播放器（`QMediaPlayer`）、文案输入与 AI 一键情绪润色、逐词/翻译/XML 导出选项卡控制。

### 4. [whisper_ui.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/whisper_ui.py) (语音识别 UI)
- **类 `DropZoneWidget(QFrame)`**：音视频文件大区域拖拽上传卡片。
- **类 `WhisperWidget(QWidget)`**：
  - 左侧：拖拽区、语言选择、参考文案（用于精确对齐纠错）输入框、开始识别按钮。
  - 右侧：分步流水线状态展示、识别结果实时表格编辑、一键导出（SRT / VTT / ASS / FCPXML）、LLM 多语言翻译面板。

### 5. [videocut_ui.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/videocut_ui.py) (场景分割 UI)
- **类 `SceneCutWorker(QObject)`**：调用 `SceneCutter` 的异步 Worker。
- **类 `WatermarkSettingsDialog(QDialog)`**：切片水印字体、字号、颜色、坐标高级设置弹窗。
- **类 `VideoCutWidget(QWidget)`**：
  - 阈值滑块调节（敏感度 0~1）、帧偏移设置、静帧/视频切片导出开关、批量文件处理进度面板。

### 6. [video_downloader_ui.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/video_downloader_ui.py) (视频下载 UI)
- **类 `VideoDownloadWidget(QWidget)`**：
  - URL 输入与一键解析解析出多清晰度及播放列表表格；
  - 表格行右键菜单、全选/反选、并发线程数调整、画质格式选择、在线更新 yt-dlp 对话框。

### 7. [ass_editor_ui.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/ass_editor_ui.py) (ASS 样式编辑 UI)
- **类 `ColorPicker(QPushButton)`**：ASS 颜色格式（`&HAABBGGRR&`）解析与拾取器。
- **类 `PreviewWidget(QGraphicsView)`**：基于 `QGraphicsScene` 与 `QPainterPathStroker` 精确模拟 ASS 字幕渲染（双层描边、不透明背景盒、旋转与投影）。
- **类 `ASSEditorWidget(QWidget)`**：
  - 加载/保存 `.ass` 样式，实时调整 Font、Margins、Alignment、Border、Shadow 并即时画布预览。

### 8. [settings_dialog.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/settings_dialog.py) (全局设置)
- **类 `GlobalSettingsDialog(QDialog)`**：
  - 统一配置 ElevenLabs API Key、Gladia API Key、Groq API Key；
  - 配置创作者用户名（自动水印）与字幕分行字符数/停顿气口偏好。

### 9. [styles.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/styles.py) & [qss_resources.py](file:///Users/tim/Documents/shell/pyMediaConvert/pyMediaTools/ui/qss_resources.py) (设计系统)
- **`styles.py`**：
  - `generate_common_qss(...)`：根据系统深/浅色模式动态计算强调色 (`QPalette.Highlight`)、透明蒙版色 (`rgba(255,255,255,0.05)`) 和各平台推荐系统字体（macOS: AppleSystemUIFont, Windows: Segoe UI）。
  - `apply_common_style(widget)`：为主窗口及所有子控件注入现代圆角无缝 QSS。

---