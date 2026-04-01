# pyMediaTools - 智能媒体处理与创作工具箱

[![Version](https://img.shields.io/badge/version-v1.15.0-blue.svg)](https://github.com/your-repo/pyMediaTools/releases)
[![Python](https://img.shields.io/badge/python-3.12-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey.svg)]()
[![License](https://img.shields.io/badge/license-LGPL%2FGPL-orange.svg)](LICENSE)

---

## 项目简介

`pyMediaTools` 是一个基于 Python 和 PySide6 的跨平台媒体处理工具箱，集成视频转换、音频处理、语音识别、TTS 配音、视频下载、场景分割与字幕编辑等功能。它专注于为创作者、短视频内容制作和媒体处理人员提供一个“一站式”桌面应用。

## 主要功能

- **工作台 / 媒体转换**
  - 批量视频/音频转换
  - 多种格式输出（H.264、DNxHR、PNG、MP3、WAV 等）
  - 支持自定义 LOGO/水印、ASS 文本叠加
  - 支持 macOS VideoToolbox 硬件编码

- **视频配音（ElevenLabs）**
  - 集成 ElevenLabs TTS 语音合成
  - 支持多语种发音与语气/情绪标签
  - 支持语音文件输出与字幕导出

- **语音识别**
  - 基于 Groq Whisper 的语音转写
  - 支持词级时间戳与字幕导出
  - 支持多格式字幕输出：SRT、VTT、ASS、FCXPL

- **场景分割**
  - 基于 OpenCV 的场景检测与视频切割
  - 导出场景视频片段与静帧截图
  - 支持选择水印字体和 ASS 字幕模板

- **视频下载**
  - 基于 `yt-dlp` 的视频/音频下载
  - 支持多平台链接解析（YouTube、Bilibili 等）
  - 支持音频提取、字幕下载、质量与格式选择
  - 集成 yt-dlp 版本检测与更新

- **字幕编辑**
  - ASS 字幕编辑器界面
  - 支持载入与保存 ASS 字幕文件
  - 支持预览与字幕样式管理

## 项目结构

```
/MediaTools.py            # 应用入口
/config.toml             # 运行时配置
/requirements.txt        # Python 依赖
/bin/                    # 捆绑 ffmpeg / ffprobe
/assets/                 # 资源文件：字体、ASS、图标、Logo
/pyMediaTools/           # 应用核心代码包
  /ui/                   # PySide6 界面组件
  /core/                 # 业务逻辑与处理模块
  /qml/                  # 备用 QML 资源
  /bridges/              # 外部桥接逻辑
  logging_config.py      # 日志初始化与配置
  utils.py               # 工具函数
/tests/                  # 单元测试
/docs/                   # 项目文档
```

## 核心模块说明

### `MediaTools.py`
- 应用入口，初始化日志、创建 `QApplication`，加载主面板模块。
- 主窗口模块包含：工作台、视频配音、语音识别、场景分割、视频下载、字幕编辑。

### `pyMediaTools/ui/`
- `media_tools_ui.py`: 媒体批量转换界面与转换流程。
- `elevenlabs_ui.py`: ElevenLabs 语音合成界面与情绪标签管理。
- `whisper_ui.py`: Whisper 语音识别与字幕构建界面。
- `videocut_ui.py`: 场景分割、截图与水印设置界面。
- `video_downloader_ui.py`: yt-dlp 下载管理界面。
- `ass_editor_ui.py`: ASS 字幕编辑器。
- `dashboard_shell.py`: 主面板、模块切换与整体布局。

### `pyMediaTools/core/`
- `mediaconvert.py`: 基于 FFmpeg 的视频与音频格式转换、编码器检测与批处理支持。
- `config.py` / `factory.py`: 运行模式配置与扩展转换方案。
- `videodownloader.py`: yt-dlp 下载、解析、任务管理。
- `ytdlp_updater.py`: yt-dlp 版本检测与更新。
- `vidoecut.py`: OpenCV 场景检测、分割、截图与字幕资源查找。
- `whisper_transcription.py`: Groq Whisper 语音转写、时间戳处理与字幕导出。
- `elevenlabs.py`: ElevenLabs TTS、情绪标签、字幕生成与 API 请求。
- `subtitle_writer.py`, `subtitle_builder.py`: 字幕生成与格式转换逻辑。
- `translation_manager.py`, `translation_worker.py`: 文本翻译与字幕语言管理。

## 运行与开发

建议使用 Python 3.12。当前依赖包括但不限于：

- `requests`
- `yt_dlp`
- `PySide6`
- `pysrt`
- `toml`
- `opencv-python`

安装依赖：

```bash
python -m pip install -r requirements.txt
python install_dependencies.py
```

### 运行方式

```bash
python MediaTools.py
```

## 配置说明

- `config.toml`：项目运行时配置文件，支持 ElevenLabs API、默认路径、转换模式等。
- `ELEVENLABS_API_KEY`：如果不在配置文件中设置，可使用环境变量提供 ElevenLabs API Key。

## 打包说明

本项目使用 `nuitka` 打包配置，输出目录为 `dist-nuitka/`。
```bash
python -m pip install nuitka
nuitka MediaTools.py
```

## 版本发布流程

本项目使用 GitHub Actions 自动构建与发布。

### 发布步骤

#### 1. 确保代码已提交并推送
```bash
git status
git add .
git commit -m "你的改动说明"
git push origin main
```

#### 2. 创建版本 Tag
```bash
git tag -a v1.0.1 -m "Release version 1.0.1"
```

#### 3. 推送 Tag 触发自动构建
```bash
git push origin v1.0.1
```

#### 4. 查看构建结果
- 访问项目的 **Actions** 页面查看构建日志
- 访问项目的 **Releases** 页面查看发布结果

### 版本号说明

| 版本号格式 | 什么时候用 | 示例 |
|-----------|-----------|------|
| `vX.0.0` | 重大更新、不兼容改动 | `v2.0.0` |
| `vX.Y.0` | 新增功能 | `v1.1.0` |
| `vX.Y.Z` | 修复 bug | `v1.0.1` |

### 构建失败处理

1. 查看 GitHub Actions 错误日志
2. 修复问题
3. 重新创建并推送 tag：
```bash
git tag -d v1.0.1
git push origin :refs/tags/v1.0.1
git tag -a v1.0.1 -m "Release version 1.0.1"
git push origin v1.0.1
```

## 许可证

本项目遵循 `LICENSE` 中的开源许可条款。
