# yt-dlp 更新问题修复说明

## 🐛 问题描述

用户在执行yt-dlp版本更新时遇到错误：
```
下载的文件格式不正确
已自动回滚到原版本。
```

## 🔍 根本原因

在 `ytdlp_updater.py` 的 `update_from_github()` 方法中，GitHub zip包的目录结构处理存在问题：

### 原始代码的问题：

```python
# 错误的目录名称
extract_dir = os.path.join(self.backup_dir, f"yt_dlp_{remote_version}")

# GitHub zip包实际结构：yt-dlp-<version>/yt_dlp/
# 但代码期望是：yt_dlp_<version>/yt_dlp/
```

**具体问题**：
1. GitHub生成的zip包目录名是 `yt-dlp-<version>`（用dash连接）
2. 代码期望的临时目录名是 `yt_dlp_<version>`（用underscore连接）
3. 目录名称不匹配导致源代码查找失败
4. 最终触发"下载的文件格式不正确"的错误

## ✅ 解决方案

### 1. 改进的目录结构处理

```python
# 使用临时目录（不再依赖特定的目录命名约定）
temp_extract_dir = os.path.join(self.backup_dir, f"yt_dlp_temp_{remote_version}")

# 方式1: 直接查找yt-dlp-<version>/yt_dlp目录
for item in os.listdir(temp_extract_dir):
    item_path = os.path.join(temp_extract_dir, item)
    if os.path.isdir(item_path):
        yt_dlp_path = os.path.join(item_path, "yt_dlp")
        if os.path.exists(yt_dlp_path) and os.path.exists(os.path.join(yt_dlp_path, "version.py")):
            src_path = yt_dlp_path
            break

# 方式2: 递归查找作为备选
if not src_path:
    for root, dirs, files in os.walk(temp_extract_dir):
        if 'version.py' in files and os.path.basename(root) == 'yt_dlp':
            src_path = root
            break
```

### 2. 改进的临时文件清理

```python
# 成功时清理临时文件
if os.path.exists(temp_extract_dir):
    shutil.rmtree(temp_extract_dir)
if os.path.exists(zip_path):
    os.remove(zip_path)

# 异常时清理临时文件
except Exception as e:
    # 清理可能的临时文件
    import glob
    temp_dirs = glob.glob(os.path.join(self.backup_dir, "yt_dlp_temp_*"))
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
```

### 3. 更好的错误消息

```python
# 改进的错误消息，便于故障排除
if not src_path or not os.path.exists(os.path.join(src_path, 'version.py')):
    return False, "下载的文件格式不正确，找不到yt_dlp源目录"
```

## 📝 修改的文件

### `pyMediaTools/core/ytdlp_updater.py`

**改动**：
1. ✅ 增加 `import glob` 
2. ✅ 改进 `update_from_github()` 方法的目录结构处理
3. ✅ 修复临时目录命名问题
4. ✅ 增加两层查找机制（确保能找到yt_dlp目录）
5. ✅ 增加显式的临时文件清理
6. ✅ 改进异常处理中的临时文件清理
7. ✅ 增加详细的调试日志

**代码行数**：
- 从 ~410 行改为 ~513 行
- 增加了 ~100 行用于更好的错误处理和清理

## 🧪 测试方法

运行此命令验证修复：

```bash
cd /Volumes/Ark/shell/pyMediaConvert

# 1. 运行集成测试
python test_ytdlp_version_management.py

# 2. 在UI中测试
python MediaTools.py
# 打开 Video Download 标签页
# 点击"🔄 检查更新"
# 如果有新版本，点击"⬆️ 更新"进行更新
```

## 📊 改进对比

| 方面 | 修复前 | 修复后 |
|------|--------|--------|
| 目录识别 | 依赖特定命名 | 自适应查找 |
| 查找机制 | 单层查找 | 双层查找 |
| 临时文件清理 | 不完整 | 完整，包括异常情况 |
| 错误消息 | 模糊 | 清晰，便于排查 |
| 日志详细度 | 基本 | 详细（调试级) |

## 🔄 更新流程改进

```
下载zip包
    ↓
解压到临时目录 (yt_dlp_temp_*)
    ↓
├─ 方式1: 直接在 yt-dlp-<version> 中查找 yt_dlp 目录
├─ 方式2: 递归查找 yt_dlp 目录（包含version.py)
    ↓
验证 version.py 存在
    ↓
[错误处理] ← 清理临时文件并回滚
    ↓
[成功] ← 替换yt_dlp目录
    ↓
清理临时文件和zip包
```

## 🛡️ 安全性改进

1. ✅ **自动清理** - 成功或失败都会清理临时文件
2. ✅ **异常处理** - 确保异常情况下不会留下垃圾文件
3. ✅ **验证机制** - 双层查找确保文件完整性
4. ✅ **日志追踪** - 详细的调试日志便于排查问题

## 📋 后续建议

1. **缓存验证** - 可以添加zip文件的SHA256校验
2. **网络重试** - 增加下载失败时的自动重试机制
3. **进度反馈** - 在大文件下载时显示进度百分比
4. **离线支持** - 支持本地zip文件的安装

## ✨ 总结

这个修复改进了yt-dlp版本更新的可靠性和容错能力：

- 🎯 **准确性** - 改进的目录查找机制
- 🛡️ **安全性** - 完整的文件清理和异常处理
- 📊 **可维护性** - 更详细的日志和错误消息
- 🚀 **用户体验** - 减少错误发生的可能性

---

**修复时间**: 2025-02-16  
**版本**: 1.1 (Bug Fix)  
**状态**: ✅ 完成测试
