"""
yt-dlp 版本管理和更新 - 集成测试和使用示例

这个脚本展示了如何使用 YtDlpVersionManager 和相关功能。
"""

import os
import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pyMediaTools.core.ytdlp_updater import YtDlpVersionManager, YtDlpUpdater, VersionComparator


def test_version_comparator():
    """测试版本比较工具"""
    print("\n" + "="*60)
    print("测试 1: 版本比较工具")
    print("="*60)
    
    comparator = VersionComparator()
    
    test_cases = [
        ("2026.02.04", "2026.02.03", True),   # 2026.02.04 > 2026.02.03
        ("2026.02.03", "2026.02.04", False),  # 2026.02.03 < 2026.02.04
        ("2026.02.04", "2026.02.04", False),  # 相同版本
        ("2025.01.01", "2026.01.01", False),  # 较早版本
    ]
    
    for v1, v2, expected_newer in test_cases:
        result = comparator.is_newer(v1, v2)
        status = "✓" if result == expected_newer else "✗"
        print(f"{status} is_newer('{v1}', '{v2}') = {result} (期望: {expected_newer})")


def test_get_local_version():
    """测试获取本地版本"""
    print("\n" + "="*60)
    print("测试 2: 获取本地版本")
    print("="*60)
    
    manager = YtDlpVersionManager()
    version = manager.get_local_version()
    print(f"本地 yt-dlp 版本: {version}")
    if version:
        print("✓ 成功获取本地版本")
    else:
        print("✗ 无法获取本地版本")


def test_get_remote_version():
    """测试获取远程版本"""
    print("\n" + "="*60)
    print("测试 3: 获取远程版本（GitHub）")
    print("="*60)
    
    manager = YtDlpVersionManager()
    print("正在从 GitHub 获取最新版本...")
    
    try:
        version = manager.get_remote_version_from_github(timeout=10)
        if version:
            print(f"✓ GitHub 最新版本: {version}")
        else:
            print("✗ 无法从 GitHub 获取版本")
    except Exception as e:
        print(f"✗ 错误: {e}")
    
    print("\n正在从 PyPI 获取最新版本...")
    try:
        version = manager.get_remote_version_from_pypi(timeout=10)
        if version:
            print(f"✓ PyPI 最新版本: {version}")
        else:
            print("✗ 无法从 PyPI 获取版本")
    except Exception as e:
        print(f"✗ 错误: {e}")


def test_check_update():
    """测试检查更新"""
    print("\n" + "="*60)
    print("测试 4: 检查更新")
    print("="*60)
    
    manager = YtDlpVersionManager()
    
    print("正在检查更新...")
    has_update, local_version, remote_version = manager.check_update_available(timeout=10)
    
    print(f"本地版本: {local_version}")
    print(f"远程版本: {remote_version}")
    print(f"有更新: {has_update}")
    
    if has_update:
        print(f"✓ 发现新版本 {remote_version} (当前: {local_version})")
    elif local_version and remote_version:
        print(f"✓ 已是最新版本 {local_version}")
    else:
        print("✗ 无法确定版本状态")


def test_backup_and_rollback():
    """测试备份和回滚"""
    print("\n" + "="*60)
    print("测试 5: 备份和回滚")
    print("="*60)
    
    manager = YtDlpVersionManager()
    
    # 创建备份
    print("正在创建备份...")
    backup_path = manager.backup_current()
    if backup_path:
        print(f"✓ 备份成功: {backup_path}")
    else:
        print("✗ 备份失败")
        return
    
    # 获取最新备份
    print("\n正在获取最新备份...")
    latest_backup = manager.get_latest_backup()
    if latest_backup:
        print(f"✓ 最新备份: {latest_backup}")
    else:
        print("✗ 无法获取备份")


def test_get_release_info():
    """测试获取发布信息"""
    print("\n" + "="*60)
    print("测试 6: 获取发布信息")
    print("="*60)
    
    manager = YtDlpVersionManager()
    
    # 尝试获取最新版本的发布信息
    remote_version = manager.get_remote_version_from_github()
    if remote_version:
        print(f"正在获取版本 {remote_version} 的发布信息...")
        info = manager.get_release_info(remote_version)
        
        if info:
            print(f"✓ 发布时间: {info.get('published_at')}")
            print(f"✓ 发布页面: {info.get('download_url')}")
            
            # 显示更新说明（截断为最多500字符）
            body = info.get('body', '')
            if body:
                preview = body[:500] + '...' if len(body) > 500 else body
                print(f"\n更新说明预览:\n{preview}")
        else:
            print("✗ 无法获取发布信息")
    else:
        print("✗ 无法获取远程版本")


def print_project_structure():
    """打印项目结构"""
    print("\n" + "="*60)
    print("项目结构")
    print("="*60)
    
    structure = """
pyMediaConvert/
├── pyMediaTools/
│   ├── core/
│   │   ├── ytdlp_updater.py          ← 版本管理核心模块
│   │   ├── ytdlp_update_worker.py     ← 异步更新Worker
│   │   └── videodownloader.py         ← 下载核心
│   └── ui/
│       └── video_downloader_ui.py     ← 增强的UI（添加版本管理）
└── yt_dlp/
    ├── version.py                      ← 版本文件
    └── ...                             ← 其他源代码
"""
    print(structure)


def test_comprehensive():
    """综合性测试"""
    print("\n" + "="*60)
    print("综合测试流程")
    print("="*60)
    
    manager = YtDlpVersionManager()
    
    # 步骤 1: 获取本地版本
    print("\n步骤 1: 获取本地版本")
    local_version = manager.get_local_version()
    print(f"  本地版本: {local_version}")
    
    if not local_version:
        print("✗ 无法获取本地版本，无法继续测试")
        return
    
    # 步骤 2: 检查更新
    print("\n步骤 2: 检查更新")
    has_update, _, remote_version = manager.check_update_available(timeout=10)
    print(f"  本地版本: {local_version}")
    print(f"  远程版本: {remote_version}")
    print(f"  有新版本: {has_update}")
    
    # 步骤 3: 备份
    print("\n步骤 3: 创建备份")
    backup_path = manager.backup_current()
    print(f"  备份路径: {backup_path}")
    
    if backup_path and os.path.exists(backup_path):
        print("✓ 备份成功")
    else:
        print("✗ 备份失败或路径不存在")
    
    # 步骤 4: 显示更新建议
    print("\n步骤 4: 更新建议")
    if has_update and remote_version:
        print(f"✓ 建议更新到版本 {remote_version}")
        print("  可以调用 YtDlpUpdater.update_from_github() 执行更新")
    else:
        print("✓ 当前版本已是最新或无法确定")


def main():
    """主测试函数"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  yt-dlp 版本管理系统 - 集成测试".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    # 打印项目结构
    print_project_structure()
    
    # 运行测试
    try:
        test_version_comparator()
        test_get_local_version()
        test_get_remote_version()
        test_check_update()
        test_backup_and_rollback()
        test_get_release_info()
        test_comprehensive()
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print(f"\n\n测试异常: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
