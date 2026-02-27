# yt-dlp 版本管理 - 快速参考

## 📌 快速开始

### UI中使用（最简单的方式）

应用启动后：
1. 打开 Video Download 标签页
2. 看到顶部 "yt-dlp 版本管理" 区域
3. 点击 "🔄 检查更新"
4. 如果有新版本，点击 "⬆️ 更新"
5. 等待完成

### 代码中使用

```python
from pyMediaTools.core.ytdlp_updater import YtDlpVersionManager

manager = YtDlpVersionManager()
version = manager.get_local_version()
print(f"本地版本: {version}")
```

---

## 🎯 常用操作速查表

| 操作 | 代码 | 说明 |
|------|------|------|
| 获取本地版本 | `manager.get_local_version()` | 从yt_dlp/version.py读取 |
| 获取远程版本 | `manager.get_remote_version()` | 优先GitHub，备选PyPI |
| 检查更新 | `manager.check_update_available()` | 返回(has_update, local, remote) |
| 创建备份 | `manager.backup_current()` | 返回备份路径 |
| 回滚版本 | `manager.rollback()` | 回滚到最新备份 |
| 更新(GitHub) | `updater.update_from_github()` | 返回(success, message) |
| 更新(PyPI) | `updater.update_from_pypi()` | 返回(success, message) |
| 异步检查 | `YtDlpCheckUpdateWorker()` | 不阻塞UI的检查 |
| 异步更新 | `YtDlpUpdateWorker()` | 不阻塞UI的更新 |

---

## 🔧 常见任务

### 任务 1: 检查是否有新版本

```python
from pyMediaTools.core.ytdlp_updater import YtDlpVersionManager

manager = YtDlpVersionManager()
has_update, local, remote = manager.check_update_available()

if has_update:
    print(f"新版本可用: {remote} (当前: {local})")
else:
    print(f"已是最新版本: {local}")
```

**输出示例**:
```
新版本可用: 2026.02.10 (当前: 2026.02.04)
或
已是最新版本: 2026.02.04
```

---

### 任务 2: 安全地更新yt-dlp

```python
from pyMediaTools.core.ytdlp_updater import YtDlpUpdater

updater = YtDlpUpdater()

# 自动备份 → 下载 → 验证 → 替换
success, message = updater.update_from_github()

if success:
    print(f"✓ {message}")
else:
    print(f"✗ {message}")
    # 会自动回滚
```

**流程**:
1. 自动备份当前版本
2. 下载新版本源代码
3. 验证文件完整性
4. 替换yt_dlp目录
5. 失败则自动回滚

---

### 任务 3: UI中使用（异步，不卡UI）

```python
# 在PySide6 Widget中
from pyMediaTools.core.ytdlp_update_worker import YtDlpCheckUpdateWorker

worker = YtDlpCheckUpdateWorker()
worker.version_checked.connect(self.on_version_checked)
worker.error.connect(self.on_error)
worker.start()

def on_version_checked(self, info):
    if info['has_update']:
        # 显示更新可用
        pass
```

---

### 任务 4: 手动回滚到之前的版本

```python
from pyMediaTools.core.ytdlp_updater import YtDlpVersionManager

manager = YtDlpVersionManager()

# 获取所有备份
latest_backup = manager.get_latest_backup()

# 回滚到最新备份
success = manager.rollback()

# 或指定备份路径
success = manager.rollback('/path/to/backup')

if success:
    print("✓ 回滚成功")
else:
    print("✗ 回滚失败")
```

---

### 任务 5: 获取版本发布信息

```python
from pyMediaTools.core.ytdlp_updater import YtDlpVersionManager

manager = YtDlpVersionManager()

# 获取特定版本的发布信息
info = manager.get_release_info('2026.02.10')

if info:
    print(f"发布时间: {info['published_at']}")
    print(f"发布页面: {info['download_url']}")
    print(f"\n更新说明:\n{info['body']}")
```

---

## 📂 文件位置速查

| 内容 | 位置 |
|------|------|
| 本地版本号 | `pyMediaConvert/yt_dlp/version.py` |
| 版本管理核心 | `pyMediaTools/core/ytdlp_updater.py` |
| 更新Worker | `pyMediaTools/core/ytdlp_update_worker.py` |
| 视频下载UI | `pyMediaTools/ui/video_downloader_ui.py` |
| 备份目录 | `pyMediaConvert/.yt_dlp_backups/` |
| 备份元数据 | `pyMediaConvert/.yt_dlp_backups/update_metadata.json` |

---

## ⚡ 方法速查

### YtDlpVersionManager 方法

```python
manager = YtDlpVersionManager()

# 获取版本
manager.get_local_version()                          # 本地版本
manager.get_remote_version_from_github(timeout=10)   # GitHub版本
manager.get_remote_version_from_pypi(timeout=10)     # PyPI版本
manager.get_remote_version(timeout=10)               # 自动选择源

# 检查更新
manager.check_update_available(timeout=10)           # (has_update, local, remote)

# 备份管理
manager.backup_current()                             # 备份当前版本
manager.get_latest_backup()                          # 获取最新备份
manager.rollback(backup_path=None)                   # 回滚到备份

# 信息查询
manager.get_release_info(version)                    # 发布信息
```

### YtDlpUpdater 方法

```python
updater = YtDlpUpdater()

# 更新执行
updater.update_from_github()                         # (success, message)
updater.update_from_pypi()                          # (success, message)

# 继承自YtDlpVersionManager的所有方法
```

### VersionComparator 方法

```python
from pyMediaTools.core.ytdlp_updater import VersionComparator

# 版本比较
VersionComparator.parse_version('2026.02.04')       # (2026, 2, 4)
VersionComparator.is_newer('2026.02.04', '2026.02.03')    # True
VersionComparator.is_same('2026.02.04', '2026.02.04')     # True
```

