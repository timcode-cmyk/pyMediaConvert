@echo off
:: Nuitka build script for Windows
:: Parameters are now extracted to MediaTools.py (Project Options) and nuitka_config.yml
python -m nuitka MediaTools.py
pause