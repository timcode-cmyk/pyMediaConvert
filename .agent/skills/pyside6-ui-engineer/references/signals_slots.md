# PySide6 Signals & Slots Best Practices

信号与槽是 Qt 实现组件解耦与事件驱动的核心机制。

---

## 1. 规范与命名
- **自定义信号声明必须放在类属性层级**（绝不能在 `__init__` 中动态创建）：
  ```python
  class TaskManager(QObject):
      task_started = Signal(str)          # 过去式或动作态：[名词]_[动词]
      progress_updated = Signal(int, int) # 参数类型强声明
      task_finished = Signal(dict)
  ```
- **槽函数使用 `@Slot()` 装饰器**：
  在 PySide6 中使用 `@Slot(...)` 装饰器可以减少 Python 与 C++ 原生层的跨语言调用开销并提供类型安全性：
  ```python
  @Slot(int, int)
  def on_progress_updated(self, current: int, total: int):
      self.progress_bar.setValue(int(current / total * 100))
  ```

---

## 2. 避免循环引用与悬空引用
- 连接跨生命周期的对象时，若槽函数是 Python 方法，注意父子对象拥有关系，必要时通过 `sender.destroyed` 处理或在销毁前明确调用 `disconnect()`。
- 跨线程传递数据时，信号参数尽量传递基本不可变数据类型（如 `str`, `int`, `dict`, `tuple`），避免传递大且具有状态的原生 C++ 指针对象。
