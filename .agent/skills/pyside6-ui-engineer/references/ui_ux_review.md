# PySide6 UI/UX Review Checklist

本文档作为 PySide6 界面上线与重构前的自查清单。

---

## 1. 3秒法则与首要操作（3-Second Rule & Primary Action）
- [ ] 页面在 3 秒内能否向用户清晰传达当前页面的主要目的？
- [ ] 当前屏幕上是否有且仅有一个最显著的“主按钮/操作”（Primary Button）？
- [ ] 次要操作与危险操作是否通过幽灵按钮（Outline/Ghost）或警戒色进行了合理区分？

---

## 2. 状态机全覆盖（State Completeness）
- [ ] **Empty State（空状态）**：列表或内容为空时，是否有友好的插画/文字提示与明确的引导操作？
- [ ] **Loading/Busy State（加载态）**：长时间任务是否有进度条、微调旋转器（Spinner）或不可重复点击的禁用保护？
- [ ] **Validation & Error State（校验态）**：输入非法时，是否有原位（In-place）红色提示，而不是生硬弹窗？

---

## 3. 布局与呼吸感（Layout & Spacing）
- [ ] 严禁使用固定绝对坐标（`setGeometry`）；统一使用布局管理器。
- [ ] 边距与间距统一规范（如主内边距 15~20px，控件间距 8~12px）。
- [ ] 控件圆角与阴影保持统一（通常 6px ~ 8px）。
- [ ] 鼠标悬停可点击区域已配置 `Qt.PointingHandCursor`。
