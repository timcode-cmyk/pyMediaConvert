这是一个详细的指南，说明如何使用 PyInstaller 将您的 PySide6 媒体转换器项目打包成一个独立的应用程序（Windows 的 .exe、macOS 的 .app 或 Linux 的可执行文件）。

重要前提： 请确保您已使用上面提供的最新 utils.py 文件，该文件包含了兼容 PyInstaller 打包环境的路径检测逻辑。

第一步：准备工作和安装 PyInstaller

1. 获取真正的 FFmpeg 可执行文件

您的程序依赖 FFmpeg。在打包之前，您需要下载适用于您的目标操作系统的 真正 FFmpeg 和 FFprobe 可执行文件。

下载地址： 访问 FFmpeg 官方网站 或搜索可靠的 FFmpeg 编译版本。

文件放置： 将下载的 ffmpeg 和 ffprobe 可执行文件（例如 ffmpeg.exe 和 ffprobe.exe）复制到您项目根目录下的 bin/ 文件夹中，替换掉之前创建的模拟文件。

2. 安装 PyInstaller

在您的 Python 环境中安装打包工具：

pip install pyinstaller


第二步：执行打包命令

使用 PyInstaller 进行打包，并确保所有依赖项（特别是 FFmpeg 和 assets 文件夹）都被正确包含。

请在项目根目录（qt_media_converter.py 所在的目录）下运行以下命令。

💻 Windows 打包 (生成 .exe)

请将下面的命令作为一个整体复制到命令提示符 (CMD) 或 PowerShell 中运行：

pyinstaller --noconfirm --windowed ^
--name "MediaConverter" ^
--collect-all PySide6 ^
--add-data "assets;assets" ^
--add-binary "bin/ffmpeg.exe;bin" ^
--add-binary "bin/ffprobe.exe;bin" ^
qt_media_converter.py


--windowed: 创建一个不带控制台窗口的 GUI 应用程序。

--add-data "assets;assets": 将 assets 文件夹作为数据文件添加到应用中。

--add-binary "bin/ffmpeg.exe;bin": 将真正的 ffmpeg.exe 可执行文件添加到应用中的 bin 文件夹。

🍎 macOS 或 Linux 打包 (生成 .app 或可执行文件)

在 macOS 和 Linux 上，FFmpeg 可执行文件通常没有 .exe 后缀。请根据您实际的文件名调整。在终端中运行：

pyinstaller --noconfirm --windowed \
--name "MediaConverter" \
--collect-all PySide6 \
--add-data "assets:assets" \
--add-binary "bin/ffmpeg:bin" \
--add-binary "bin/ffprobe:bin" \
qt_media_converter.py


注意： 在 macOS/Linux 上，PyInstaller 的分隔符是 : 而不是 Windows 的 ;。

第三步：查找和测试应用

打包成功后，您会在项目根目录下找到两个新文件夹：build/ 和 dist/。

最终应用位置： 您的最终应用程序位于 dist/MediaConverter 目录下。

Windows: dist/MediaConverter/MediaConverter.exe

macOS: dist/MediaConverter/MediaConverter.app

Linux: dist/MediaConverter/MediaConverter (可执行文件)

测试： 运行生成的应用程序，确保 GUI 正常启动，并且转换功能可以成功调用 ffmpeg（即进度条可以正常工作）。

💡 额外提示：添加应用图标

如果您想为您的应用程序添加一个自定义图标，可以在 PyInstaller 命令中增加 --icon 参数。

Windows: 图标文件必须是 .ico 格式。

--icon="path/to/icon.ico"


macOS: 图标文件必须是 .icns 格式。

--icon="path/to/icon.icns"
