#!/usr/bin/env python3
"""
yt-dlp 版本管理 - 简化的测试脚本（无PySide6依赖)
"""

import sys
import os
import logging

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 直接导入（避免PySide6的依赖)
import urllib.request
import json
from pyMediaTools.core.ytdlp_updater import VersionComparator, YtDlpVersionManager


def test_version_comparator():
    """测试版本比较工具"""
    print("\n" + "="*60)
    print("✓ 测试 1: 版本比较工具")
    print("="*60)
    
    test_cases = [
        ("2026.02.04", "2026.02.03", True),
        ("2026.02.03", "2026.02.04", False),
        ("2026.02.04", "2026.02.04", False),
    ]
    
    passed = 0
    for v1, v2, expected in test_cases:
        result = VersionComparator.is_newer(v1, v2)
        status = "✓" if result == expected else "✗"
        print(f"  {status} is_newer('{v1}', '{v2}') = {result}")
        if result == expected:
            passed += 1
    
    print(f"\n  通过: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_get_local_version():
    """测试获取本地版本"""
    print("\n" + "="*60)
    print("✓ 测试 2: 获取本地版本")
    print("="*60)
    
    manager = YtDlpVersionManager()
    version = manager.get_local_version()
    
    print(f"  本地版本: {version}")
    success = version is not None and len(version) > 0
    
    if success:
        print("  ✓ 成功获取本地版本")
    else:
        print("  ✗ 无法获取本地版本")
    
    return success


def test_version_file():
    """测试版本文件内容"""
    print("\n" + "="*60)
    print("✓ 测试 3: 验证版本文件")
    print("="*60)
    
    version_file = os.path.join(project_root, "yt_dlp", "version.py")
    
    if not os.path.exists(version_file):
        print(f"  ✗ 版本文件不存在: {version_file}")
        return False
    
    print(f"  ✓ 版本文件存在: {version_file}")
    
    # 读取文件内容
    with open(version_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查__version__变量
    if '__version__' not in content:
        print("  ✗ 未找到__version__变量")
        return False
    
    print("  ✓ 找到__version__变量")
    
    # 提取版本号
    for line in content.split('\n'):
        if line.startswith('__version__'):
            print(f"  内容: {line.strip()}")
            break
    
    return True


def test_backup_structure():
    """测试备份目录结构"""
    print("\n" + "="*60)
    print("✓ 测试 4: 备份目录结构")
    print("="*60)
    
    manager = YtDlpVersionManager()
    
    print(f"  yt_dlp目录: {manager.yt_dlp_dir}")
    print(f"  备份目录: {manager.backup_dir}")
    
    # 检查yt_dlp目录
    if not os.path.exists(manager.yt_dlp_dir):
        print(f"  ✗ yt_dlp目录不存在")
        return False
    
    print(f"  ✓ yt_dlp目录存在")
    
    # 检查备份目录是否存在或可创建
    try:
        os.makedirs(manager.backup_dir, exist_ok=True)
        print(f"  ✓ 备份目录可用")
    except Exception as e:
        print(f"  ✗ 备份目录错误: {e}")
        return False
    
    return True


def test_remote_version_github():
    """测试从GitHub获取版本"""
    print("\n" + "="*60)
    print("✓ 测试 5: 从GitHub获取版本 (网络测试)")
    print("="*60)
    
    # 注意：这个测试需要网络连接
    manager = YtDlpVersionManager()
    
    print("  正在从GitHub API获取最新版本...")
    try:
        version = manager.get_remote_version_from_github(timeout=5)
        
        if version:
            print(f"  ✓ 成功获取: {version}")
            return True
        else:
            print(f"  ⚠ 无法获取版本（可能是网络问题）")
            return False
            
    except Exception as e:
        print(f"  ⚠ 错误 (可能是网络问题): {e}")
        return False


def test_update_mechanism():
    """测试更新机制的逻辑"""
    print("\n" + "="*60)
    print("✓ 测试 6: 更新机制逻辑验证")
    print("="*60)
    
    manager = YtDlpVersionManager()
    local_version = manager.get_local_version()
    
    print(f"  本地版本: {local_version}")
    
    # 测试假设版本对比
    test_versions = [
        (local_version, "2025.01.01", True),  # 本地版本更新
        (local_version, "2030.12.31", False),  # 远程版本更新
    ]
    
    all_passed = True
    for local, remote, local_newer in test_versions:
        result = VersionComparator.is_newer(remote, local)
        status = "✓" if result == (not local_newer) else "✗"
        print(f"  {status} 远程{remote}比本地{local}新: {result}")
        if result != (not local_newer):
            all_passed = False
    
    return all_passed


def test_directory_structure():
    """测试GitHub zip解压的目录结构识别"""
    print("\n" + "="*60)
    print("✓ 测试 7: 目录结构识别逻辑")
    print("="*60)
    
    # 创建测试目录结构
    import tempfile
    import shutil
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 模拟GitHub zip的目录结构: yt-dlp-<version>/yt_dlp/
        root_dir = os.path.join(tmpdir, "yt-dlp-2026.02.10")
        yt_dlp_dir = os.path.join(root_dir, "yt_dlp")
        os.makedirs(yt_dlp_dir)
        
        # 创建版本文件
        version_file = os.path.join(yt_dlp_dir, "version.py")
        with open(version_file, 'w') as f:
            f.write("__version__ = '2026.02.10'\n")
        
        print(f"  创建测试目录: {root_dir}")
        print(f"  创建版本文件: {version_file}")
        
        # 测试查找逻辑
        src_path = None
        
        # 方式1：直接查找
        for item in os.listdir(tmpdir):
            item_path = os.path.join(tmpdir, item)
            if os.path.isdir(item_path):
                yt_dlp_path = os.path.join(item_path, "yt_dlp")
                if os.path.exists(yt_dlp_path) and os.path.exists(os.path.join(yt_dlp_path, "version.py")):
                    src_path = yt_dlp_path
                    break
        
        if src_path:
            print(f"  ✓ 成功找到yt_dlp目录: {src_path}")
            return True
        else:
            print(f"  ✗ 未找到yt_dlp目录")
            return False


def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  yt-dlp 版本管理 - 简化测试".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    tests = [
        ("版本比较工具", test_version_comparator),
        ("本地版本", test_get_local_version),
        ("版本文件", test_version_file),
        ("备份结构", test_backup_structure),
        ("GitHub获取", test_remote_version_github),
        ("更新逻辑", test_update_mechanism),
        ("目录识别", test_directory_structure),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n  ✗ 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 汇总
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓" if result else "✗"
        print(f"  {status} {name}")
    
    print(f"\n总体: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有基础测试通过！")
        print("\n修复验证: ✅ 版本管理系统功能正常")
        return 0
    else:
        print(f"\n⚠ 有 {total - passed} 个测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
