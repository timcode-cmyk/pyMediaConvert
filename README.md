# pyMediaTools - 智能媒体处理与创作工具箱

**pyMediaTools** 是一个基于 PySide6 构建的跨平台桌面应用，集成了强大的媒体批处理能力与先进的 AI 音视频创作工具。它利用 FFmpeg 进行媒体处理，并集成 ElevenLabs 和 Groq API 以实现高质量的语音合成与智能字幕生成。

## ✨ 核心功能

### 1. 🛠️ 媒体批处理工厂 (MediaConvert)
高效处理大量视频与音频文件，支持多种转换模式：
*   **格式转换**：H.264 (MP4), DNxHR (MOV), ProRes 等常用格式。
*   **音频提取**：批量提取为 MP3 或 WAV。
*   **水印与处理**：支持添加图片/文字水印、模糊背景、裁剪等。
*   **多线程处理**：支持并发转换，充分利用系统资源。

### 2. 🗣️ 智能语音合成 (ElevenLabs TTS)
集成 ElevenLabs 先进的语音合成模型：
*   **文本转语音**：支持多种声音模型，生成自然流畅的语音。
*   **多语言支持**：支持中英文等多语言混合生成。
*   **音效生成 (SFX)**：通过文本描述生成逼真的环境音效。

### 3. 📝 智能字幕与翻译
自动生成专业级的字幕文件：
*   **SRT 生成**：自动生成与语音完美对齐的 `.srt` 字幕。
*   **逐词字幕**：支持生成逐词 (Word-level) 字幕，适合快节奏短视频。
*   **智能翻译**：利用 Groq API (支持 Llama3/Mixtral 等模型) 自动将字幕翻译为中文。

### 4. 🎨 视频剪辑工程导出 (XML)
无缝对接专业剪辑软件：
*   **FCPXML 导出**：一键导出包含字幕的 `.fcpxml` 文件，支持 DaVinci Resolve 和 Final Cut Pro。
*   **智能高亮**：利用 LLM 分析文本情感与重点，自动为关键单词应用高亮样式。
*   **样式自定义**：
    *   **原文字幕**：自定义字体、颜色、描边、阴影、背景。
    *   **翻译字幕**：独立样式设置。
    *   **高亮样式**：独立设置高亮单词的颜色与效果 (例如高亮为黄色粗体)。

### 5. 下载管理（aria2c）

### 6. 视频下载（yt-dlp）

---

## 🚀 快速开始

