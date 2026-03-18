!include "MUI2.nsh"

Name "MediaTools"
OutFile "MediaTools-Installer.exe"
InstallDir "$PROGRAMFILES\MediaTools"
RequestExecutionLevel admin

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "MainSection" SEC01
	SetOutPath "$INSTDIR"
	# 将 Nuitka 生成的整个 dist 目录下的文件放入安装目录
	File /r "dist-nuitka\MediaTools.dist\*"

	# 创建桌面快捷方式
	CreateShortcut "$DESKTOP\MediaTools.lnk" "$INSTDIR\MediaTools.exe"

	# 写入卸载程序
	WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
	Delete "$DESKTOP\MediaTools.lnk"
	RMDir /r "$INSTDIR"
SectionEnd
