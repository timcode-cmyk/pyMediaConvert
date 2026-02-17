# ElevenLabs 模型选择优化 - 使用指南

## 快速开始

### 1. 获取 API Key
访问 [ElevenLabs 官网](https://www.elevenlabs.io) 获取 API Key。

### 2. 配置 API Key

#### 方式一：环境变量（推荐）
```bash
# macOS/Linux
export ELEVENLABS_API_KEY="sk_xxx..."

# Windows
set ELEVENLABS_API_KEY=sk_xxx...
```

#### 方式二：UI 中保存
在应用中输入 API Key 并点击"💾 保存"。

#### 方式三：config.toml 配置
```toml
[elevenlabs]
api_key = "sk_xxx..."
default_model_id = "eleven_multilingual_v2"
default_output_format = "mp3_44100_128"
```

### 3. 首次使用
1. 启动应用
2. 如果配置了 API Key，会自动加载声音和模型列表
3. 或者手动点击"🔄 刷新配置"

## 核心功能

### 模型选择

#### 自动模型列表
- 点击"🔄 刷新配置"时，从 ElevenLabs API 获取最新模型列表
- 只显示支持文本转语音的模型

#### 模型信息
每个模型显示：
- 模型名称
- 支持的功能（文本转语音、语音转换等）
- 支持的语言列表
- 字符消耗限制

### 语言选择

#### 动态语言列表
- 选择不同模型时，自动更新可用语言列表
- 只显示当前模型支持的语言
- 保持用户之前的选择（如果当前模型支持）

#### 支持的语言
- 中文（简体和繁体）
- 英文（美国和英国口音）
- 多种欧洲、亚洲语言

### 语音设定

#### 风格设置
- **稳定性**：控制发音稳定性（0-100%）
- **相似度提升**：AI 复制原始声音的程度（0-100%）
- **风格**：风格夸张程度（仅当模型支持时启用）
- **速度**：发音速度（0.7×-1.2×）

#### 扬声器增强
- 增强与原始佣声器的相似性
- 仅当模型支持时启用
- 可能略微增加延迟

#### 情绪标签（新增）
- 中立（理性、客观）
- 欢快（积极、开朗）
- 悲伤（低沉、忧伤）
- 害怕（紧张、不安）
- 愤怒（严肃、坚定）
- 希望（期待、鼓励）

## 功能启用/禁用规则

### 何时功能会被禁用

| 功能 | 禁用条件 |
|-----|--------|
| 风格调整 | 模型的 `can_use_style` = false |
| 扬声器增强 | 模型的 `can_use_speaker_boost` = false |
| 语言选择 | 使用模型支持的语言列表 |

### 用户体验
- 禁用的功能会呈灰色并不可操作
- 悬停时显示"当前模型不支持此功能"提示
- 如果模型不支持 TTS，会弹出警告

## 错误处理

### 常见错误

#### 错误 1：网络连接失败
```
获取模型列表异常: [Timeout/Connection error]
```
**解决方案**：检查网络连接，重试刷新配置。

#### 错误 2：API Key 无效
```
获取模型列表失败 (401): Invalid API Key
```
**解决方案**：检查 API Key 是否正确，重新输入并保存。

#### 错误 3：API Key 额度用尽
```
获取模型列表失败 (429): Rate limit exceeded
```
**解决方案**：等待一段时间后重试，或升级 API 额度。

### 调试模式

在 `config.toml` 中启用调试模式：
```toml
[elevenlabs]
debug_save_response = true
```

这会将 API 响应保存到本地缓存，便于调试。

## API 数据结构参考

### 模型对象
```python
{
    'model_id': str,                              # 模型唯一标识
    'name': str,                                 # 显示名称
    'description': str,                          # 描述
    'can_do_text_to_speech': bool,              # 是否支持TTS
    'can_do_voice_conversion': bool,            # 是否支持语音转换
    'can_use_style': bool,                      # 是否支持风格调整
    'can_use_speaker_boost': bool,              # 是否支持扬声器增强
    'serves_pro_voices': bool,                  # 是否服务Pro声音
    'requires_alpha_access': bool,              # 是否需要Alpha访问权限
    'token_cost_factor': float,                 # 成本因子
    'maximum_text_length_per_request': int,     # 最大文本长度
    'max_characters_request_free_user': int,    # 免费用户最大字符
    'max_characters_request_subscribed_user': int,  # 订阅用户最大字符
    'languages': [                              # 支持的语言列表
        {
            'language_id': str,                 # 如 'zh-CN'
            'name': str                         # 如 'Chinese (Simplified)'
        }
    ],
    'concurrency_group': str                    # 并发组标识
}
```

## 高级配置

### 在 config.toml 中设置默认模型

```toml
[elevenlabs]
# 默认模型（用户没有选择时）
default_model_id = "eleven_turbo_v2_5"

# 默认语言
default_language_code = "zh-CN"

# 默认情绪
default_emotion = "neutral"

# 输出格式
default_output_format = "mp3_44100_128"

# 视频设置
srt_pause_threshold = 0.2
srt_max_chars = 35
```

### 完整配置示例

```toml
[elevenlabs]
api_key = "sk_xxx..."
default_model_id = "eleven_turbo_v2_5"
default_language_code = "zh-CN"
default_emotion = "neutral"
default_output_format = "mp3_44100_128"
debug_save_response = false

[groq]
api_key = "gsk_xxx..."
model = "openai/gpt-oss-120b"

[xml_styles]
[xml_styles.source]
font = "Arial"
fontSize = 50
bold = false

[xml_styles.translate]
font = "Arial"
fontSize = 40
bold = false

[xml_styles.highlight]
font = "Arial"
fontSize = 50
bold = true
```

## 最佳实践

### 1. 选择合适的模型
- **速度优先**：选择 `eleven_turbo_v2_5` 或 `eleven_turbo_v3`
- **质量优先**：选择 `eleven_multilingual_v2`
- **英文优先**：选择 `eleven_english_v2`
- **多语言**：选择 `eleven_multilingual_v2`

### 2. 语言选择
- 优先使用 `自动检测`，API 会自动检测文本语言
- 如果检测不准，手动选择语言
- 确保选择的语言与输入文本一致

### 3. 格式与成本控制
- 注意文本长度，避免超过模型限制
- 查看额度使用情况，及时检查
- 使用 `token_cost_factor` 评估成本

### 4. 功能测试
- 在设置功能前，先试听声音
- 如果使用新功能，从小文本开始测试
- 保存功能设定以便重复使用

## 故障排除

### 模型列表为空
1. 检查 API Key 是否有效
2. 检查网络连接
3. 查看日志文件中的错误信息

### 语言列表不更新
1. 重新选择模型
2. 点击"🔄 刷新配置"
3. 重启应用

### 生成失败
1. 检查错误提示信息
2. 验证模型是否支持所选功能
3. 确保文本不超过模型限制
4. 检查额度是否充足

## 更新日志

### v2.0.0 (当前版本)
- ✨ 从 API 动态加载模型列表
- ✨ 根据模型功能动态启用/禁用选项
- ✨ 动态语言列表过滤
- ✨ 改进的模型信息显示
- 🐛 修复模型选择逻辑
- 📚 完整的文档和指南

### v1.0.0
- 初始版本
- 硬编码模型列表
- 基础 TTS 功能