### 系统要求
*   **操作系统**：Windows 10/11 或 macOS 12+
*   **Python**：3.10 或更高版本
*   **依赖工具**：[FFmpeg](https://ffmpeg.org/download.html) (需包含 `ffmpeg` 和 `ffprobe`)
*   **依赖工具**：[aria2c](https://aria2.github.io/) (需包含 `aria2c`)
*   

### 安装步骤

1.  **克隆项目**
    ```bash
    git clone https://github.com/your-repo/pyMediaTools.git
    cd pyMediaTools
    ```

2.  **安装依赖**
    推荐使用虚拟环境：
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    
    pip install -r requirements.txt
    ```

3.  **配置 FFmpeg**
    将 `ffmpeg` 和 `ffprobe` 可执行文件放入项目根目录下的 `bin` 文件夹中（如果没有请新建）。
    *   Windows: `bin\ffmpeg.exe`, `bin\ffprobe.exe`
    *   macOS: `bin/ffmpeg`, `bin/ffprobe`

4.  **运行程序**
    ```bash
    python MediaTools.py
    ```

---

## ⚙️ 配置说明

### API 设置
在 GUI 界面或 `config.toml` 中配置您的 API Key：
*   **ElevenLabs**：用于语音合成。
*   **Groq**：用于智能翻译和关键词提取。

### 样式自定义
在 "XML 样式设置" 标签页中，您可以可视化地调整字幕外观。所有设置会实时预览并保存到本地配置。

---

## 📦 打包指南

本项目支持使用 Nuitka 和 Pyinstaller 打包为独立可执行文件。
### Pyinstaller 打包
```bash
pyinstaller MediaTools.spec
```
### macOS 打包
```bash
nuitka --standalone \
       --macos-app-icon=Icon.icns \
       --macos-create-app-bundle \
       --output-dir=dist-nuitka \
       --plugin-enable=pyside6 \
       --nofollow-import-to=yt_dlp \
       --no-deployment-flag=excluded-module-usage \
       --include-qt-plugins=multimedia,platforms,styles,imageformats \
       --include-package=pyMediaTools \
       --include-module=optparse \
       --include-module=asyncio \
       --include-data-dir=bin=bin \
       --include-data-dir=yt_dlp=yt_dlp \
       --include-data-files=config.toml=config.toml \
       --include-data-files=MediaTools.ico=MediaTools.ico \
       --include-data-dir=assets=assets \
       MediaTools.py
```

### Windows 打包
```bash
nuitka --standalone --windows-console-mode=disable --output-dir=dist-nuitka --windows-icon-from-ico=MediaTools.ico --nofollow-import-to=yt_dlp --no-deployment-flag=excluded-module-usage --include-module=optparse --include-module=asyncio --include-package=pyMediaTools --plugin-enable=pyside6 --include-qt-plugins=multimedia,platforms,styles,imageformats --include-data-dir=yt_dlp=yt_dlp --include-data-files=bin\aria2c.exe=bin\aria2c.exe --include-data-files=MediaTools.ico=MediaTools.ico --include-data-files=bin\ffmpeg.exe=bin\ffmpeg.exe --include-data-files=bin\ffprobe.exe=bin\ffprobe.exe --include-data-files=config.toml=config.toml --include-data-dir=assets=assets MediaTools.py

```

---

## 📄 许可证

本项目遵循开源协议。FFmpeg 组件遵循 LGPL/GPL 协议。
使用 ElevenLabs 和 Groq API 时请遵守其相应的服务条款。

---

## 如何发布新版本
本项目使用 GitHub Actions 自动构建和发布。每次发布新版本只需要创建一个 Git Tag 并推送即可。

### 发布步骤

#### 1. 确保代码已提交并推送
在发布之前，确保你的所有代码改动已经提交并推送到 GitHub：
```bash
# 查看当前状态
git status

# 添加所有改动
git add .

# 提交改动（把"你的改动说明"替换成实际的描述）
git commit -m "你的改动说明"

# 推送到 GitHub
git push origin main
```

#### 2. 创建版本 Tag
Git Tag 是一个版本标记，用于标识发布的版本号。版本号格式为 `v主版本.次版本.修订版本`，例如 `v1.0.0`、`v1.1.0`、`v2.0.0`。
```bash
# 创建一个新的版本 tag（将 v1.0.1 替换为你想要的版本号）
git tag -a v1.0.1 -m "Release version 1.0.1"
```

#### 3. 推送 Tag 触发自动构建
```bash
# 推送 tag 到 GitHub（这会自动触发 CI 构建）
git push origin v1.0.1
```
推送后，GitHub Actions 会自动执行以下操作：
1. 构建项目
2. 生成安全签名（Attestation）
3. 创建 Release 并上传构建产物

#### 4. 查看构建结果
- 构建进度：访问项目的 **Actions** 页面查看
- 发布结果：访问项目的 **Releases** 页面查看已发布的文件

### 版本号说明

| 版本号格式 | 什么时候用 | 示例 |
|-----------|-----------|------|
| `vX.0.0` | 重大更新、不兼容改动 | `v2.0.0` |
| `vX.Y.0` | 新增功能 | `v1.1.0` |
| `vX.Y.Z` | 修复 bug | `v1.0.1` |

### 如果构建失败怎么办
1. 访问项目的 **Actions** 页面查看错误日志
2. 修复代码问题
3. 删除失败的 tag 并重新创建：
```bash
# 删除本地 tag
git tag -d v1.0.1
# 删除远程 tag
git push origin :refs/tags/v1.0.1
# 修复问题后，重新创建并推送
git tag -a v1.0.1 -m "Release version 1.0.1"
git push origin v1.0.1
```
