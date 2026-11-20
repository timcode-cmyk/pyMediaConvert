# PySide6 Model/View Architecture Guide

Qt 的 Model/View 架构用于高效渲染和管理大量、动态变化的数据。

---

## 1. 适用场景选型
- **数据量 < 100 行，简单展示**：可直接使用 `QTableWidget` / `QListWidget` / `QTreeWidget`（便捷型控件）。
- **数据量 >= 100 行，需要动态增删、搜索过滤、自定义渲染或频繁刷新**：必须使用 `QTableView` / `QListView` / `QTreeView` 搭配底层 Model（如 `QAbstractTableModel`）。

---

## 2. 基础自定义 TableModel 范式
```python
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex

class MediaTableModel(QAbstractTableModel):
    def __init__(self, data=None):
        super().__init__()
        self._data = data or []
        self._headers = ["文件名", "格式", "大小", "状态"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        row = index.row()
        col = index.column()
        return self._data[row][col]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None
```
- **数据更新通知**：当数据列表发生变动时，必须通过 `self.beginResetModel()` / `self.endResetModel()` 或 `beginInsertRows()` / `endInsertRows()` 通知视图，不可仅修改 Python 内存列表。
