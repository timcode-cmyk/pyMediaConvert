!include "MUI2.nsh"

Name "MediaTools"

# 接收从 GitHub Actions 传入的文件名
!ifndef OUTFILE
	OutFile "MediaTools-Default-Setup.exe"
!else
	OutFile "${OUTFILE}"
!endif

# --- 关键修改：安装到用户本地应用数据目录 ---
InstallDir "$LOCALAPPDATA\MediaTools"

# --- 关键修改：请求普通用户权限，不再弹出 UAC 盾牌 ---
RequestExecutionLevel user

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "MainSection" SEC01
	SetOutPath "$INSTDIR"

	# 将 Nuitka 生成的整个 dist 目录下的文件放入安装目录
	# 确保 GitHub Actions 中的路径与此一致
	File /r "dist-nuitka\MediaTools.dist\*"

	# 创建桌面快捷方式 (安装到当前用户的桌面)
	CreateShortcut "$DESKTOP\MediaTools.lnk" "$INSTDIR\MediaTools.exe"

	# 写入卸载程序
	WriteUninstaller "$INSTDIR\uninstall.exe"

	# 可选：写入注册表以便在“添加/删除程序”中显示（用户权限级别）
	WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MediaTools" "DisplayName" "MediaTools"
	WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MediaTools" "UninstallString" "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
	# 删除快捷方式
	Delete "$DESKTOP\MediaTools.lnk"

	# 删除安装目录
	RMDir /r "$INSTDIR"

	# 删除注册表信息
	DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MediaTools"
SectionEnd
