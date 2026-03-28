@echo off
echo Starting PyInstaller build for Windows...

:: Check if PyInstaller is installed
pip install pyinstaller

:: Run PyInstaller
pyinstaller MediaTools.spec --noconfirm

echo PyInstaller build complete. Output in dist/MediaTools
pause
