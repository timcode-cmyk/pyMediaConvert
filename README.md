# pyMediaTools

轻量级的跨平台媒体批处理与 AI 语音生成工具（基于 FFmpeg + ElevenLabs API + PySide6 GUI）。

功能概览：
- **媒体处理**：批量转换视频/音频、添加 Logo 水印、导出图片序列、支持多种编码（H.264、DNxHR、PNG、MP3、WAV 等）。
- **ElevenLabs 工具箱**：集成文本转语音 (TTS) 与音效生成 (SFX)，支持字幕自动生成 (SRT) 与配额查询。

注意：本项目使用 FFmpeg/ffprobe，遵循其 LGPL/GPL 许可（见项目 LICENSE / README）。

## 目录
- 简介
- 系统与依赖
- 快速开始（从源码运行）
- GUI 使用说明
- CLI 使用说明
- 配置文件说明 (config.toml)
- 打包为独立 macOS 应用（使用 Nuitka）
- 常见问题与调试提示
- 贡献与许可

---

## 简介
pyMediaTools 包含两个核心模块：
1. **MediaConvert**：
- 遍历输入目录并识别支持的媒体文件；
- 使用 ffmpeg 执行转码、加 logo、裁剪与滤镜等处理；
- 用 PySide6 提供简单易用的桌面 GUI，带转换进度与停止功能。
2. **ElevenLabs**：
- 调用 ElevenLabs API 生成高质量语音与音效；
- 自动生成对齐的 SRT 字幕文件。

---

## 系统与依赖

- 支持平台：macOS（主要测试平台）
- 必需外部工具：ffmpeg, ffprobe（推荐手动下载放到项目根目录下的 bin/ 目录，或保证系统 PATH 中有可用的 ffmpeg/ffprobe）
- Python: 3.10+ 推荐
- Python 包：
  - pyside6
  - tqdm
  - requests
  - nuitka（仅在打包时需要）
  - 其它依赖见 `pyproject.toml` / `requirements.txt`（如果项目包含）

