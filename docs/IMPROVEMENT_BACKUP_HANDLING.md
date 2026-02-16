# yt-dlp 版本管理 - 功能改进文档

## 📋 改进内容

基于用户反馈，对版本更新系统进行了两项重要改进：

### 问题 1: 备份失败导致更新失败
**原始问题**: 如果本地源码不存在或损坏，`backup_current()` 返回 None，导致整个更新流程中止。

**改进方案**:
- 新增 `_is_yt_dlp_corrupted()` 方法检查本地源码完整性
- 如果源码不存在或已损坏，跳过备份直接下载
- 如果备份失败但源码完整，仍继续更新（不中止）
- 大幅提高了更新的可靠性

### 问题 2: 备份文件堆积
**原始问题**: 每次更新都创建新备份，备份文件越来越多占用磁盘空间。

**改进方案**:
- 新增 `_cleanup_old_backups()` 方法自动清理旧备份
- 默认只保留最新的3个备份
- 更新成功后自动清理
- 同时清理备份元数据

---

## 🔧 新增方法详解

### 1. `_is_yt_dlp_corrupted()` -> bool
检查yt_dlp源代码是否已损坏或不完整

**检查项**:
- ✓ 目录是否存在
- ✓ `version.py` 是否存在
- ✓ `__init__.py` 是否存在  
- ✓ `version.py` 是否可读（能否提取版本号）

**返回值**:
- `True`: 源码不存在或已损坏
- `False`: 源码完整且可用

**日志**:
- DEBUG: 源码验证通过消息
- WARNING: 各个缺失项的警告
- ERROR: 检查过程中的异常

---

### 2. `_cleanup_old_backups(keep_latest=3)` -> int
清理旧备份文件，只保留最新的N个

**参数**:
- `keep_latest`: 保留的最新备份数量，默认为3

**功能**:
1. 列出所有 `yt_dlp_backup_*` 目录
2. 按修改时间排序（最新的在前）
3. 删除超出 `keep_latest` 的备份目录
4. 同步删除元数据中的记录

**返回值**: 
- 清理的备份数量

**日志**:
- INFO: 删除备份的名称
- INFO: 清理完成摘要
- WARNING: 清理元数据失败或删除备份失败

**示例**:
```
备份目录:
  yt_dlp_backup_2026.02.10_20250216_120530/  ← 保留 (最新)
  yt_dlp_backup_2026.02.04_20250215_143200/  ← 保留 (第2新)
  yt_dlp_backup_2026.01.20_20250214_100000/  ← 保留 (第3新)
  yt_dlp_backup_2026.01.10_20250213_090000/  ← 删除 (过旧)
  yt_dlp_backup_2025.12.20_20250212_080000/  ← 删除 (过旧)
```

---

## 📊 改进的流程图

### 改进前
```
检查远程版本
    ↓
备份当前版本 ← 失败返回错误
    ↓
[中止，无法更新]
```

### 改进后

#### 情况 A: 源码完整
```
检查远程版本
    ↓
检查源码完整性 ✓ 完整
    ↓
备份当前版本
    ├─ 成功 → 继续
    └─ 失败 → 仍继续（不中止）
    ↓
下载新版本
    ↓
更新成功 → 清理旧备份 (保留3个)
```

#### 情况 B: 源码不存在或损坏
```
检查远程版本
    ↓
检查源码完整性 ✗ 损坏/不存在
    ↓
跳过备份 (直接下载)
    ↓
下载新版本
    ↓
更新成功 → 清理旧备份 (保留3个)
```

---

## 🎯 使用场景

### 场景 1: 全新安装或源码损坏
```
用户环境: yt_dlp 目录不存在或损坏
操作: 点击"更新"按钮
结果: 
  ✓ 系统自动判断源码不存在
  ✓ 跳过备份直接下载最新版本
  ✓ 成功安装完整的yt-dlp
```

### 场景 2: 备份堆积
```
用户情况: 已有多次备份
  - yt_dlp_backup_2026.02.10_...
  - yt_dlp_backup_2026.02.04_...
  - yt_dlp_backup_2026.01.20_...
  - yt_dlp_backup_2026.01.10_...
  - yt_dlp_backup_2025.12.20_...

执行: 新的更新操作
结果:
  ✓ 创建新备份
  ✓ 更新成功后自动清理
  ✓ 只保留最新的3个备份
  ✓ 节省磁盘空间
```

### 场景 3: 备份失败但源码完整
```
用户情况: 磁盘空间不足导致备份失败
执行: 更新操作
结果:
  ✓ 系统检测到备份失败但源码完整
  ✓ 日志记录警告信息
  ✓ 继续进行更新操作（不中止）
  ✓ 更新成功
```

---

## 💾 备份管理

### 备份目录结构
```
.yt_dlp_backups/
├── yt_dlp_backup_2026.02.10_20250216_120530/  (最新)
├── yt_dlp_backup_2026.02.04_20250215_143200/  (次新)
├── yt_dlp_backup_2026.01.20_20250214_100000/  (第3新)
└── update_metadata.json  (元数据)
```

### 备份元数据格式
```json
{
  "yt_dlp_backup_2026.02.10_20250216_120530": {
    "version": "2026.02.10",
    "timestamp": "2025-02-16T12:05:30.123456",
    "path": ".../yt_dlp_backup_2026.02.10_20250216_120530"
  },
  "yt_dlp_backup_2026.02.04_20250215_143200": {
    "version": "2026.02.04",
    "timestamp": "2025-02-15T14:32:00.654321",
    "path": ".../yt_dlp_backup_2026.02.04_20250215_143200"
  }
}
```

