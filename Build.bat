@echo off
title MediaTools 一键更新并打包工具
color 0B

echo ==========================================
echo       正在开始更新源码并打包进程
echo ==========================================

:: 1. 拉取最新代码
echo [步骤 1/3] 正在从 Git 拉取最新源码...
git pull
if %errorlevel% neq 0 (
    echo [错误] Git 拉取失败，请检查网络或冲突。
    pause
    exit /b
)

:: 2. 检查 PyInstaller 是否安装
echo [步骤 2/3] 正在检查打包环境...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 未检测到 PyInstaller，正在尝试安装...
    pip install pyinstaller
)

:: 3. 执行打包命令
echo [步骤 3/3] 正在使用 MediaTools.spec 执行打包...
pyinstaller MediaTools.spec --noconfirm

:: 结果判断
if %errorlevel% eq 0 (
    echo.
    echo ==========================================
    echo       恭喜！打包任务已成功完成。
    echo       请在 dist 目录下查看生成的程序。
    echo ==========================================
) else (
    echo.
    echo [错误] 打包过程中出现问题，请检查上方日志。
)

pause