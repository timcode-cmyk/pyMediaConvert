@echo off
setlocal enabledelayedexpansion
title MediaTools 智能环境构建与打包工具
color 0E

echo ==========================================
echo       MediaTools 自动化环境检查与打包
echo ==========================================

:: 1. 清理旧产物
echo [1/5] 清理旧目录...
if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"

:: 2. 检查 Python 与 虚拟环境 (.venv)
echo [2/5] 检查 Python 环境...

if exist ".venv\Scripts\activate.bat" (
    echo [状态] 检测到现有的虚拟环境，正在激活...
    call .venv\Scripts\activate.bat
) else (
    echo [状态] 未检测到 .venv 虚拟环境。
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        echo [动作] 检测到系统 Python，正在创建 .venv...
        python -m venv .venv
        call .venv\Scripts\activate.bat
        echo [动作] 安装必要依赖...
        pip install --upgrade pip
        if exist "requirements.txt" (pip install -r requirements.txt)
        pip install pyinstaller
    ) else (
        echo [警告] 系统未安装 Python！尝试通过 winget 安装 PyInstaller 环境...
        :: 注意：winget 直接装 pyinstaller 并不常见，通常是装 python
        winget install -e --id Python.Python.3.11 --silent
        echo [提示] Python 已安装，请重新运行此脚本以初始化虚拟环境。
        pause
        exit
    )
)

:: 3. 拉取最新源码
echo [3/5] 正在同步 Git 源码...
git pull
if %errorlevel% neq 0 (
    echo [错误] Git 同步失败。
    pause
    exit /b
)

:: 4. 再次确保 PyInstaller 可用
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [动作] 虚拟环境中缺失 PyInstaller，正在安装...
    pip install pyinstaller
)

:: 5. 执行打包
echo [4/5] 开始执行 PyInstaller 打包...
:: 使用 --confirm-external-binders 和 --noconfirm 确保全自动
pyinstaller --noconfirm MediaTools.spec

:: 结果处理
if %errorlevel% eq 0 (
    echo ==========================================
    echo [成功] 打包完成！输出目录: \dist
    echo ==========================================
) else (
    echo [失败] 打包过程中遇到错误。
)

:: 如果是在虚拟环境中，最后退出环境
if defined VIRTUAL_ENV call deactivate
pause