---

## 🎛️ 配置选项

### 构造函数参数

```python
# 默认（使用项目根目录下的yt_dlp）
manager = YtDlpVersionManager()

# 自定义yt_dlp目录
manager = YtDlpVersionManager('/custom/path/to/yt_dlp')
```

### 方法参数

```python
# 超时时间（秒）
manager.get_remote_version_from_github(timeout=20)    # 默认10秒

# 备份路径
manager.rollback(backup_path='/specific/backup')      # 默认最新备份

# 更新方式
updater.update_from_github()                         # 从源代码更新
updater.update_from_pypi()                           # 从PyPI更新
```

---

## 📊 信号 (Signal) 列表

### YtDlpCheckUpdateWorker

| 信号 | 参数 | 说明 |
|------|------|------|
| `version_checked` | dict | 版本检查结果 |
| `error` | str | 错误消息 |

**version_checked 参数**:
```python
{
    'has_update': bool,        # 是否有新版本
    'local_version': str,      # 本地版本
    'remote_version': str,     # 远程版本
    'error': None              # 错误信息
}
```

### YtDlpUpdateWorker

| 信号 | 参数 | 说明 |
|------|------|------|
| `progress` | str | 进度消息 |
| `finished` | dict | 更新完成结果 |
| `error` | str | 错误消息 |

**finished 参数**:
```python
{
    'success': bool,          # 是否成功
    'message': str,           # 结果消息
    'new_version': str,       # 新版本号
    'old_version': str        # 旧版本号
}
```

### YtDlpRollbackWorker

| 信号 | 参数 | 说明 |
|------|------|------|
| `progress` | str | 进度消息 |
| `finished` | dict | 回滚完成结果 |
| `error` | str | 错误消息 |

---

## 🐛 调试技巧

### 启用详细日志

```python
import logging

# 设置DEBUG级别
logging.getLogger('pyMediaTools').setLevel(logging.DEBUG)

# 查看详细的API请求信息
logging.getLogger('urllib3').setLevel(logging.DEBUG)
```

### 检查备份目录

```python
import os
from pyMediaTools.core.ytdlp_updater import YtDlpVersionManager

manager = YtDlpVersionManager()

# 列出所有备份
backup_dir = manager.backup_dir
if os.path.exists(backup_dir):
    backups = os.listdir(backup_dir)
    print(f"备份目录: {backup_dir}")
    print(f"备份列表: {backups}")
```

### 查看元数据

```python
import json
from pyMediaTools.core.ytdlp_updater import YtDlpVersionManager

manager = YtDlpVersionManager()

# 读取备份元数据
with open(manager.metadata_file, 'r') as f:
    metadata = json.load(f)
    for backup_name, info in metadata.items():
        print(f"{backup_name}: {info}")
```

---

## ❌ 常见错误和解决方案

| 错误 | 原因 | 解决 |
|------|------|------|
| `无法连接GitHub` | 网络问题 | 检查网络，或使用PyPI源 |
| `版本文件不存在` | yt_dlp目录损坏 | 重新克隆官方源代码 |
| `备份失败` | 磁盘空间不足 | 清理磁盘或删除旧备份 |
| `回滚失败` | 权限问题 | 检查目录权限 |
| `超时` | 网络较慢 | 增加timeout参数值 |

---

## 📈 版本号格式

系统支持 `YYYY.MM.DD` 格式：

```
当前: 2026.02.04 → Year: 2026, Month: 2, Day: 4
最新: 2026.02.10 → Year: 2026, Month: 2, Day: 10
旧版: 2025.12.25 → Year: 2025, Month: 12, Day: 25
```

**比较规则**: 按年月日顺序比较，日期更晚的版本号更高

---

## 🔗 相关资源

- **官方仓库**: https://github.com/yt-dlp/yt-dlp
- **PyPI包**: https://pypi.org/project/yt-dlp/
- **GitHub API文档**: https://docs.github.com/en/rest

---

## 📝 示例代码合集

### 例 1: 完整的检查和更新流程

```python
from pyMediaTools.core.ytdlp_updater import YtDlpVersionManager, YtDlpUpdater

# 初始化
manager = YtDlpVersionManager()
updater = YtDlpUpdater()

# 步骤1: 检查更新
local, remote = manager.get_local_version(), manager.get_remote_version()
print(f"本地: {local}, 远程: {remote}")

# 步骤2: 如果有更新，执行更新
if remote and manager.check_update_available()[0]:
    print("开始更新...")
    success, msg = updater.update_from_github()
    
    if success:
        print(f"✓ {msg}")
    else:
        print(f"✗ {msg} (已自动回滚)")
```

### 例 2: 在PySide6中使用

```python
from PySide6.QtWidgets import QWidget
from pyMediaTools.core.ytdlp_update_worker import YtDlpCheckUpdateWorker

class MyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.check_worker = None
    
    def check_update(self):
        self.check_worker = YtDlpCheckUpdateWorker()
        self.check_worker.version_checked.connect(self.on_done)
        self.check_worker.start()
    
    def on_done(self, info):
        if info['has_update']:
            print(f"新版本: {info['remote_version']}")
```

### 例 3: 异步更新并显示进度

```python
from pyMediaTools.core.ytdlp_update_worker import YtDlpUpdateWorker
from PySide6.QtWidgets import QProgressDialog

dialog = QProgressDialog("更新中...", None, 0, 0)

worker = YtDlpUpdateWorker()
worker.progress.connect(dialog.setLabelText)
worker.finished.connect(dialog.accept)
worker.error.connect(dialog.reject)
worker.start()

dialog.exec()
```

---

**快速参考版本**: 1.0  
**最后更新**: 2025-02-16
