# pyMediaTools 项目详细分析

## 📋 项目概况

**项目名称**: pyMediaTools - 智能媒体处理与创作工具箱  
**框架**: PySide6（Qt6 Python绑定）  
**Python版本**: 3.10+  
**操作系统**: macOS 12+、Windows 10/11

### 核心功能模块
1. **MediaConvert** - 媒体批处理工厂
   - 格式转换（H.264, DNxHR, ProRes等）
   - 音频提取
   - 水印和图像处理
   - 多线程并发处理

2. **ElevenLabs TTS** - 智能语音合成
   - 文本转语音
   - 多语言支持
   - 音效生成（SFX）

3. **字幕与翻译** - 智能字幕系统
   - SRT自动生成
   - 逐词字幕
   - 智能翻译（Groq API）
   - FCPXML导出（支持DaVinci Resolve和Final Cut Pro）

4. **下载管理** - aria2c集成

5. **视频下载** - yt-dlp集成

---

## 📁 项目结构详解

```
pyMediaConvert/
├── pyMediaTools/               # 核心模块
│   ├── ui/                    # UI层
│   │   ├── video_downloader_ui.py    # 视频下载UI（主要关注）
│   │   └── ...                      # 其他UI模块
│   ├── core/                  # 业务逻辑层
│   │   ├── videodownloader.py        # 视频下载核心逻辑（主要关注）
│   │   ├── mediaconvert.py
│   │   ├── elevenlabs.py
│   │   ├── groq_analysis.py
│   │   └── ...
│   ├── bridges/               # 接口/桥接
│   ├── qml/                   # QML资源
│   └── utils.py               # 工具函数
├── yt_dlp/                    # yt-dlp源代码目录（本地）
│   ├── __init__.py
│   ├── version.py             # 版本文件：2026.02.04
│   ├── YoutubeDL.py
│   ├── update.py              # 更新逻辑（已有）
│   └── ...
├── bin/                       # 二进制工具
│   ├── ffmpeg
│   ├── ffprobe
│   └── aria2c
├── assets/                    # 资源文件
├── config.toml               # 应用配置
└── requirements.txt          # 依赖列表
```

---

## 🎯 Video Downloader 核心分析

### UI层 (`video_downloader_ui.py`)

**主要类**: `VideoDownloadWidget`

**功能流程**:
```
1. URL输入 → 解析链接 → 展示视频列表
   └── YtDlpInfoWorker(QThread) 异步解析

2. 选择下载参数:
   - 格式选择 (mp4/mkv/webm/mp3/m4a/wav)
   - 画质选择 (Best/4K/2K/1080p/720p/480p)
   - 字幕选择 (多语言支持)
   - 并发线程数 (1-8)
   - 保存路径

3. 开始下载 → 并发下载多个视频
   └── YtDlpDownloadWorker(QThread) 并发处理
       └── ThreadPoolExecutor 实现多线程
```

**关键信号**:
- `progress`: 下载进度更新
- `finished`: 下载完成
- `error`: 错误处理

### 核心层 (`videodownloader.py`)

**主要类**:

1. **YtDlpInfoWorker** - 信息解析
   - 异步解析视频/播放列表
   - 返回视频元数据

2. **YtDlpDownloadWorker** - 下载管理
   - 配置化下载选项
   - 进度钩子（progress hooks）
   - 支持并发下载（ThreadPoolExecutor）
   - FFmpeg集成
   - 字幕嵌入

**下载配置选项**:
```python
{
    'audio_only': bool,           # 仅音频
    'ext': str,                   # 输出格式
    'quality': str,               # 质量等级
    'subtitles': bool,            # 下载字幕
    'sub_lang': str,              # 字幕语言
    'concurrency': int            # 并发数
}
```

---

## 🔧 yt-dlp 版本管理现状

### 当前版本信息
- **版本**: 2026.02.04
- **Git Head**: c677d866d41eb4075b0a5e0c944a6543fc13f15d
- **渠道**: stable
- **源**: yt-dlp/yt-dlp
- **位置**: 项目本地 `yt_dlp/` 目录

### 版本文件位置
- `yt_dlp/version.py` - 版本定义
- `yt_dlp/update.py` - 更新逻辑（yt-dlp自有）

---

## ✨ 实现计划：yt-dlp 版本检测与更新

### 需要创建的模块

#### 1. **YtDlpVersionManager** (`pyMediaTools/core/ytdlp_updater.py`)
负责版本检测和更新管理

**功能**:
- ✅ 检测本地yt_dlp版本
- ✅ 获取远程最新版本（GitHub/PyPI）
- ✅ 对比版本
- ✅ 下载并安装更新
- ✅ 备份原文件
- ✅ 回滚功能

**接口**:
```python
class YtDlpVersionManager:
    def get_local_version() -> str
    def get_remote_version() -> str
    def check_update_available() -> bool
    def update_from_github() -> bool
    def update_from_pypi() -> bool
    def rollback() -> bool
    def is_updating() -> bool
```

#### 2. **UI增强** (`video_downloader_ui.py`)
在video downloader界面添加版本管理功能

**添加的UI组件**:
- 版本显示标签
- "检查更新" 按钮
- "更新yt-dlp" 按钮
- 更新进度对话框
- 更新日志（变更说明）

### 实现步骤

**Step 1**: 创建YtDlpVersionManager核心模块
**Step 2**: 创建异步更新Worker线程
**Step 3**: 增强Video Downloader UI
**Step 4**: 添加配置持久化
**Step 5**: 测试和文档

---

## 📊 系统依赖关系图

```
VideoDownloadWidget (UI)
├── YtDlpInfoWorker (QThread)
│   └── yt_dlp module
├── YtDlpDownloadWorker (QThread)
│   ├── yt_dlp module
│   ├── FFmpeg
│   └── ThreadPoolExecutor
└── YtDlpVersionManagerWorker (QThread) [新增]
    └── YtDlpVersionManager
        ├── GitHub API
        ├── PyPI API
        └── Local yt_dlp (version.py)
```

---

## 🔐 安全考虑

1. **备份策略**: 更新前自动备份yt_dlp目录
2. **验证机制**: 验证下载文件的完整性（checksum）
3. **回滚机制**: 更新失败时自动回滚
4. **权限检查**: 验证写入权限

---

## 📈 性能优化

1. 版本检查使用缓存（可配置TTL）
2. 异步后台更新，不阻塞主UI线程
3. 增量下载（如果支持）
4. 并行检测多个源

---

## 🚀 部署建议

1. 首次运行时自动检查更新
2. 添加定时检查任务（可选）
3. 用户可手动触发更新
4. 提供更新日志和变更说明
5. 使用国内镜像源（可选）

