# Qt Designer UI Workflow for PySide6

本文档规范 Qt Designer 可视化设计文件（`.ui`）与 PySide6 Python 代码之间的集成与协同规范。

---

## 1. 核心理念与架构原则
- **职责完全分离（Separation of Concerns）**：
  - `.ui` 文件只负责界面布局与控件初始属性。
  - **绝不**手动修改由工具编译生成的 `ui_*.py` 代码，任何界面调整必须回退到 Qt Designer 中修改并重新编译，避免改动被覆盖。
  - 业务逻辑、信号与槽绑定、动态数据填充统统放在自定义的继承类/控制器（Controller）中。
- **命名规范（Naming Convention）**：
  - 在 Qt Designer 的 Object Inspector 中，必须为有交互的组件赋予语义化、驼峰或蛇形命名（如 `btn_submit`、`line_edit_search` 或 `saveButton`），禁止保留默认的 `pushButton_1`。

---

## 2. 静态编译方案（推荐：`pyside6-uic`）

这是生产环境最推荐的方案，具有类型提示友好、运行期零加载开销等优势。

### 2.1 编译流程
在终端执行：
```bash
pyside6-uic main_window.ui -o ui_main_window.py
```
或者批量编译命令：
```bash
find . -name "*.ui" -exec pyside6-uic {} -o ui_{/.}.py \;
```

### 2.2 多重继承集成模式
```python
import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from ui_main_window import Ui_MainWindow

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)  # 初始化由 Designer 生成的控件和布局
        self.init_signals()

    def init_signals(self):
        self.btn_submit.clicked.connect(self.handle_submit)

    def handle_submit(self):
        input_text = self.line_edit_input.text()
        print(f"Submitted: {input_text}")
```

---

## 3. 动态加载方案（`QUiLoader`）

适用于轻量原型、测试或无需静态编译的场景。

```python
from PySide6.QtCore import QFile
from PySide6.QtWidgets import QMainWindow
from PySide6.QtUiTools import QUiLoader

class DynamicMainWindow(QMainWindow):
    def __init__(self, ui_file_path, parent=None):
        super().__init__(parent)
        loader = QUiLoader()
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        self.setCentralWidget(self.ui)
        # 访问控件
        self.ui.btn_submit.clicked.connect(self.handle_submit)
```

---

## 4. 资源文件协同（`.qrc` 与 `pyside6-rcc`）
当 UI 中引用了本地图标、背景图时：
1. 编写资源清单 `resources.qrc`；
2. 编译资源文件：
   ```bash
   pyside6-rcc resources.qrc -o resources_rc.py
   ```
3. 在主入口或生成的代码中导入 `import resources_rc`。
