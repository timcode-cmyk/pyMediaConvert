# yt-dlp 版本管理系统 - 集成指南

## 📋 功能概述

为pyMediaTools的视频下载功能添加了完整的yt-dlp源代码版本检测、更新和管理系统。

### 核心功能

✅ **版本检测**
- 获取本地yt-dlp版本
- 获取远程最新版本（GitHub/PyPI）
- 版本号对比（支持YYYY.MM.DD格式）

✅ **自动更新** 
- 从GitHub下载最新源代码
- 通过PyPI package更新
- 自动备份当前版本
- 更新失败自动回滚

✅ **版本管理**
- 备份版本历史
- 一键回滚到历史版本
- 查看发布信息和更新日志

✅ **用户界面**
- Video downloader 顶部版本显示
- 检查更新按钮
- 更新进度对话框
- 实时日志输出

---

## 🏗️ 系统架构

```
UI 层 (video_downloader_ui.py)
    ├── VideoDownloadWidget (添加版本管理UI)
    └── YtDlpUpdateDialog (更新进度展示)
        
业务逻辑层 (core/)
    ├── ytdlp_updater.py
    │   ├── VersionComparator (版本比较)
    │   ├── YtDlpVersionManager (版本检测/备份/回滚)
    │   └── YtDlpUpdater (版本更新)
    │
    └── ytdlp_update_worker.py
        ├── YtDlpCheckUpdateWorker (异步检查)
        ├── YtDlpUpdateWorker (异步更新)
        └── YtDlpRollbackWorker (异步回滚)

数据存储
    ├── yt_dlp/version.py (本地版本文件)
    └── .yt_dlp_backups/ (备份目录)
        └── update_metadata.json (备份元数据)
```

---

## 📦 创建的文件列表

### 1. **pyMediaTools/core/ytdlp_updater.py** (650行)
核心版本管理模块

**主要类**:
- `VersionComparator` - 版本号比较工具
- `YtDlpVersionManager` - 版本检测、备份、回滚
- `YtDlpUpdater` - 版本更新执行器

**主要方法**:
```python
# 版本检测
get_local_version() -> str|None
get_remote_version(timeout=10) -> str|None
check_update_available(timeout=10) -> (bool, str, str)

# 备份和回滚
backup_current() -> str|None
rollback(backup_path=None) -> bool
get_latest_backup() -> str|None

# 更新执行
update_from_github() -> (bool, str)
update_from_pypi() -> (bool, str)

# 信息查询
get_release_info(version) -> dict|None
```

### 2. **pyMediaTools/core/ytdlp_update_worker.py** (140行)
异步Worker线程实现

**主要类**:
- `YtDlpCheckUpdateWorker` - 异步版本检查
- `YtDlpUpdateWorker` - 异步更新执行
- `YtDlpRollbackWorker` - 异步回滚执行

**信号**:
```python
# YtDlpCheckUpdateWorker
version_checked -> dict
error -> str

# YtDlpUpdateWorker  
progress -> str
finished -> dict
error -> str

# YtDlpRollbackWorker
progress -> str
finished -> dict
error -> str
```

### 3. **pyMediaTools/ui/video_downloader_ui.py** (改进版本, +200行)
增强的视频下载UI

**新增UI组件**:
- 版本显示标签
- 检查更新按钮
- 更新按钮
- 更新进度对话框

**新增方法**:
```python
check_update_async()              # 异步检查更新
on_version_checked(info)         # 版本检查回调
on_check_update_error(error)     # 检查错误回调
start_update()                   # 启动更新
on_update_finished(info, dialog) # 更新完成回调
on_update_error(error, dialog)   # 更新错误回调
```

**新增对话框类**:
- `YtDlpUpdateDialog` - 更新进度对话框

---

## 🚀 使用方法

### 方法 1: 在 Video Downloader UI 中使用

应用启动时会自动检查yt-dlp版本。

```
1. 打开Video Downloader标签页
2. 看到顶部 "yt-dlp 版本管理" 区域
3. 点击 "🔄 检查更新" 按钮
4. 如果有新版本，"⬆️ 更新" 按钮会启用
5. 点击 "⬆️ 更新" 确认更新
6. 等待更新完成（进度窗口显示日志）
```

