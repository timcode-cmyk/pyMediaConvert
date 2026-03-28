python -m nuitka --standalone --macos-app-icon=Icon.icns --assume-yes-for-downloads --macos-create-app-bundle --output-dir=dist-nuitka \
          --macos-app-version=__version__ \
          --nofollow-import-to=yt_dlp --no-deployment-flag=excluded-module-usage \
          --include-module=optparse --include-module=asyncio --include-package=pyMediaTools \
          --plugin-enable=pyside6 --include-qt-plugins=multimedia,platforms,styles,imageformats \
          --include-data-files=bin/ffmpeg=bin/ffmpeg --include-data-files=bin/ffprobe=bin/ffprobe \
          --include-data-files=config.toml=config.toml --include-data-dir=assets=assets MediaTools.py