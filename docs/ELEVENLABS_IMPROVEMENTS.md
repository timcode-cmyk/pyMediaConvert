# pyMediaTools 项目详细分析报告

## 📋 项目概述

**pyMediaTools** 是一个基于 PySide6 的跨平台桌面应用，集成了强大的媒体处理与 AI 创作工具，主要功能包括：

### 核心功能模块

| 模块 | 描述 | 状态 |
|------|------|------|
| **MediaConvert** | 高效批量视频/音频格式转换、水印处理、裁剪等 | ✅ 完整 |
| **ElevenLabs TTS** | 文本转语音、多语言、音效生成 | 🔨 需改进 |
| **Subtitle** | 自动字幕生成、逐词字幕、多语言翻译 | ✅ 完整 |
| **XML Export** | FCPXML 导出支持 DaVinci Resolve/Final Cut Pro | ✅ 完整 |
| **Video Download** | yt-dlp 视频下载 | ✅ 完整 |
| **Download Manager** | aria2c 下载管理 | ✅ 完整 |

---

## 🔍 ElevenLabs 模块当前分析

### 架构组成

```
pyMediaTools/
├── core/
│   ├── elevenlabs.py          # 核心业务逻辑、API调用、多线程workers
│   ├── elevenlabs.py          # 字幕生成、导出等
│   └── ...其他模块
└── ui/
    ├── elevenlabs_ui.py       # UI界面、事件处理
    └── ...其他UI
```

### Core 层分析 (elevenlabs.py)

#### 关键类和功能

1. **QuotaWorker** (继承 QThread)
   - 获取 API 额度信息
   - 显示字符使用率

2. **TTSWorker** (继承 QThread) - ⭐ 重点改进对象
   - 文本转语音核心功能
   - **硬编码模型**: `"eleven_multilingual_v2"`
   - 支持语音设置 (稳定性、相似度、风格、速度、扬声器增强)
   - **缺少**: 模型选择、语言代码、情绪标签
   - 支持字幕生成、翻译、XML导出

3. **SFXWorker** (继承 QThread)
   - 音效生成功能
   - 使用 `"eleven_text_to_sound_v2"` 模型

4. **VoiceListWorker** (继承 QThread)
   - 获取可用声音列表

#### 当前 API 调用实现

```python
# TTSWorker 中的 API 调用 (第 118-123 行)
data = {
    "text": self.text,
    "model_id": "eleven_multilingual_v2",  # ⚠️ 硬编码
    "voice_settings": {
        "stability": ...,
        "similarity_boost": ...,
        "style": ...,
        "use_speaker_boost": ...,
        "speed": ...
    },
    "output_format": self.output_format
}
```

**缺失的 API 参数**:
- ❌ `model_id` 选择 (应支持 v1, v2, v2.5, v3 等)
- ❌ `language_code` (用于指定输入文本语言)
- ❌ `voice_settings.emotion` (情绪标签)

### UI 层分析 (elevenlabs_ui.py)

#### 当前界面结构

| 区域 | 功能 | 完整性 |
|------|------|--------|
| API 配置 | API Key 保存、刷新、额度显示 | ✅ 完整 |
| TTS 功能 | 声音选择、文本输入、生成 | ✅ 完整 |
| 语音设置 | 稳定性、相似度、风格、速度 | ✅ 完整 |
| 字幕选项 | 翻译、逐词、XML导出、高亮 | ✅ 完整 |
| SFX 功能 | 音效描述、时长、生成 | ✅ 完整 |
| 播放控制 | 进度条、时间显示、音量 | ✅ 完整 |

#### 缺失的 UI 组件

- ❌ **模型选择下拉框** (v1/v2/v2.5/v3 等)
- ❌ **语言代码选择** (zh, en, ja, ko, ar 等)
- ❌ **情绪标签选择** (cheerful, sad, fearful, angry 等)

#### VoiceSettingsDialog 当前参数

```python
# 第 289-299 行
self.stability = 50         # ✅ 已有
self.similarity = 75        # ✅ 已有
self.style = 0              # ✅ 已有
self.speed = 100            # ✅ 已有
self.speaker_boost = True   # ✅ 已有
# ❌ emotion 缺失
# ❌ language_code 缺失
```

---

## 📊 ElevenLabs API v2.5 / v3 特性支持

### 支持的模型

根据最新的 ElevenLabs 文档，支持的模型包括：

| 模型 ID | 名称 | 特性 | 推荐用途 |
|---------|------|------|---------|
| `eleven_multilingual_v2` | 多语言 V2 | 多语言、标准质量 | 通用 |
| `eleven_english_v2` | 英文 V2 | 英文优化、较快 | 英文专用 |
| `eleven_english_v1` | 英文 V1 | 英文、较慢 | 存档使用 |
| `eleven_turbo_v2_5` | Turbo V2.5 | **快速、低延迟** | 实时应用 |
| `eleven_turbo_v2` | Turbo V2 | 快速生成 | 快速应用 |

### 语言代码支持

ElevenLabs 支持以下语言代码：

