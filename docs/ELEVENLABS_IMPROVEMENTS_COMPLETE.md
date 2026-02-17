# ElevenLabs 改进实施总结

**日期**: 2026年2月16日  
**改进内容**: V2/V2.5/V3 模型选择、语言代码设置、情绪标签选项

---

## 📋 实施内容清单

### ✅ Core 层修改 (pyMediaTools/core/elevenlabs.py)

#### 1. 新增常量定义

```python
# 模型定义
ELEVENLABS_MODELS = {
    'eleven_multilingual_v2': {...},      # 多语言V2（默认推荐）
    'eleven_english_v2': {...},           # 英文V2
    'eleven_turbo_v2_5': {...},           # Turbo快速模型
    'eleven_english_v1': {...},           # 英文V1（存档）
}

# 语言代码（30+种语言）
LANGUAGE_CODES = {
    '中文（简体）': 'zh-CN',
    '英文（美国）': 'en-US',
    '日文': 'ja-JP',
    ...
}

# 情绪标签（6种）
EMOTION_OPTIONS = {
    'neutral': '中立、理性',
    'cheerful': '欢快、积极',
    'sad': '悲伤、低沉',
    'fearful': '害怕、紧张',
    'angry': '愤怒、严肃',
    'hopeful': '希望、期待',
}
```

#### 2. TTSWorker 扩展

**构造函数新增参数**:
- `model_id`: 模型选择（默认: eleven_multilingual_v2）
- `language_code`: 语言代码（默认: 从配置读取或autom）
- `emotion`: 情绪标签（默认: None）

**API 调用优化**:
- 支持动态模型选择（不再硬编码）
- 条件性添加 `language_code` 参数
- 条件性添加 `emotion` 参数到 `voice_settings`
- 更好的日志记录

```python
# 现在支持这样的API请求
data = {
    "text": self.text,
    "model_id": "eleven_turbo_v2_5",         # 可选择
    "language_code": "zh-CN",                # 条件添加
    "voice_settings": {
        ...
        "emotion": "cheerful"                # 条件添加
    },
    ...
}
```

---

### ✅ UI 层修改 (pyMediaTools/ui/elevenlabs_ui.py)

#### 1. TTS 操作区枠新增控件

在声音选择下方添加了新的配置行：

```
┌─────────────────────────────────────────────────────────┐
│ 模型: [eleven_multilingual_v2 ▼]  语言: [中文（简体）▼] │
│ 情绪: [默认（无特定情绪）▼]                              │
└─────────────────────────────────────────────────────────┘
```

**新增 UI 组件**:
- `self.combo_model`: 模型选择下拉框（4个推荐模型）
- `self.combo_language`: 语言代码选择下拉框（30+语言）
- `self.combo_emotion`: 情绪标签选择下拉框（6个情绪+默认）

#### 2. VoiceSettingsDialog 扩展

新增情绪标签选择框：

```
调整语音生成参数
━━━━━━━━━━━━━━━━━━━━━━━━━━━
稳定性:     [◆─────────────] 50%
相似度提升: [◆─────────────] 75%
风格:       [◆─────────────] 0%
速度:       [◆─────────────] 1.00
━━━━━━━━━━━━━━━━━━━━━━━━━━━
情绪标签: [😊 欢快 - 积极、开朗、充满能量 ▼]
━━━━━━━━━━━━━━━━━━━━━━━━━━━
☑ 扬声器增强
```

**改进**:
- `get_settings()` 现在返回 emotion 参数
- `set_settings()` 支持恢复 emotion 设置
- 情绪标签显示 emoji + 描述文本

#### 3. TTS 生成流程优化

更新 `generate_tts_audio()` 方法：

```python
# 获取UI中的新参数
model_id = self.combo_model.currentData()
language_code = self.combo_language.currentData()
emotion = self.combo_emotion.currentData()

# 传递给TTSWorker
self.tts_worker = TTSWorker(
    ...
    model_id=model_id,
    language_code=language_code,
    emotion=emotion
)
```

---

### ✅ 配置文件修改 (config.toml)

在 `[elevenlabs]` 部分新增配置项：

```toml
[elevenlabs]
api_key = ""
default_output_format = "mp3_44100_128"

# ⭐ 新增的配置项
default_model_id = "eleven_multilingual_v2"
default_language_code = "zh-CN"
default_emotion = ""

# ... 其他配置项保持不变
```

**说明**:
- `default_model_id`: 应用默认使用的模型
- `default_language_code`: 文本输入语言（留空自动检测）
- `default_emotion`: 默认情绪标签（留空则无特定情绪）

---

## 🎯 功能特性对比

