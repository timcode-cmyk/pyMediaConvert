# PySide6 Deployment & Packaging Guide

本文档规范 PySide6 桌面端跨平台打包、分发与构建的最佳实践。

---

## 1. 核心原则
- **清洁隔离环境**：必须在仅安装了该应用运行时依赖的独立 Python 虚拟环境（Virtualenv / Poetry / Conda）中执行打包，绝不可在全局脏环境中打包，以防将无用依赖打包进二进制中造成体积膨胀。
- **同构目标平台打包（Native Target OS）**：由于 Qt 依赖底层 C++ 原生动态链接库（Windows `.dll`、macOS `.dylib` / Framework、Linux `.so`），严禁跨平台交叉编译。请在 macOS 上构建 `.app`/`.dmg`，在 Windows 上构建 `.exe`，在 Linux 上构建 AppImage/deb，或通过 GitHub Actions CI/CD 多平台矩阵自动化构建。

---

## 2. 官方方案：`pyside6-deploy` (基于 Nuitka)

PySide6 6.4+ 官方推荐的轻量部署工具，底层使用 Nuitka 编译生成高性能原生二进制：

```bash
# 生成配置文件与打包
pyside6-deploy main.py
```
它会自动探测应用依赖的 Qt 模块，并生成 `pysidedeploy.spec` 供进一步微调（如应用名称、图标、平台特性）。

---

## 3. 行业通用方案：PyInstaller

PyInstaller 是最成熟、应用最广泛的 Python 桌面应用打包工具。

### 3.1 基础打包命令
```bash
pyinstaller \
  --windowed \
  --onedir \
  --name "pyMediaTools" \
  --icon "assets/app.ico" \
  main.py
```
- `--windowed` (或 `-w`)：关闭命令行控制台黑色黑框（GUI 应用必备）。
- `--onedir`：打包为文件夹形式（启动更快、方便调试丢失的动态库与静态资源；调试完成后可改用 `--onefile` 生成单执行文件）。

### 3.2 静态资源与数据文件挂载（`--add-data`）
对于未编译进 `.qrc` 的额外外部资源（如 `config.toml`、图标素材、字体）：
- **macOS / Linux** 语法（以冒号 `:` 分隔）：
  ```bash
  --add-data "assets:assets" --add-data "config.toml:."
  ```
- **Windows** 语法（以分号 `;` 分隔）：
  ```bash
  --add-data "assets;assets" --add-data "config.toml;."
  ```

### 3.3 运行时资源路径安全访问函数
打包后的临时运行目录在 `sys._MEIPASS`：
```python
import sys
import os

def get_resource_path(relative_path: str) -> str:
    """获取资源在开发环境或 PyInstaller 打包环境下的真实绝对路径"""
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller 打包临时解压目录
        base_path = sys._MEIPASS
    else:
        # 开发时基于项目根目录
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
```

---

## 4. macOS 专属优化（`.app` 与 Codesign）
在 macOS 上发布时：
1. 确保 Info.plist 中声明了高分屏 Retina 支持与权限（摄像头、麦克风等）；
2. 使用 `codesign` 对生成的 `.app` 签名，避免 Gatekeeper 拦截报“应用已损坏”。
