---
name: coding-standards
description: 编码与架构规范控制 — 确保AI在维护与扩展项目时遵守代码规范、架构分离及UI设计一致性
---

# `pyMediaConvert` 编码与UI规范指南

当你（AI助手）在处理 `pyMediaConvert` 相关的编码任务、尤其是增加新特性、完善现有模块时，**必须**严格遵循本规范指南。这能够保证项目长期运作的稳定性和高质量。

## 1. 架构与设计模式规则
- **SRP (单一职责原则)**: 绝不能在一个类里写尽所有逻辑。每个模块、类或函数都必须只承担一类责任。如果某个源文件超过 1000 行，你应该考虑建议用户抽取逻辑，拒绝堆砌。
- **业务逻辑与 UI 解耦**: 
  - 所有核心数据处理、外部API通信与耗时密集任务应统统放进 `pyMediaTools/core/`，或其他类似的核心包下面。
  - 用户界面 (`pyMediaTools/ui/`) 只负责：绘制界面、读写用户操作参数，并将参数**透传**到 core 处理模块。
- **线程控制与防卡死**: Qt 应用程序的主 UI 线程**绝对禁止**运行超过 50ms 的堵塞任务或耗时网络请求（如音频处理、API 下载）。所有这些应包装到 `QThread` (或使用 `QRunnable/QThreadPool`)，并通过 `Signal / Slot` 回传处理进度和状态，防止应用无响应 (ANR)。

## 2. UI/UX 视觉一致性要求
当你需要编写或扩展任何 `QWidget` 时，必须服从以下 UI 规则以确保深/浅色模式表现完美且高级：
- **永远使用动态色与公共样式**: 除特别指明，不可直接在 Widget 初始化里写死类似 `#FFFFFF` 或 `black` 的硬编码颜色！你应该：
  - 调用 `pyMediaTools.ui.styles` 模块中的 `apply_common_style(self)`。
  - 依赖 `QPalette` 的内置属性（比如 `self.palette().color(QPalette.WindowText)`）来获取颜色。
  - **判断深浅模式**: 通过如下安全语句判断并应用细微色彩：
    ```python
    is_dark = self.palette().color(QPalette.Window).lightness() < 128
    ```
- **使用色彩渲染信息 (Color Overlays)**: 当用颜色区分 UI 的 List、Group 或 Status 时，应使用 `rgba()` 实现极低不透明度的背景色 (如 `0.05` 或 `0.1` opacity) 叠加。这样既不会破坏现有深/浅色的基础风格，又提供了高级的彩色标记反馈。
- **圆角与边距**: Modern UI 需要舒适的呼吸感。确保布局里 `setContentsMargins(15, 15, 15, 15)` 及 `setSpacing(10)` 的合理留白。控件统一 `border-radius: 6px`（或 8px, 10px）。
- **鼠标指针提示**: 可点击区域应设置 `self.setCursor(Qt.PointingHandCursor)` 增强交互提示。

## 3. 项目结构概览和拓展思路
对 `pyMediaConvert` 的修改通常涉及三条主线：
1. **新增转码或媒体处理模式 (Worker)**：
   - 在 `core.mediaconvert` 或相关的 `converter` 源文件中添加实现，并实现基于文件的调度。
   - 不要忘记在 `config.toml` 中将新增功能注册为独立的 mode（例如 `[modes.new_feature]`）。
2. **新增工具集 Tab/UI**：
   - 永远将相关代码写在 `pyMediaTools/ui/[name]_ui.py` 下，并最终在 `dashboard_shell.py` 的选项卡/Stack里进行注册和挂载。
3. **配置文件的生命周期管控**：
   - 用户的设定需要从 `config.toml` 及 `pyMediaTools/utils/__init__.py` 等安全加载。

**如果在后续编程中你发觉自己编写的代码偏离了以上的界面、架构规范，请立刻修正。**
