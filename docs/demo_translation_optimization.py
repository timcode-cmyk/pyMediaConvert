#!/usr/bin/env python3
"""
演示翻译优化：完整句子分段 vs 受限分段

这个脚本展示了 ignore_line_length 参数如何改进翻译准确性
"""

import sys
sys.path.insert(0, '/Users/tim/Documents/shell/pyMediaConvert')

from pyMediaTools.core.subtitle_builder import SubtitleSegmentBuilder


def demo_translation_optimization():
    """演示翻译优化效果"""
    
    print("\n" + "="*70)
    print("翻译准确性优化演示")
    print("="*70)
    
    # 创建测试数据：一个较长的句子
    text = "这是一个很长的中文句子，包含多个概念，需要准确翻译。"
    chars = list(text)
    
    # 创建均匀分布的时间戳
    num_chars = len(chars)
    starts = [i * 0.5 for i in range(num_chars)]
    ends = [(i + 1) * 0.5 for i in range(num_chars)]
    
    print(f"\n📝 输入文本：{text}")
    print(f"📊 字符数：{len(chars)}")
    
    # 配置
    config = {
        'srt_max_chars': 20,  # 显示时的行长度限制
        'srt_sentence_enders': ["。", "！", "？"],
        'srt_pause_threshold': 0.2
    }
    
    builder = SubtitleSegmentBuilder(config=config)
    
    print(f"\n⚙️  配置：")
    print(f"   - srt_max_chars: {config['srt_max_chars']}")
    print(f"   - srt_sentence_enders: {config['srt_sentence_enders']}")
    
    # 显示模式（标准分段）
    print("\n" + "-"*70)
    print("1️⃣  显示模式（标准分段，考虑行长度限制）")
    print("-"*70)
    print("用途：优化显示效果，适合字幕显示")
    print("特点：可能会在行长度限制处分割，导致句子不完整")
    
    display_segments = builder.build_segments(
        chars, starts, ends,
        ignore_line_length=False  # 默认值
    )
    
    print(f"\n生成了 {len(display_segments)} 个片段：")
    for i, seg in enumerate(display_segments, 1):
        print(f"  {i}. [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}")
    
    # 翻译模式（完整句子分段）
    print("\n" + "-"*70)
    print("2️⃣  翻译模式（完整句子分段，忽略行长度限制）")
    print("-"*70)
    print("用途：翻译语句，获得完整的语义单位")
    print("特点：只按标点和停顿分割，保证句子完整")
    
    translation_segments = builder.build_segments(
        chars, starts, ends,
        ignore_line_length=True  # 新参数
    )
    
    print(f"\n生成了 {len(translation_segments)} 个片段：")
    for i, seg in enumerate(translation_segments, 1):
        print(f"  {i}. [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}")
    
    # 对比分析
    print("\n" + "="*70)
    print("对比分析")
    print("="*70)
    
    print(f"\n📊 数据对比：")
    print(f"   显示模式片段数：{len(display_segments)}")
    print(f"   翻译模式片段数：{len(translation_segments)}")
    
    print(f"\n✨ 优化效果：")
    if len(translation_segments) < len(display_segments):
        print(f"   ✓ 翻译模式片段更少，更合适用于翻译")
        print(f"   ✓ 避免了由行长度限制导致的句子分割")
    else:
        print(f"   ✓ 两种模式片段数相同（说明行长度限制未起作用）")
    
    # 验证完整性
    display_text = "".join([seg['text'] for seg in display_segments])
    translation_text = "".join([seg['text'] for seg in translation_segments])
    
    print(f"\n🔍 完整性检查：")
    print(f"   显示模式恢复文本：{display_text}")
    print(f"   翻译模式恢复文本：{translation_text}")
    print(f"   原始文本：      {text}")
    
    if display_text == text and translation_text == text:
        print(f"   ✓ 两种模式都能完整恢复原文本")
    
    return True


def demo_multiple_sentences():
    """演示多句子场景"""
    
    print("\n" + "="*70)
    print("多句子场景演示")
    print("="*70)
    
    text = "第一句话。第二句话很长需要显示优化。第三句。"
    chars = list(text)
    starts = [i * 0.3 for i in range(len(chars))]
    ends = [(i + 1) * 0.3 for i in range(len(chars))]
    
    print(f"\n📝 输入文本：{text}")
    
    config = {
        'srt_max_chars': 15,
        'srt_sentence_enders': ["。"],
        'srt_pause_threshold': 0.2
    }
    
    builder = SubtitleSegmentBuilder(config=config)
    
    print(f"\n⚙️  配置：max_chars_per_line = {config['srt_max_chars']}")
    
    # 显示模式
    display_segments = builder.build_segments(
        chars, starts, ends,
        ignore_line_length=False
    )
    
    print(f"\n📺 显示模式（{len(display_segments)} 个片段）：")
    for i, seg in enumerate(display_segments, 1):
        print(f"   {i}. {seg['text']}")
    
    # 翻译模式
    translation_segments = builder.build_segments(
        chars, starts, ends,
        ignore_line_length=True
    )
    
    print(f"\n🌐 翻译模式（{len(translation_segments)} 个片段）：")
    for i, seg in enumerate(translation_segments, 1):
        print(f"   {i}. {seg['text']}")
    
    return True


def main():
    """运行所有演示"""
    
    try:
        demo_translation_optimization()
        demo_multiple_sentences()
        
        print("\n" + "="*70)
        print("✨ 演示完成！")
        print("="*70)
        print("\n关键要点：")
        print("1. 显示模式：优化视觉效果（考虑行长度）")
        print("2. 翻译模式：优化语义准确性（完整句子）")
        print("3. 通过 ignore_line_length 参数灵活切换")
        print("\n现在翻译会使用完整的句子，提高翻译准确性！")
        
        return 0
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
