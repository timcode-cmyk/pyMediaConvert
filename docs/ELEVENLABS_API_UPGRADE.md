# ElevenLabs API 升级与优化详细分析

## 项目概述
本项目是一个基于 PySide6 的多媒体处理工具，集成了 ElevenLabs API 用于文本转语音 (TTS) 和音效生成 (SFX)。

## 问题分析

### 1. **模型选择逻辑缺陷**

#### 问题描述
- **硬编码模型列表**：之前的模型列表完全硬编码在代码中，而不是从 ElevenLabs API 动态获取
- **功能验证缺失**：没有检查所选模型是否支持特定功能（如文本转语音、风格、扬声器增强等）
- **语言支持不清楚**：UI 中语言选项是全局的，不能根据所选模型的实际支持情况进行动态过滤
- **用户体验差**：用户可能选择一个不支持当前功能的模型，导致 API 调用失败

#### 示例
假设用户选择了一个不支持风格调整的模型，但 UI 上风格滑块仍然是可操作的，最后 API 会返回错误。

### 2. **API 文档要求**

根据最新的 ElevenLabs API 文档，模型列表端点返回以下结构：

```json
{
  "model_id": "eleven_turbo_v2_5",
  "name": "Turbo V2.5",
  "description": "Fast model",
  "can_do_text_to_speech": true,
  "can_do_voice_conversion": false,
  "can_use_style": true,
  "can_use_speaker_boost": true,
  "serves_pro_voices": false,
  "token_cost_factor": 1.0,
  "maximum_text_length_per_request": 3000,
  "max_characters_request_free_user": 10000,
  "max_characters_request_subscribed_user": 1000000,
  "languages": [
    {
      "language_id": "zh-CN",
      "name": "Chinese (Simplified)"
    }
  ],
  "concurrency_group": "group1"
}
```

## 解决方案

### 1. **新增 ModelListWorker 类**

在 `pyMediaTools/core/elevenlabs.py` 中添加了 `ModelListWorker` 类：

```python
class ModelListWorker(QThread):
    """从 ElevenLabs API 获取可用模型列表"""
    finished = Signal(list)  # 发送模型列表
    error = Signal(str)

    def run(self):
        url = "https://api.elevenlabs.io/v1/models"
        # 分析每个模型的功能
        # 返回包含所有必要信息的模型字典列表
```

**关键特性**：
- 调用 `/v1/models` 端点获取最新模型列表
- 提取每个模型的功能支持信息
- 捕获语言支持列表
- 异步处理，不阻塞 UI

### 2. **更新 UI 模型加载逻辑**

#### load_voices() 方法改进
```python
def load_voices(self):
    # 同时启动两个 worker
    self.model_worker = ModelListWorker(api_key)
    self.voice_worker = VoiceListWorker(api_key)
    
    # 都启动后等待结果
    self.model_worker.start()
    self.voice_worker.start()
```

#### 新增 on_models_loaded() 回调
- 清空并重新填充模型选择框（来自 API）
- 存储模型信息到 `self.models_info` 字典
- 默认选择第一个支持 TTS 的模型
- 触发模型变化处理

#### 新增 on_model_changed() 回调
- 当用户选择不同模型时自动触发
- 检查模型是否支持 TTS（如果不支持则发出警告）
- 调用 `update_feature_availability()` 和 `update_available_languages()`

### 3. **动态启用/禁用功能**

#### update_feature_availability() 方法
根据模型的 API 返回信息，动态启用/禁用相关功能：

```python
def update_feature_availability(self, model_info):
    """根据模型信息启用/禁用相关功能"""
    can_use_style = model_info.get('can_use_style', False)
    can_use_speaker_boost = model_info.get('can_use_speaker_boost', False)
    
    # 存储到 self.current_model_features
    self.current_model_features = {
        'can_use_style': can_use_style,
        'can_use_speaker_boost': can_use_speaker_boost,
        'can_do_voice_conversion': model_info.get('can_do_voice_conversion', False),
    }
```

#### VoiceSettingsDialog 集成
- 接收 `model_features` 参数
- 根据功能支持情况启用/禁用 UI 组件
- 风格滑块不支持时置灰并显示提示
- 扬声器增强复选框不支持时禁用并显示提示

示例代码：
```python
class VoiceSettingsDialog(QDialog):
    def __init__(self, parent=None, model_features=None):
        self.model_features = model_features or {
            'can_use_style': True,
            'can_use_speaker_boost': True,
        }
        self.setup_ui()
    
    def setup_ui(self):
        # ...风格设置
        can_use_style = self.model_features.get('can_use_style', True)
        self.slider_style.setEnabled(can_use_style)
        
        # ...扬声器增强
        can_use_speaker_boost = self.model_features.get('can_use_speaker_boost', True)
        self.chk_speaker_boost.setEnabled(can_use_speaker_boost)
```

### 4. **动态语言列表**