### 方法 2: 在代码中直接使用

```python
from pyMediaTools.core.ytdlp_updater import YtDlpVersionManager, YtDlpUpdater

# 创建版本管理器
manager = YtDlpVersionManager()

# 获取版本
local_version = manager.get_local_version()
remote_version = manager.get_remote_version()

# 检查更新
has_update, local, remote = manager.check_update_available()

# 备份和更新
if has_update:
    backup = manager.backup_current()
    
    updater = YtDlpUpdater()
    success, message = updater.update_from_github()
    
    if not success:
        manager.rollback()  # 出错时回滚
```

### 方法 3: 使用异步Worker线程

```python
from pyMediaTools.core.ytdlp_update_worker import YtDlpCheckUpdateWorker, YtDlpUpdateWorker

# 检查更新
check_worker = YtDlpCheckUpdateWorker()
check_worker.version_checked.connect(handle_version_check)
check_worker.start()

# 执行更新  
update_worker = YtDlpUpdateWorker(update_method='github')
update_worker.progress.connect(on_progress)
update_worker.finished.connect(on_finished)
update_worker.start()
```

---

## 💾 文件位置和备份

### 本地版本文件
```
pyMediaConvert/yt_dlp/version.py
```

### 备份目录
```
pyMediaConvert/.yt_dlp_backups/
├── yt_dlp_backup_2026.02.04_20250216_120530/
├── yt_dlp_backup_2026.02.03_20250215_143200/
└── update_metadata.json
```

### 备份元数据格式
```json
{
  "yt_dlp_backup_2026.02.04_20250216_120530": {
    "version": "2026.02.04",
    "timestamp": "2025-02-16T12:05:30.123456",
    "path": ".../yt_dlp_backup_2026.02.04_20250216_120530"
  }
}
```

---

## ⚙️ 配置和扩展

### 自定义yt_dlp目录

```python
# 默认使用项目根目录下的 yt_dlp 目录
manager = YtDlpVersionManager()

# 或指定自定义目录
manager = YtDlpVersionManager('/custom/path/to/yt_dlp')
```

### 修改超时时间

```python
# 检查更新时指定超时
has_update, _, _ = manager.check_update_available(timeout=20)

# 获取远程版本时指定超时
version = manager.get_remote_version_from_github(timeout=15)
```

### 切换更新源

```python
# 使用GitHub
success, msg = updater.update_from_github()

# 使用PyPI
success, msg = updater.update_from_pypi()
```

---

## 🔒 安全特性

### 1. 自动备份
- 更新前自动备份当前版本
- 备份保存在隐藏目录 `.yt_dlp_backups/`
- 支持多个备份版本

### 2. 自动回滚
- 更新失败时自动恢复备份
- 手动回滚到任意历史版本
- 回滚不会删除更新失败的文件

### 3. 版本验证
- 验证下载文件的有效性
- 确保源代码结构完整
- 失败时中止操作

### 4. 权限检查
- 检查yt_dlp目录的写入权限
- 自动创建必要的备份目录

---

## 🧪 测试

运行集成测试：

```bash
python test_ytdlp_version_management.py
```

**测试覆盖**:
1. 版本比较工具
2. 获取本地版本
3. 获取远程版本（GitHub和PyPI）
4. 检查更新功能
5. 备份和回滚
6. 发布信息获取

---

## 📊 版本格式

系统支持 `YYYY.MM.DD` 格式的版本号：

```
2026.02.04   → Year: 2026, Month: 02, Day: 04
2025.12.31   → Year: 2025, Month: 12, Day: 31
```

版本比较遵循时间顺序，最新的日期为最新版本。

---

## 🐛 故障排除

### 问题 1: 无法连接GitHub/PyPI

**原因**: 网络问题或API限制

**解决**:
- 检查网络连接
- 尝试手动访问 https://github.com/yt-dlp/yt-dlp
- 如果公网不可用，考虑使用镜像源
- 查看日志获取详细错误信息

### 问题 2: 更新失败

**原因**: 磁盘空间不足、权限问题等