| 特性 | 改进前 | 改进后 |
|------|--------|--------|
| 模型选择 | 固定 `eleven_multilingual_v2` | ✅ 支持 4+ 推荐模型 |
| 语言指定 | 自动检测 | ✅ 显式选择 30+ 语言 |
| 情绪控制 | 无 | ✅ 6 种情绪标签 + 默认 |
| 参数传递 | TTSWorker 不支持 | ✅ 完整支持 |
| API 调用 | 固定参数 | ✅ 灵活组合 |
| 日志记录 | 基础 | ✅ 详细的参数日志 |

---

## 📝 使用指南

### 基础用法

1. **选择模型**
   - 打开应用 → TTS 选项卡
   - 在"模型"下拉框选择需要的模型
   - 默认使用 "多语言 V2"（推荐）

2. **设置语言**
   - 在"语言"下拉框选择输入文本的语言
   - 默认为 "中文（简体）"
   - 选择 "自动检测" 让 API 自动识别

3. **应用情绪**
   - 点击 "⚙️ 语音设定" 按钮
   - 在对话框中选择"情绪标签"
   - 可选：cheerful（欢快）、sad（悲伤）、angry（愤怒）等
   - 默认为 "默认（无特定情绪）"

### 高级配置

编辑 `config.toml` 设置全局默认值：

```toml
[elevenlabs]
default_model_id = "eleven_turbo_v2_5"    # 使用快速模型
default_language_code = "en-US"           # 英文输入
default_emotion = "cheerful"              # 欢快语调
```

---

## 🔧 技术细节

### API 请求示例

**带完整参数的请求**:
```json
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps

{
  "text": "Hello world！",
  "model_id": "eleven_turbo_v2_5",
  "language_code": "en-US",
  "voice_settings": {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0,
    "use_speaker_boost": true,
    "speed": 1.0,
    "emotion": "cheerful"
  },
  "output_format": "mp3_44100_128"
}
```

### 模型选择建议

| 应用场景 | 推荐模型 | 原因 |
|---------|----------|------|
| 实时直播 | `eleven_turbo_v2_5` | 快速、低延迟 |
| 标准应用 | `eleven_multilingual_v2` | 多语言、质量高 |
| 英文专用 | `eleven_english_v2` | 英文优化、质量高 |
| 存档/冷却 | `eleven_english_v1` | 不推荐新项目 |

### 情绪标签应用

| 情绪 | 适用内容 | 效果 |
|------|---------|------|
| `neutral` | 新闻、教程、文档 | 理性、专业 |
| `cheerful` | 儿童、营销、广告 | 欢快、积极 |
| `sad` | 故事、叙述、剧情 | 低沉、感人 |
| `angry` | 戏剧、新闻评论 | 严肃、有力 |
| `fearful` | 悬念、恐怖内容 | 紧张、不安 |
| `hopeful` | 励志、鼓励性内容 | 期待、积极 |

---

## ⚠️ 注意事项

1. **模型兼容性**
   - 并非所有模型都支持 `emotion` 参数
   - 如果 API 返回错误，尝试切换模型或禁用情绪标签

2. **语言检测**
   - 设置 `language_code` 有利于提高准确性
   - 留空则 API 自动检测（可能有误）

3. **API 额度**
   - 使用不同模型可能会消耗不同额度
   - 注意监控额度使用情况

4. **向后兼容性**
   - 所有新参数都是可选的
   - 如果不设置，将使用 API 默认值
   - 现有项目无需修改即可使用新模型

---

## 📊 文件变更统计

```
修改文件:
  1. pyMediaTools/core/elevenlabs.py
     - 新增 ~120 行（常量定义 + 参数扩展）
     
  2. pyMediaTools/ui/elevenlabs_ui.py
     - 新增 ~80 行（UI 组件）
     - 修改 VoiceSettingsDialog (~50 行)
     - 修改 generate_tts_audio() (~5 行)
     
  3. config.toml
     - 新增 ~4 行配置项

总计新增代码: ~250 行
```

---

## ✨ 后续优化方向

1. **模型预设**
   - 保存常用模型组合（如"英文专业"、"中文温暖"）
   - 快速切换预设配置

2. **情绪分析**
   - 基于文本情感自动选择情绪标签
   - 利用 Groq API 进行文本分析

3. **语言自动识别**
   - 检测输入文本的主要语言
   - 自动选择最佳 language_code

4. **性能对比**
   - UI 中显示模型的性能指标
   - 让用户快速对比不同模型的速度/质量

5. **高级音色控制**
   - 支持更多 voice_settings 参数（如未来添加的）
   - 提供音色预设库

---

## 📞 支持

如有问题或建议，请：
1. 检查 logs 中的详细错误信息
2. 参考 config.toml 的配置说明
3. 查看 API 返回的错误消息（通常在 UI 中显示）

---

**改进结束！所有功能已就绪。** 🎉