#### update_available_languages() 方法
- 从模型的 `languages` 数组提取支持的语言
- 将 `language_id` 映射到用户友好的语言名称
- 清空并重新填充语言选择框
- 尝试恢复用户之前的选择
- 如果之前选择的语言不再支持，选择第一个可用语言

```python
def update_available_languages(self, model_info):
    languages = model_info.get('languages', [])
    
    for lang in languages:
        lang_id = lang.get('language_id')
        # 查找对应的语言名称并添加到列表
```

## 改进效果

### 用户体验
1. **实时反馈**：选择模型后立即更新可用功能
2. **信息完整性**：用户看到的功能都是当前模型实际支持的
3. **错误预防**：不支持的功能被禁用，提高 API 成功率
4. **智能语言**：只显示当前模型支持的语言

### 代码质量
1. **模块化**：ModelListWorker 独立处理 API 请求
2. **可维护性**：不需要手动更新模型列表，自动同步 API
3. **错误处理**：完整的异常捕获和用户提示

## 数据流程图

```
用户点击 "刷新配置"
    ↓
调用 load_voices()
    ↓
启动两个 Worker：
    ├─ ModelListWorker → /v1/models
    └─ VoiceListWorker → /v1/voices
    ↓
收到 models 列表 → on_models_loaded()
    ├─ 清空 combo_model
    ├─ 添加新模型（从 API）
    ├─ 存储模型信息到 models_info
    └─ 触发 on_model_changed()
    ↓
on_model_changed()
    ├─ 调用 update_feature_availability()
    │   └─ 存储 current_model_features
    ├─ 调用 update_available_languages()
    │   └─ 更新语言列表
    └─ 显示模型详情 (日志)
    ↓
用户选择模型
    ↓
combo_model.currentIndexChanged 信号
    └─ 触发 on_model_changed()
        └─ （重复上述步骤）
    ↓
用户点击 "语音设定"
    ↓
创建 VoiceSettingsDialog
    ├─ 传入 current_model_features
    ├─ 根据功能启用/禁用选项
    └─ 显示对话框
```

## API 调用时机

1. **应用启动**：
   - 从 config.toml / 环境变量加载保存的 API Key
   - 自动调用 load_voices()

2. **用户按下 "刷新配置"**：
   - 手动调用 load_voices()
   - 更新模型、声音和额度信息

3. **生成 TTS**：
   - 使用当前选择的 model_id、language_code 和 emotion
   - 检查模型的 `maximum_text_length_per_request`，确保文本不超长

## 注意事项

### 1. 模型可用性
- 某些模型可能需要 `alpha_access` 或 Pro 订阅
- API 可能在 `requires_alpha_access` 字段中标记
- 建议在 UI 中显示模型的访问要求

### 2. 成本计算
- 每个模型有 `token_cost_factor` 影响费用
- TTS 字符消耗根据 `max_characters_request_free_user` 和 `max_characters_request_subscribed_user` 而定
- 提示用户在生成前检查额度

### 3. 语言查询
- 某些旧模型可能没有返回 `languages` 字段
- 此时应允许所有预定义语言

### 4. 并发限制
- API 可能有 `concurrency_group` 限制并发请求数
- 多个模型可能共享同一个并发组

## 文件修改列表

### pyMediaTools/core/elevenlabs.py
- **新增**：`ModelListWorker` 类（~60 行）
- **改动**：导入语句和模块结构

### pyMediaTools/ui/elevenlabs_ui.py
- **导入**：增加 `ModelListWorker`
- **ElevenLabsWidget.__init__**：
  - 新增 `self.models_info` 字典
  - 新增 `self.current_model_features` 字典
- **setup_ui**：
  - 连接 `combo_model.currentIndexChanged` 信号到 `on_model_changed()`
- **新增方法**：
  - `on_models_loaded(models)`：处理模型列表加载
  - `on_model_changed()`：处理模型选择变化
  - `update_feature_availability(model_info)`：更新功能可用性
  - `update_available_languages(model_info)`：更新语言列表
- **修改方法**：
  - `load_voices()`：同时启动 ModelListWorker
  - `open_voice_settings()`：传入 `model_features` 参数
- **VoiceSettingsDialog**：
  - `__init__`：接受 `model_features` 参数
  - `setup_ui()`：根据功能启用/禁用风格和扬声器增强

## 总结

这次升级完全改造了 ElevenLabs 模型选择系统，从硬编码的静态列表升级为动态、API驱动的解决方案。用户现在能够：

1. ✅ **看到所有可用模型**（实时从 API 获取）
2. ✅ **自动过滤语言**（根据模型支持）
3. ✅ **禁用不支持的功能**（自动根据模型能力）
4. ✅ **获得更好的错误提示**（功能不可用时显示原因）
5. ✅ **无需代码更新**（模型列表自动同步）

所有改动都与 ElevenLabs 最新 API 文档完全兼容。
