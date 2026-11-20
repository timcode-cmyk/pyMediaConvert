# PySide6 Architecture & Design Patterns

本文档总结 PySide6 应用程序中最常用的核心架构与设计模式。

---

## 1. 窗口与容器选型原则
- **`QMainWindow`**：用于完整的独立主窗口，自带菜单栏（MenuBar）、状态栏（StatusBar）、工具栏（ToolBar）和侧边栏停靠区（DockWidgets）。
- **`QDialog`**：用于模态或非模态的独立操作流程（如配置、更新提示、关于、文件导出），自带确认/取消生命周期管理 (`accept()`, `reject()`, `exec()`)。
- **`QWidget`**：用于组合小构件（Component），不应滥用为主窗口。
- **`QStackedWidget`**：用于多页单窗口切换（如向导式流程、仪表盘 Tab 页切换），避免在同一个页面里动态隐藏显示数十个控件。

---

## 2. 线程与防卡死模型（Worker + QThread）

**UI 线程原则**：Qt 应用程序的事件循环运行在主 UI 线程，任何超过 50ms 的堵塞（网络请求、音视频转码、大规模文件读写）都必须转移到后台线程。

### 标准 Worker 模式（推荐，优于直接继承 QThread）
```python
from PySide6.QtCore import QObject, QThread, Signal, Slot

class Worker(QObject):
    finished = Signal()
    progress = Signal(int)
    error = Signal(str)

    @Slot()
    def do_work(self):
        try:
            for i in range(100):
                # 密集计算或处理
                self.progress.emit(i)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class Controller(QObject):
    def start_task(self):
        self.thread = QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.do_work)
        self.worker.progress.connect(self.handle_progress)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()
```