### 清理策略

**默认保留**: 最新的3个备份
**清理时机**: 更新成功后立即执行
**清理范围**:
- 备份目录及其内容
- 元数据中的记录

**配置方式**:
```python
# 修改保留备份数量
updater._cleanup_old_backups(keep_latest=5)  # 保留5个
```

---

## 📈 改进效果

| 方面 | 改进前 | 改进后 |
|------|--------|--------|
| 源码不存在时 | ❌ 更新失败 | ✅ 直接下载 |
| 备份失败时 | ❌ 更新中止 | ✅ 继续更新 |
| 备份积压 | ❌ 持续增长 | ✅ 自动清理 |
| 磁盘占用 | 📈 逐渐增加 | 📊 保持稳定 |
| 可靠性 | 中等 | ✅ 企业级 |

---

## 🔍 日志示例

### 成功的更新流程
```
INFO:pyMediaTools.core.ytdlp_updater:正在检查本地版本...
INFO:pyMediaTools.core.ytdlp_updater:本地版本检查完成
INFO:pyMediaTools.core.ytdlp_updater:正在从GitHub获取最新版本...
INFO:pyMediaTools.core.ytdlp_updater:GitHub最新版本: 2026.02.10
INFO:pyMediaTools.core.ytdlp_updater:发现新版本: 2026.02.10 (当前: 2026.02.04)
DEBUG:pyMediaTools.core.ytdlp_updater:yt_dlp源代码验证通过，版本: 2026.02.04
INFO:pyMediaTools.core.ytdlp_updater:正在备份当前版本...
INFO:pyMediaTools.core.ytdlp_updater:备份成功: /path/.yt_dlp_backups/yt_dlp_backup_2026.02.04_20250216_120530
INFO:pyMediaTools.core.ytdlp_updater:正在下载版本 2026.02.10...
INFO:pyMediaTools.core.ytdlp_updater:下载完成: /path/.yt_dlp_backups/yt_dlp_2026.02.10.zip
INFO:pyMediaTools.core.ytdlp_updater:成功替换yt_dlp目录
INFO:pyMediaTools.core.ytdlp_updater:已清理临时文件
INFO:pyMediaTools.core.ytdlp_updater:清理旧备份文件...
INFO:pyMediaTools.core.ytdlp_updater:已删除旧备份: yt_dlp_backup_2026.01.10_20250213_090000
INFO:pyMediaTools.core.ytdlp_updater:清理完成，共删除 1 个旧备份
INFO:pyMediaTools.core.ytdlp_updater:更新成功，新版本: 2026.02.10
```

### 源码损坏时的更新流程
```
INFO:pyMediaTools.core.ytdlp_updater:正在检查本地版本...
WARNING:pyMediaTools.core.ytdlp_updater:yt_dlp目录不存在或已损坏
WARNING:pyMediaTools.core.ytdlp_updater:本地源码不存在或已损坏，将直接下载最新版本...
INFO:pyMediaTools.core.ytdlp_updater:正在下载版本 2026.02.10...
INFO:pyMediaTools.core.ytdlp_updater:下载完成: /path/.yt_dlp_backups/yt_dlp_2026.02.10.zip
INFO:pyMediaTools.core.ytdlp_updater:成功替换yt_dlp目录
INFO:pyMediaTools.core.ytdlp_updater:已清理临时文件
INFO:pyMediaTools.core.ytdlp_updater:清理旧备份文件...
INFO:pyMediaTools.core.ytdlp_updater:更新成功，新版本: 2026.02.10
```

---

## 🧪 测试方法

### 测试 1: 源码完整的更新
```bash
python3 << 'EOF'
from pyMediaTools.core.ytdlp_updater import YtDlpUpdater

updater = YtDlpUpdater()
success, msg = updater.update_from_github()
print(f"更新结果: {success}, 消息: {msg}")
EOF
```

### 测试 2: 检查备份清理
```bash
ls -la .yt_dlp_backups/
# 应该只有最新的3个备份目录
```

### 测试 3: 源码损坏时的更新
```bash
# 临时移走yt_dlp目录
mv yt_dlp yt_dlp.bak

# 执行更新
python3 << 'EOF'
from pyMediaTools.core.ytdlp_updater import YtDlpUpdater

updater = YtDlpUpdater()
success, msg = updater.update_from_github()
print(f"更新结果: {success}, 消息: {msg}")
EOF

# 恢复原目录
rm -rf yt_dlp
mv yt_dlp.bak yt_dlp
```

---

## 🛡️ 安全性

✅ **自动备份** - 源码完整时自动备份  
✅ **智能检查** - 多层检查源码完整性  
✅ **失败恢复** - 备份失败时仍继续（不中止）  
✅ **源码损坏时** - 自动直接下载（跳过备份）  
✅ **空间管理** - 自动清理过旧备份  
✅ **元数据同步** - 删除备份时同步删除元数据

---

## 📝 代码改动统计

**新增方法**: 2个
- `_is_yt_dlp_corrupted()`
- `_cleanup_old_backups()`

**修改方法**: 2个
- `update_from_github()` - 改进备份处理 + 清理旧备份
- `update_from_pypi()` - 改进备份处理 + 清理旧备份

**代码增量**: ~150 行

**功能改进**: 100% 向后兼容

---

**改进完成**: 2025-02-16  
**版本**: 1.2 (功能增强)  
**状态**: ✅ 测试完成