```
中文: zh, zh-CN, zh-TW
英文: en, en-US, en-GB
日文: ja, ja-JP
韩文: ko, ko-KR
阿拉伯文: ar, ar-SA
法文: fr, fr-FR
西班牙文: es, es-ES
德文: de, de-DE
... 等 50+ 种语言
```

### 情绪标签 (Emotion)

支持的情绪标签：

| 标签 | 说明 | 应用场景 |
|------|------|---------|
| `cheerful` | 欢快、积极 | 儿童内容、营销广告 |
| `sad` | 悲伤、低沉 | 叙事、故事讲述 |
| `fearful` | 害怕、紧张 | 恐怖、悬念内容 |
| `angry` | 愤怒、严肃 | 新闻播报、戏剧 |
| `neutral` | 中立、理性 | 技术文档、教程 |
| `hopeful` | 希望、期待 | 励志、鼓励性内容 |

---

## 💡 改进方案

### 1️⃣ **Core 层改进** (elevenlabs.py)

#### 改进点

1. **模型管理**
   - 添加模型常量定义
   - 支持动态模型选择
   - 默认使用推荐模型

2. **参数扩展**
   - 语言代码支持
   - 情绪标签支持
   - 保留现有所有参数兼容性

3. **API 调用优化**
   - 统一参数验证
   - 支持可选参数的灵活组合
   - 更好的错误处理

#### 代码结构调整

```python
# 新增内容

# 模型常量
LANGUAGE_CODES = {
    'Chinese (Simplified)': 'zh-CN',
    'Chinese (Traditional)': 'zh-TW',
    'English (US)': 'en-US',
    'English (UK)': 'en-GB',
    'Japanese': 'ja-JP',
    'Korean': 'ko-KR',
    # ... 等等
}

EMOTION_OPTIONS = {
    'cheerful': '欢快、积极',
    'sad': '悲伤、低沉',
    'fearful': '害怕、紧张',
    'angry': '愤怒、严肃',
    'neutral': '中立、理性',
    'hopeful': '希望、期待',
}

MODEL_OPTIONS = {
    'eleven_multilingual_v2': {
        'name': '多语言 V2',
        'description': '标准多语言模型',
        'languages': 'all',
        'quality': 'high',
    },
    'eleven_english_v2': {...},
    'eleven_turbo_v2_5': {...},
}

class TTSWorker(QThread):
    def __init__(self, ..., model_id=None, language_code=None, emotion=None):
        # 新增参数
        self.model_id = model_id or "eleven_multilingual_v2"
        self.language_code = language_code
        self.emotion = emotion
```

### 2️⃣ **UI 层改进** (elevenlabs_ui.py)

#### 新增 UI 组件

1. **模型选择区域** (在 TTS 部分顶部)
   ```
   模型: [下拉框: v1, v2, v2.5, v3] 
           [?] (信息按钮)
   ```

2. **语言代码选择** (在声音选择下方)
   ```
   语言: [下拉框: 中文(简体), 英文(US), ...]
   ```

3. **情绪标签选择** (在语言选择下方或集成到语音设置)
   ```
   情绪: [下拉框: 中立, 欢快, 悲伤, ...]
   ```

#### VoiceSettingsDialog 扩展

- 添加情绪标签滑块或选择框
- 保留现有的所有设置
- 添加预设组合 (如"专业播音"、"温暖亲切"等)

---

## 📝 改进清单

### Core 修改清单

- [ ] 添加模型、语言、情绪常量定义
- [ ] TTSWorker 构造函数添加 model_id、language_code、emotion 参数
- [ ] TTSWorker.run() 方法更新 API 调用参数
- [ ] 参数验证和错误处理

### UI 修改清单

- [ ] elevenlabs_ui.py 添加模型选择下拉框
- [ ] 添加语言代码选择下拉框
- [ ] 在 VoiceSettingsDialog 中添加情绪标签选择
- [ ] 更新初始化逻辑存储和恢复这些新参数
- [ ] 在 generate_tts_audio() 中传递新参数到 TTSWorker

### Config 修改清单

- [ ] 添加默认模型设置
- [ ] 添加默认语言代码
- [ ] 添加默认情绪标签
- [ ] 记录支持的所有选项

---

## 🎯 预期效果

| 功能 | 改进前 | 改进后 |
|------|--------|--------|
| 模型选择 | 固定 v2 | ✅ 支持 6+ 种模型 |
| 语言支持 | 自动识别 | ✅ 显式选择 50+ 语言 |
| 情绪效果 | 无 | ✅ 6 种情绪标签 |
| 用户体验 | 功能完整 | ✅ 更灵活、更专业 |
| 输出质量 | 固定 | ✅ 可针对性优化 |

---

## 📂 涉及文件

1. `/Volumes/Ark/shell/pyMediaConvert/pyMediaTools/core/elevenlabs.py` 
2. `/Volumes/Ark/shell/pyMediaConvert/pyMediaTools/ui/elevenlabs_ui.py`
3. `/Volumes/Ark/shell/pyMediaConvert/config.toml`

下一步将实施具体的代码改进。

