@echo off
title MediaTools 一键更新并清理打包工具
color 0A

echo ==========================================
echo       正在初始化：清理、更新并开始打包
echo ==========================================

:: 1. 清理旧的编译产物
echo [步骤 1/4] 正在清空旧的 dist 和 build 目录...
:: /s 表示删除子目录，/q 表示安静模式（不询问确认）
if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"
echo 清理完成。

:: 2. 拉取最新代码
echo [步骤 2/4] 正在从 Git 拉取最新源码...
git pull
if %errorlevel% neq 0 (
    echo [错误] Git 拉取失败，请检查网络或本地冲突。
    pause
    exit /b
)

:: 3. 检查并执行打包
echo [步骤 3/4] 正在执行打包程序...
:: --noconfirm: 核心参数，遇到已存在文件或覆盖提示时自动确认
pyinstaller --noconfirm MediaTools.spec

:: 4. 结果验证
if %errorlevel% eq 0 (
    echo.
    echo ==========================================
    echo [成功] 打包任务已完成！
    echo 产物位置: %cd%\dist
    echo ==========================================
) else (
    echo.
    echo [错误] 打包过程中出现异常，请向上滚动查看详细报错。
)

pause