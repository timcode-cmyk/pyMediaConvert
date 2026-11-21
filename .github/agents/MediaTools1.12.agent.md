---
description: 'pyMediaTools 桌面媒体工具包开发与架构助手规范'
tools: []
---
本仓库为基于 Python + PySide6 的专业桌面媒体处理工具集（`pyMediaTools`），覆盖视频转码与水印、ElevenLabs 语音合成、Gladia 语音识别、场景分割、视频下载与 ASS 字幕编辑等模块。

## 开发规范
- **架构分层**：核心算法、FFmpeg 调用与外部 API 统一位于 `pyMediaTools/core/`，严禁包含 UI 弹窗或控件；界面逻辑位于 `pyMediaTools/ui/`，单文件尽量保持在 1000 行以内。
- **配置管理**：`config.toml` 仅作为只读的出厂默认配置，个性化覆盖持久化于系统标准用户配置目录的 `user_config.json`，支持通过环境变量以最高优先级覆盖。
- **UI 一致性**：统一通过 `pyMediaTools.ui.styles.apply_common_style(self)` 与 `QPalette` 适配深浅色模式及跨平台字体，禁止硬编码颜色和平台专属字体。
- **线程安全与跨平台**：耗时任务必须在独立 Worker 线程执行，主界面退出时需安全回收后台线程；外部进程调用必须通过 `get_subprocess_creation_flags()` 隐藏 Windows 控制台黑框。
