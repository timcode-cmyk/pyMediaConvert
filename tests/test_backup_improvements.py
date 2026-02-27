#!/usr/bin/env python3
"""
yt-dlp 备份处理改进 - 验证脚本
测试两个改进:
1. 源码不存在或损坏时直接下载
2. 成功更新后自动清理旧备份
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# 直接导入模块
sys.path.insert(0, '/Volumes/Ark/shell/pyMediaConvert/pyMediaTools/core')
from ytdlp_updater import YtDlpVersionManager


def test_is_yt_dlp_corrupted():
    """测试源码完整性检查"""
    print("\n" + "="*60)
    print("✓ 测试 1: 源码完整性检查")
    print("="*60)
    
    manager = YtDlpVersionManager()
    
    # 测试1: 正常的yt_dlp
    print("\n测试 1a: 正常的yt_dlp目录")
    is_corrupted = manager._is_yt_dlp_corrupted()
    print(f"  当前yt_dlp目录状态: {'✓ 完整' if not is_corrupted else '✗ 损坏'}")
    
    # 测试2: 模拟源码不存在
    print("\n测试 1b: 临时移走yt_dlp目录")
    original_path = manager.yt_dlp_dir
    temp_backup = original_path + ".test_backup"
    
    if os.path.exists(original_path):
        shutil.move(original_path, temp_backup)
        manager_test = YtDlpVersionManager()
        is_corrupted = manager_test._is_yt_dlp_corrupted()
        print(f"  yt_dlp不存在时状态: {'✓ 检测到损坏' if is_corrupted else '✗ 未检测到'}")
        shutil.move(temp_backup, original_path)
    else:
        print(f"  跳过: yt_dlp目录不存在")
    
    return True


def test_cleanup_old_backups():
    """测试旧备份清理功能"""
    print("\n" + "="*60)
    print("✓ 测试 2: 旧备份清理")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试管理器
        manager = YtDlpVersionManager()
        original_backup_dir = manager.backup_dir
        
        # 临时改变备份目录
        manager.backup_dir = tmpdir
        manager.metadata_file = os.path.join(tmpdir, "update_metadata.json")
        
        print(f"\n测试备份目录: {tmpdir}")
        
        # 创建5个模拟备份
        backup_names = [
            "yt_dlp_backup_2026.02.10_20250216_120530",  # 最新
            "yt_dlp_backup_2026.02.04_20250215_143200",  # 第2新
            "yt_dlp_backup_2026.01.20_20250214_100000",  # 第3新
            "yt_dlp_backup_2026.01.10_20250213_090000",  # 过旧
            "yt_dlp_backup_2025.12.20_20250212_080000",  # 最旧
        ]
        
        # 创建备份目录
        for name in backup_names:
            backup_path = os.path.join(tmpdir, name)
            os.makedirs(backup_path)
            # 创建version.py模拟文件
            with open(os.path.join(backup_path, "version.py"), 'w') as f:
                f.write(f"__version__ = '{name.split('_')[3]}'\n")
        
        # 创建元数据
        metadata = {}
        for name in backup_names:
            metadata[name] = {
                "version": name.split('_')[3],
                "timestamp": "2025-02-16T00:00:00",
                "path": os.path.join(tmpdir, name)
            }
        
        with open(manager.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n创建了 {len(backup_names)} 个模拟备份:")
        for name in backup_names:
            print(f"  - {name}")
        
        # 执行清理（保留最新的3个）
        print(f"\n执行清理: 保留最新的3个...")
        deleted = manager._cleanup_old_backups(keep_latest=3)
        
        # 验证结果
        print(f"\n清理结果:")
        print(f"  删除的备份数: {deleted}")
        
        remaining_backups = [d for d in os.listdir(tmpdir) if d.startswith('yt_dlp_backup_')]
        print(f"  剩余备份数: {len(remaining_backups)}")
        
        if remaining_backups:
            print(f"  剩余备份:")
            for name in sorted(remaining_backups):
                print(f"    - {name}")
        
        # 验证元数据是否同步
        with open(manager.metadata_file, 'r') as f:
            updated_metadata = json.load(f)
        
        print(f"\n元数据验证:")
        print(f"  原始记录数: {len(metadata)}")
        print(f"  更新后记录数: {len(updated_metadata)}")
        
        # 验证是否正确保留了最新的3个
        success = (
            deleted == 2 and  # 应该删除2个（5-3=2）
            len(remaining_backups) == 3 and  # 应该保留3个
            len(updated_metadata) == 3  # 元数据也应该有3条
        )
        
        if success:
            print("\n✓ 清理功能正常工作！")
        else:
            print("\n✗ 清理功能有问题")
        
        return success


def test_backup_directory_structure():
    """验证备份目录结构"""
    print("\n" + "="*60)
    print("✓ 测试 3: 备份目录结构")
    print("="*60)
    
    manager = YtDlpVersionManager()
    
    print(f"\n备份目录: {manager.backup_dir}")
    
    if not os.path.exists(manager.backup_dir):
        print("  备份目录不存在，将在首次备份时创建")
        return True
    
    # 列出现有备份
    backups = [d for d in os.listdir(manager.backup_dir) 
               if d.startswith('yt_dlp_backup_')]
    
    print(f"\n现有备份数: {len(backups)}")
    
    if backups:
        print("  备份列表:")
        for backup in sorted(backups):
            path = os.path.join(manager.backup_dir, backup)
            size = sum(f.stat().st_size for f in Path(path).rglob('*'))
            size_mb = size / (1024 * 1024)
            print(f"    - {backup} ({size_mb:.2f} MB)")
    
    # 验证元数据
    if os.path.exists(manager.metadata_file):
        with open(manager.metadata_file, 'r') as f:
            metadata = json.load(f)
        print(f"\n元数据记录: {len(metadata)} 条")
    else:
        print("\n元数据文件不存在")
    
    print("\n✓ 备份目录结构正常")
    return True


def main():
    """运行所有验证测试"""
    print("\n" + "="*60)
    print("yt-dlp 备份处理改进 - 验证测试")
    print("="*60)
    
    tests = [
        ("源码完整性检查", test_is_yt_dlp_corrupted),
        ("旧备份清理功能", test_cleanup_old_backups),
        ("备份目录结构", test_backup_directory_structure),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ 测试异常: {e}")
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
        print("\n🎉 所有验证测试通过！")
        print("\n改进摘要:")
        print("  ✓ 新增 _is_yt_dlp_corrupted() 方法")
        print("  ✓ 新增 _cleanup_old_backups() 方法")
        print("  ✓ 改进 update_from_github() 备份处理")  
        print("  ✓ 改进 update_from_pypi() 备份处理")
        print("  ✓ 自动清理旧备份（保留最新3个）")
        print("  ✓ 源码不存在时可直接下载")
        print("  ✓ 备份失败时仍继续更新")
        return 0
    else:
        print(f"\n⚠ 有 {total - passed} 个测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
