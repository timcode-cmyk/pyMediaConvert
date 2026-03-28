#!/bin/bash
set -e

echo "Starting PyInstaller build for macOS..."

# Install PyInstaller if not present
pip install pyinstaller

# Run PyInstaller
pyinstaller MediaTools.spec --noconfirm

echo "PyInstaller build complete. Output in dist/MediaTools.app"