**解决**:
- 系统自动回滚到备份版本
- 检查磁盘空间
- 确保有足够的写入权限
- 查看更新日志了解具体错误

### 问题 3: 备份空间过大

**原因**: 多个旧版本备份

**解决**:
- 手动清理 `.yt_dlp_backups/` 目录中旧的备份
- 只保留最近的 2-3 个备份

### 问题 4: 版本获取失败

**原因**: yt-dlp源代码目录结构异常

**解决**:
- 确保 `yt_dlp/version.py` 文件存在
- 检查文件内容，确保包含 `__version__` 定义
- 如需重新安装，从 GitHub 克隆官方源代码

---

## 📝 日志记录

系统使用Python标准logging模块，日志包括：

- **DEBUG**: 版本号解析、API请求详情
- **INFO**: 备份完成、更新成功等
- **WARNING**: 网络连接失败、版本文件缺失
- **ERROR**: 更新过程异常、权限问题

日志配置在 `pyMediaTools/logging_config.py` 中。

---

## 🔄 更新流程图

```
用户点击检查更新
    ↓
[YtDlpCheckUpdateWorker]
    ├─ 获取本地版本 (yt_dlp/version.py)
    ├─ 获取GitHub最新版本 (API)
    └─ 对比版本
        ↓
有新版本? ──是→ 启用更新按钮
    ↓
   否 → 提示已是最新

用户点击更新
    ↓
显示确认对话框 ──用户取消─→ 返回
    ↓
   用户确认
    ↓
[YtDlpUpdateWorker]
    ├─ 备份当前版本
    ├─ 下载新版本
    ├─ 验证文件
    ├─ 替换yt_dlp目录
    └─ 报告结果
        ↓
更新成功? ──是→ 刷新版本标签 → 完成
    ↓
   否 → 自动回滚 → 显示错误
```

---

## 📚 API 参考

### YtDlpVersionManager

```python
class YtDlpVersionManager:
    # 构造函数
    def __init__(self, yt_dlp_dir: str = None)
    
    # 版本查询
    def get_local_version() -> Optional[str]
    def get_remote_version_from_github(timeout=10) -> Optional[str]
    def get_remote_version_from_pypi(timeout=10) -> Optional[str]
    def get_remote_version(timeout=10) -> Optional[str]
    
    # 检查更新
    def check_update_available(timeout=10) -> Tuple[bool, Optional[str], Optional[str]]
    
    # 备份管理
    def backup_current() -> Optional[str]
    def get_latest_backup() -> Optional[str]
    def rollback(backup_path=None) -> bool
    
    # 发布信息
    def get_release_info(version: str) -> Optional[Dict]
```

### YtDlpUpdater (继承YtDlpVersionManager)

```python
class YtDlpUpdater(YtDlpVersionManager):
    def update_from_github() -> Tuple[bool, str]
    def update_from_pypi() -> Tuple[bool, str]
```

### VersionComparator

```python
class VersionComparator:
    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, int, int]
    
    @staticmethod
    def is_newer(version_a: str, version_b: str) -> bool
    
    @staticmethod
    def is_same(version_a: str, version_b: str) -> bool
```

---

## 📄 相关文件

- [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md) - 项目详细分析
- [test_ytdlp_version_management.py](test_ytdlp_version_management.py) - 集成测试
- [pyMediaTools/core/ytdlp_updater.py](pyMediaTools/core/ytdlp_updater.py) - 核心模块
- [pyMediaTools/core/ytdlp_update_worker.py](pyMediaTools/core/ytdlp_update_worker.py) - Worker线程
- [pyMediaTools/ui/video_downloader_ui.py](pyMediaTools/ui/video_downloader_ui.py) - UI集成

---

## 🎯 后续扩展建议

1. **定时检查** - 添加后台定时检查更新的功能
2. **中文镜像** - 支持从国内镜像源下载（加速）
3. **预览发布说明** - 在更新前展示完整的更新日志
4. **自动更新** - 根据用户偏好自动更新
5. **多版本管理** - 支持同时使用多个版本
6. **命令行工具** - 提供CLI接口进行版本管理

---

**最后更新**: 2025-02-16  
**版本**: 1.0  
**作者**: GitHub Copilot
