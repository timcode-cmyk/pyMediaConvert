nuitka --standalone --windows-console-mode=disable --assume-yes-for-downloads --output-dir=dist-nuitka `
          --windows-icon-from-ico=MediaTools.ico `
          --nofollow-import-to=yt_dlp --no-deployment-flag=excluded-module-usage `
          --include-module=optparse --include-module=asyncio --include-package=pyMediaTools `
          --plugin-enable=pyside6 --include-qt-plugins=multimedia,platforms,styles,imageformats `
          --include-data-files=MediaTools.ico=MediaTools.ico --include-data-files=bin/ffmpeg.exe=bin/ffmpeg.exe `
          --include-data-files=bin/ffprobe.exe=bin/ffprobe.exe --include-data-files=config.toml=config.toml `
          --include-data-dir=assets=assets MediaTools.py