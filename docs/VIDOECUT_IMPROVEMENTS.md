# Videocut 改进说明

## 改进概要

针对 Windows 平台下 FFmpeg 执行时弹出 cmd 窗口影响用户体验的问题，进行了以下改进：

## 主要改进

### 1. **隐藏 Windows CMD 窗口**
- 参考 MediaConvert 模块的处理方式
- 在所有 `subprocess.run()` 调用中添加 `subprocess.CREATE_NO_WINDOW` 标志
- 仅在 Windows 平台上生效，不影响其他平台
- **受影响的操作**：
  - FFmpeg 视频分割
  - FFmpeg 截图生成
  - FFprobe 时长获取
  - FFmpeg 帧率检测
  - FFmpeg 场景检测

```python
# 针对 Windows 隐藏窗口
creationflags = 0
if sys.platform == "win32":
    creationflags = subprocess.CREATE_NO_WINDOW

subprocess.run(cmd, ..., creationflags=creationflags)
```

### 2. **调试日志系统**
- 新增 `debug` 参数用于启用调试模式
- 调试日志保存到独立的文件中（默认在 `output/logs/` 目录）
- 支持自定义日志目录

**日志内容包括**：
- 视频基本信息（时长、帧率、阈值）
- 每个 FFmpeg 命令的完整命令行
- 场景检测结果
- 每个场景的处理状态（视频分割、截图生成）

### 3. **命令行参数扩展**

新增参数：
```bash
--debug, -d              启用调试模式，记录详细操作日志
--log-dir, -l LOG_DIR    指定调试日志保存目录（默认: output/logs）
```

**使用示例**：
```bash
# 启用调试模式，日志保存到默认位置
python vidoecut.py -i video.mp4 -o output --debug

# 指定自定义日志目录
python vidoecut.py -i video.mp4 -o output --debug --log-dir ./debug_logs
```

## 技术细节

### Windows 窗口隐藏机制
- `subprocess.CREATE_NO_WINDOW` 是 Windows 专用的创建标志
- 它会在进程创建时隐藏控制台窗口
- 创建的进程可以正常输出到管道，不影响功能
- 在非 Windows 系统上此标志被忽略（值为 0）

### 日志系统
- 调试日志单独保存，不混入主程序日志
- 每个视频的调试信息保存到独立的日志文件
- 文件名格式：`{视频名}_debug.log`
- 日志包含时间戳，便于追踪执行时间

## 向后兼容性

- 所有改进均为可选功能
- 不启用 `--debug` 时行为完全相同
- 现有的调用方式无需修改
- 代码结构保持一致，易于集成到 UI 模块

## 场景切分精度与偏移说明

- 现在会把检测到的场景时间点根据视频帧率四舍五入到最接近的帧边界，确保分割命令生成的片段不会包含下一场景的残余帧。
- FFmpeg `-ss` 参数已移到输入之后，以便进行精确寻帧，配合 `-avoid_negative_ts 1` 能在复制模式下也保持帧级准确性。
- `frame_offset` 参数仅用于静帧截图；它**不**再影响视频片段的起始时间。
- 这些改变不会影响现有的调用逻辑，老参数仍然有效。

## 代码示例

### Python 脚本调用
```python
from pathlib import Path
from pyMediaTools.core.vidoecut import SceneCutter

# 不启用调试模式
cutter = SceneCutter(debug=False)

# 启用调试模式
log_dir = Path("./debug_logs")
cutter = SceneCutter(debug=True, log_dir=log_dir)

# 处理视频
options = {
    "threshold": 0.2,
    "export_frame": True,
    "frame_offset": 10,
    "watermark_params": None
}
cutter.process_video(video_path, output_dir, **options)
```

### 命令行调用
```bash
# 基本用法（无日志）
python -m pyMediaTools.core.vidoecut -i input.mp4 -o output

# 启用调试（日志保存到 output/logs/）
python -m pyMediaTools.core.vidoecut -i input.mp4 -o output --debug

# 自定义日志位置
python -m pyMediaTools.core.vidoecut -i input.mp4 -o output --debug --log-dir /tmp/logs
```

## 验证步骤

1. **Windows 测试**：运行视频处理，确认不出现 FFmpeg 窗口
2. **调试验证**：使用 `--debug` 参数，检查日志文件是否正确生成
3. **跨平台测试**：在 Linux/macOS 上运行，确保功能正常

## 相关文件修改

- `pyMediaTools/core/vidoecut.py`
  - 添加 `sys` 导入
  - 修改所有 subprocess 调用
  - 新增日志系统
  - 扩展命令行参数
