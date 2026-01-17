# TTSWorker 重构 - 快速参考指南

## 🎯 一句话总结
从 450+ 行的单体类拆分为 4 个专业的工具类，将 TTSWorker 简化为 110 行的协调器。

## 📦 新的类结构

```python
# 导入新工具类
from pyMediaTools.core.subtitle_writer import SubtitleWriter
from pyMediaTools.core.subtitle_builder import SubtitleSegmentBuilder
from pyMediaTools.core.translation_manager import TranslationManager
from pyMediaTools.core.cjk_tokenizer import CJKTokenizer

# TTSWorker 现在只有 2 个方法
class TTSWorker(QThread):
    def run(self):
        """调用 ElevenLabs API"""
        
    def process_response(self, resp_json):
        """协调所有工具类处理响应"""
```

## 🔧 各工具类职责

| 类 | 文件 | 职责 | 核心方法 |
|---|------|------|---------|
| SubtitleWriter | subtitle_writer.py | SRT 文件写入 | `write_srt()` |
| SubtitleSegmentBuilder | subtitle_builder.py | 字幕分割 | `build_segments()` |
| CJKTokenizer | cjk_tokenizer.py | 文本分词 | `tokenize_by_cjk()` |
| TranslationManager | translation_manager.py | 翻译服务 | `translate_segments()` |

## 📋 使用示例

### 1. 标准字幕生成
```python
from pyMediaTools.core.subtitle_builder import SubtitleSegmentBuilder
from pyMediaTools.core.subtitle_writer import SubtitleWriter

# 准备数据
chars = ['你', '好', '。']
starts = [0.0, 0.5, 1.0]
ends = [0.5, 1.0, 1.5]

# 生成分段
builder = SubtitleSegmentBuilder()
segments = builder.build_segments(chars, starts, ends)

# 写入文件
SubtitleWriter.write_srt("output.srt", segments)
```

### 2. 逐词字幕
```python
# 使用 word_level=True
segments = builder.build_segments(
    chars, starts, ends, 
    word_level=True, 
    words_per_line=5
)
SubtitleWriter.write_srt("output_word.srt", segments)
```

### 3. 翻译字幕
```python
from pyMediaTools.core.translation_manager import TranslationManager

# 初始化翻译器
translator = TranslationManager(
    api_key="your-groq-key",
    model="llama3-8b-8192"
)

# 翻译分段
translated = translator.translate_segments(segments)

# 写入翻译版本
SubtitleWriter.write_srt("output_cn.srt", translated)
```

### 4. CJK 分词
```python
from pyMediaTools.core.cjk_tokenizer import CJKTokenizer

tokenizer = CJKTokenizer()

# 检测 CJK 字符
is_cjk = tokenizer.is_cjk('中')  # True

# 分词
words = tokenizer.tokenize_by_cjk(chars, starts, ends)
```

## ✨ 改进前后对比

### 调用方式（无变化）
```python
# 仍然这样使用 TTSWorker
worker = TTSWorker(
    api_key="key",
    voice_id="voice",
    text="text",
    save_path="output.mp3",
    translate=True,
    word_level=True
)
worker.start()
```

### 内部实现（完全改进）

**改进前**:
```
process_response()
  ├─ 解码音频
  ├─ create_srt(word_level=False)  # 180 行混乱的分割逻辑
  ├─ create_srt(word_level=True)   # 重复的分割逻辑
  ├─ generate_translated_srt()     # 重复的分割逻辑 + 翻译
  │   └─ _translate_with_groq()
  └─ XML 导出
```

**改进后**:
```
process_response()
  ├─ 解码音频
  ├─ SubtitleSegmentBuilder.build_segments()  # 专业分割
  │   └─ CJKTokenizer (按需)
  ├─ SubtitleWriter.write_srt()  # 统一写入
  ├─ TranslationManager.translate_segments()  # 专业翻译
  │   └─ SubtitleWriter.write_srt()
  └─ XML 导出
```

## 🧪 验证清单

- [ ] 导入成功: `from pyMediaTools.core.elevenlabs import TTSWorker`
- [ ] 旧方法已删除: `hasattr(worker, 'create_srt')` → False
- [ ] 新工具类可用: `from pyMediaTools.core.subtitle_writer import SubtitleWriter`
- [ ] 运行测试: `python3 test_ttsworker_refactor.py`
- [ ] UI 测试: 启动 GUI 并完整测试工作流

## 🔄 迁移指南

### 如果你有自定义代码调用 TTSWorker

❌ **不要这样做（旧方式，已删除）**:
```python
worker.create_srt(alignment, "output.srt")
worker.generate_translated_srt(alignment, "output_cn.srt")
```

✅ **应该这样（新方式，自动处理）**:
```python
# 现在在 TTSWorker 初始化时配置
worker = TTSWorker(
    ...,
    translate=True,  # 自动翻译
    word_level=True  # 自动生成逐词版本
)
```

如果需要手动调用：
```python
from pyMediaTools.core.subtitle_builder import SubtitleSegmentBuilder
from pyMediaTools.core.subtitle_writer import SubtitleWriter

builder = SubtitleSegmentBuilder()
segments = builder.build_segments(chars, starts, ends)
SubtitleWriter.write_srt("output.srt", segments)
```

## 📈 性能数据

| 指标 | 改进 |
|------|------|
| 代码行数 | 658 → 317 (-52%) |
| TTSWorker 行数 | ~450 → ~110 (-75%) |
| 圈复杂度 | 8+ → ~2 (-75%) |
| 方法数 | 5 → 2 (-60%) |

## ⚡ 核心改进

1. **可测试性**: 每个工具类都可以独立测试
2. **可维护性**: 代码职责清晰，易于理解
3. **可扩展性**: 添加新功能只需创建新工具类
4. **可复用性**: 工具类可在其他地方使用
5. **性能**: 零开销，直接委托调用

## 🎓 学习资源

- 查看 `REFACTOR_SUMMARY.md` 了解详细的架构说明
- 查看 `REFACTOR_CHECKLIST.md` 了解完整的重构清单
- 运行 `test_ttsworker_refactor.py` 查看实际测试

---

**建议**: 如果你需要快速上手，只需了解：
1. TTSWorker 的公共 API 没有变化
2. 内部通过工具类优雅地处理复杂逻辑
3. 如果需要自定义，使用相应的工具类而不是直接修改 TTSWorker