安装示例（macOS）：
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt || pip install pyside6 tqdm requests
```

准备 ffmpeg/ffprobe（推荐：手动放到 bin/）：
1. 下载静态 build（例如从 ffmpeg.org 或第三方构建站）；
2. 在项目根目录创建 bin/，把 ffmpeg 和 ffprobe 可执行文件放入 bin/；
3. 使其可执行：
```bash
chmod +x bin/ffmpeg bin/ffprobe
```
运行时，程序会优先使用项目 bin/ 中的二进制（在 Windows 中为 `ffmpeg.exe`/`ffprobe.exe`），若不存在则回退到系统 PATH 中的可执行文件。打包 Windows 发行版时请确保将 `ffmpeg.exe` 和 `ffprobe.exe` 包含到 `bin/` 或通过打包器的 `--include-data-files`/`--include-data-dir` 选项捆绑进程序，否则在没有 PATH 中 ffmpeg 的机器上会出现 “ffmpeg 未找到” 的错误。

---

## 快速开始（从源码运行）

1. 激活虚拟环境并安装依赖（见上文）。
2. 确保 bin/ 中有 ffmpeg/ffprobe（或系统 PATH 可用）。
3. 在项目根目录运行 GUI：
```bash
python app.py  # 启动整合后的带选项卡工具箱（媒体转换 + ElevenLabs）
```

---

## GUI 使用说明（简短）

- 输入目录：拖拽或选择包含媒体文件的文件夹（支持扩展名参见 config.py）
- 输出目录：选择转换后文件保存位置
- 模式下拉：选择转换器（例如 hailuo / h264 / mp3）
- 开始/停止：在后台线程执行转换，停止会发送停止请求
- 进度：文件级与总体进度显示

---

## CLI 使用说明

项目包含简易 CLI：cli.py。常见用法：
```bash
# 在项目根目录
python cli.py --mode h264 --dir /path/to/input --out processed_output
```

参数：
- --mode, -m: 必需，选择 config.MODES 中定义的模式名（例如 hailuo, h264, mp3 等）
- --dir, -d: 输入目录（默认当前目录）
- --out, -o: 输出目录（相对于输入目录的子目录或绝对路径）
- --ext, -e: 可选，用来覆盖支持的扩展（逗号分隔，如 ".mp4,.mov"）

示例：
```bash
python cli.py -m hailuo -d ~/Videos -o converted
```

CLI 会按 config.py 中指定的转换器类实例化并执行转换；若 bin/ 中存在 ffmpeg/ffprobe，会优先使用它们。

---

## config 配置说明

配置文件：pyMediaConvert/config.py（在 MODES 字典中定义所有模式）

每个模式结构：
- class: 对应 pyMediaConvert.worker 中的转换器类
- description: GUI 显示的简短说明
- output_ext: 输出文件后缀/后缀模板
- support_exts: 支持的输入扩展名列表（None 则使用转换器默认）
- params: 传给转换器构造的参数字典（例如 LogoConverter 的 x, y, logo_path 等）

添加自定义模式示例（编辑 config.py）：
```python
MODES['my_mode'] = {
    'class': H264Converter,
    'description': '自定义 H264',
    'output_ext': '_myh264.mp4',
    'support_exts': ['.mp4', '.mov'],
    'params': {'some_param': 123}
}
```

---

## 打包为独立应用（使用 Nuitka）
（保持原 README 中的 Nuitka 说明；确保在打包前把 bin/ 中的 ffmpeg/ffprobe 包含进 bundle，或在打包命令中通过 --include-data-dir 指定）

示例打包命令（参考）：
###  macOS 
```bash
nuitka --standalone \
       --macos-app-icon=Icon.icns \
       --macos-create-app-bundle \
       --output-dir=dist-nuitka \
       --plugin-enable=pyside6 \
       --include-qt-plugins=multimedia,platforms,styles,imageformats \
       --include-package=pyMediaConvert \
       --include-data-dir=bin=bin \
       --include-data-dir=assets=assets \
       --nofollow-import-to=pytest,tkinter \
       app.py
```

### Windows
```bash
nuitka --standalone --onefile --windows-disable-console --windows-icon-from-ico=MediaTools.ico --include-package=pyMediaConvert --plugin-enable=pyside6 --include-qt-plugins=multimedia,platforms,styles,imageformats --include-data-files=bin\ffmpeg.exe=bin\ffmpeg.exe  --include-data-files=bin\ffprobe.exe=bin\ffprobe.exe --include-data-dir=assets=assets app.py

```

---

## 常见问题与调试提示

- ffmpeg 未找到：请把 ffmpeg/ffprobe 放到项目根目录的 bin/，或确保系统 PATH 可用。

打包为单文件 App 后进度条不更新的常见原因：
- 资源路径问题：打包器（PyInstaller/Nuitka）在 onefile 模式下会把数据解包到运行时临时目录（sys._MEIPASS），因此代码中需使用该路径查找嵌入的 `bin/`。已在 `pyMediaConvert.utils.get_base_dir()` 中增加对 `sys._MEIPASS` 的支持。
- 可执行权限：嵌入的 `ffmpeg/ffprobe` 可能缺少执行权限，打包时/运行时需确保给二进制文件添加执行位（`chmod +x`）。工具现在会尽力确保可执行位（POSIX）。
- 进度读取方式：原来使用临时文件轮询读取 `-progress <file>` 的做法在某些打包或沙箱环境下不稳定（文件 IO 权限或路径问题）。推荐使用 `-progress pipe:1`（FFmpeg 输出到 stdout 并实时读取），已在代码中优先采用此方式，回退到临时文件作为兼容性备用。

如果你在打包后遇到进度不可用的问题，请检查 `bin/ffmpeg` 是否被包含、是否可执行，并在 App 启动日志中查找启动时的 stderr/错误输出。

---

## 贡献 & 许可
- 欢迎 PR / issue，提供平台信息与复现步骤。
- 遵守 FFmpeg 的许可（LGPL/GPL）要求。

---
