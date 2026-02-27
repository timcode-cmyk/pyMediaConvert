"""
ElevenLabs API
"""
import os
import requests
import base64
import json
import pysrt
from PySide6.QtCore import QThread, Signal
from ..utils import load_project_config
from .subtitle_writer import SubtitleWriter
from .subtitle_builder import SubtitleSegmentBuilder
from .translation_manager import TranslationManager
from .groq_analysis import extract_keywords
from ..logging_config import get_logger

logger = get_logger(__name__)

# ============================================================================
# ElevenLabs API 常量定义 - 模型、语言、情绪支持
# ============================================================================

# 支持的模型列表 (最新版本，包含 V3)
ELEVENLABS_MODELS = {
    
}

# 语言代码列表 (根据 ElevenLabs 官方支持)
LANGUAGE_CODES = {
    'en': '英语 (English)',
    'es': '西班牙语 (Español)',
    'pt': '葡萄牙语 (Português)',
    'fr': '法语 (Français)',
    'de': '德语 (Deutsch)',
    'it': '意大利语 (Italiano)',
    'pl': '波兰语 (Polski)',
    'tr': '土耳其语 (Türkçe)',
    'ru': '俄语 (Русский)',
    'nl': '荷兰语 (Nederlands)',
    'cs': '捷克语 (Čeština)',
    'sv': '瑞典语 (Svenska)',
    'no': '挪威语 (Norsk)',
    'ja': '日语 (日本語)',
    'ko': '韩语 (한국어)',
    'zh': '中文 (简体)',
    'zh-TW': '中文 (繁體)',
    'hi': '印地语 (हिंदी)',
    'th': '泰语 (ไทย)',
    'ar': '阿拉伯语 (العربية)',
    'uk': '乌克兰语 (Українська)',
    'vi': '越南语 (Tiếng Việt)',
    'id': '印尼语 (Bahasa Indonesia)',
    'ms': '马来语 (Bahasa Melayu)',
    'el': '希腊语 (Ελληνικά)',
    'da': '丹麦语 (Dansk)',
    'fi': '芬兰语 (Suomi)',
    'hu': '匈牙利语 (Magyar)',
    'ro': '罗马尼亚语 (Română)',
    'he': '希伯来语 (עברית)',
    'fa': '波斯语 (فارسی)',
    'bn': '孟加拉语 (বাংলা)',
    'ta': '泰米尔语 (தமிழ்)',
}

# 情绪标签列表 - 包含英文标签和中文+表情映射
EMOTION_OPTIONS = {
    'neutral': {
        'name': '中立',
        'description': '理性、客观、标准播读风格',
        'emoji': '😐',
    },
    'cheerful': {
        'name': '欢快',
        'description': '积极、开朗、充满能量',
        'emoji': '😊',
    },
    'happy': {
        'name': '开心',
        'description': '高兴、愉快、充满喜悦',
        'emoji': '😄',
    },
    'sad': {
        'name': '悲伤',
        'description': '低沉、忧伤、富有表现力',
        'emoji': '😢',
    },
    'fearful': {
        'name': '害怕',
        'description': '紧张、不安、带有恐惧感',
        'emoji': '😨',
    },
    'angry': {
        'name': '愤怒',
        'description': '严肃、坚定、充满力量',
        'emoji': '😠',
    },
    'hopeful': {
        'name': '希望',
        'description': '期待、鼓励、积极向上',
        'emoji': '🤗',
    },
    'excited': {
        'name': '兴奋',
        'description': '激动、兴奋、充满能量',
        'emoji': '🤩',
    },
    'whisper': {
        'name': '耳语',
        'description': '低声细语、温柔私密',
        'emoji': '🤫',
    },
    'annoyed': {
        'name': '厌烦',
        'description': '烦恼、不满、略感沮丧',
        'emoji': '😒',
    },
    'appalled': {
        'name': '震惊',
        'description': '惊讶、震惊、无法置信',
        'emoji': '😱',
    },
    'thoughtful': {
        'name': '思考',
        'description': '沉思、体贴、深思熟虑',
        'emoji': '🤔',
    },
    'surprised': {
        'name': '惊讶',
        'description': '意外、惊喜、出乎意料',
        'emoji': '😲',
    },
    'laughing': {
        'name': '笑声',
        'description': '大声笑、欢快的笑声',
        'emoji': '😂',
    },
    'chuckles': {
        'name': '轻笑',
        'description': '轻声笑、温和的笑声',
        'emoji': '😄',
    },
    'sighs': {
        'name': '叹气',
        'description': '深叹、无奈、释然',
        'emoji': '😔',
    },
    'clears throat': {
        'name': '清嗓子',
        'description': '清喉咙、整理嗓子',
        'emoji': '🗣️',
    },
    'short pause': {
        'name': '短停顿',
        'description': '短暂停顿、瞬间沉默',
        'emoji': '⏸️',
    },
    'long pause': {
        'name': '长停顿',
        'description': '长时间停顿、深长的沉默',
        'emoji': '⏸️',
    },
    'exhales sharply': {
        'name': '急速呼气',
        'description': '快速吐气、呼吸声',
        'emoji': '💨',
    },
    'inhales deeply': {
        'name': '深吸气',
        'description': '深吸一口气、吸气声',
        'emoji': '🌬️',
    },
}

# ⭐ 新增：英文标签到中文+表情的映射
EMOTION_DISPLAY_MAP = {emotion_key: f"{info['emoji']} {info['name']}" for emotion_key, info in EMOTION_OPTIONS.items()}

# ⭐ 新增：中文+表情到英文标签的反向映射
DISPLAY_TO_EMOTION_MAP = {display: emotion_key for emotion_key, display in EMOTION_DISPLAY_MAP.items()}


class QuotaWorker(QThread):
    """
    从 ElevenLabs API 获取额度信息
    根据 API 文档: GET /v1/user
    """
    quota_info = Signal(int, int)  # (usage, limit)
    error = Signal(str)

    def __init__(self, api_key=None):
        super().__init__()
        cfg = load_project_config().get('elevenlabs', {})
        self.api_key = api_key or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")

    def run(self):
        url = "https://api.elevenlabs.io/v1/user"
        headers = {"xi-api-key": self.api_key}
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if 'subscription' in data:
                    usage = data['subscription'].get('character_count', 0)
                    limit = data['subscription'].get('character_limit', 0)
                    self.quota_info.emit(usage, limit)
                else:
                    self.error.emit("未能解析订阅信息。")
            else:
                self.error.emit(f"获取额度失败: {response.text}")
        except Exception as e:
            self.error.emit(str(e))


class TTSWorker(QThread):
    """
    从 ElevenLabs API 生成语音
    根据 API 文档: POST /v1/text-to-speech/{voice_id}/with-timestamps
    """
    finished = Signal(str)  # 返回保存的文件路径
    error = Signal(str)

    def __init__(self, api_key=None, voice_id=None, text=None, save_path=None, output_format=None, 
                 translate=False, word_level=False, export_xml=False, words_per_line=1, 
                 groq_api_key=None, groq_model=None, xml_style_settings=None, video_settings=None, 
                 keyword_highlight=False, voice_settings=None, model_id=None, language_code=None, emotion=None):
        super().__init__()
        cfg = load_project_config().get('elevenlabs', {})
        self.api_key = api_key or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")
        self.voice_id = voice_id
        self.text = text
        self.save_path = save_path
        self.output_format = output_format or cfg.get('default_output_format') or "mp3_44100_128"
        self.debug_mode = cfg.get('debug_save_response', False)
        self.translate = translate
        self.word_level = word_level
        self.words_per_line = words_per_line
        self.export_xml = export_xml
        self.groq_api_key = groq_api_key
        self.groq_model = groq_model
        self.xml_style_settings = xml_style_settings
        self.video_settings = video_settings if video_settings else {}
        self.keyword_highlight = keyword_highlight
        
        # ⭐ 新增：模型、语言、情绪参数
        self.model_id = model_id or cfg.get('default_model_id')
        self.language_code = language_code or cfg.get('default_language_code')
        self.emotion = emotion or cfg.get('default_emotion')
        
        # Use provided voice settings or defaults
        self.voice_settings = voice_settings if voice_settings else {
            'stability': 0.5,
            'similarity_boost': 0.75,
            'style': 0,
            'use_speaker_boost': True,
            'speed': 1.0
        }

    def run(self):
        json_cache_path = os.path.splitext(self.save_path)[0] + ".json"

        # 如果开启调试模式且缓存文件存在，则直接使用
        if self.debug_mode and os.path.exists(json_cache_path):
            try:
                with open(json_cache_path, 'r', encoding='utf-8') as f:
                    resp_json = json.load(f)
                logger.info(f"[调试模式] 从缓存加载TTS响应: {json_cache_path}")
                self.process_response(resp_json)
                return
            except Exception as e:
                logger.warning(f"[调试模式] 加载缓存失败，将重新调用API. 错误: {e}")


        # --- 正常API调用 ---
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/with-timestamps"
        headers = {
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        # 构建请求体 - 支持新的模型、语言、情绪参数
        data = {
            "text": self.text,
            "model_id": self.model_id,  # ⭐ 使用可配置的模型ID
            "voice_settings": {
                "stability": self.voice_settings.get('stability', 0.5),
                "similarity_boost": self.voice_settings.get('similarity_boost', 0.75),
                "style": self.voice_settings.get('style', 0),
                "use_speaker_boost": self.voice_settings.get('use_speaker_boost', True),
                "speed": self.voice_settings.get('speed', 1.0)
            },
            "output_format": self.output_format
        }
        
        # ⭐ 条件性添加语言代码（可选参数）
        if self.language_code:
            data["language_code"] = self.language_code
            logger.info(f"使用语言代码: {self.language_code}")
        
        # ⭐ 条件性添加情绪标签（可选参数）
        if self.emotion:
            data["voice_settings"]["emotion"] = self.emotion
            logger.info(f"使用情绪标签: {self.emotion}")
        
        logger.info(f"使用模型: {self.model_id}")

        try:
            response = requests.post(url, json=data, headers=headers, timeout=120)
            if response.status_code != 200:
                self.error.emit(f"TTS 生成失败 ({response.status_code}): {response.text}")
                return

            try:
                resp_json = response.json()
            except Exception:
                self.error.emit("无法解析 TTS 返回的 JSON。")
                return

            # 如果开启调试模式，保存响应到文件
            if self.debug_mode:
                try:
                    with open(json_cache_path, 'w', encoding='utf-8') as f:
                        json.dump(resp_json, f, ensure_ascii=False, indent=2)
                    logger.info(f"[调试模式] 已保存TTS响应到缓存: {json_cache_path}")
                except Exception as e:
                    logger.error(f"[调试模式] 保存响应到缓存失败. 错误: {e}")

            self.process_response(resp_json)

        except Exception as e:
            self.error.emit(str(e))

    def process_response(self, resp_json):
        """
        处理来自API或缓存的JSON响应。
        使用新的模块化工具类处理字幕生成、翻译等功能。
        """
        try:
            # Step 1: 解码和保存音频
            audio_b64 = resp_json.get("audio_base64") or resp_json.get("audio")
            if not audio_b64:
                self.error.emit("未能从 TTS 响应中提取音频(audio_base64)。")
                return

            try:
                audio_bytes = base64.b64decode(audio_b64)
            except Exception:
                self.error.emit("无法解码返回的音频 base64 数据。")
                return

            try:
                os.makedirs(os.path.dirname(self.save_path) or ".", exist_ok=True)
                with open(self.save_path, "wb") as f:
                    f.write(audio_bytes)
            except Exception as e:
                self.error.emit(f"保存音频失败: {str(e)}")
                return

            # Step 2: 生成字幕（委托给 SubtitleSegmentBuilder 和 SubtitleWriter）
            alignment = resp_json.get("alignment")
            if alignment:
                try:
                    base_path = os.path.splitext(self.save_path)[0]
                    
                    chars = alignment.get('characters', [])
                    starts = alignment.get('character_start_times_seconds', [])
                    ends = alignment.get('character_end_times_seconds', [])
                    
                    if not chars or not starts or not ends:
                        logger.warning("alignment 数据不完整，跳过字幕生成。")
                    else:
                        cfg = load_project_config().get('elevenlabs', {}).copy()
                        # 使用 UI 传入的视频设置覆盖配置文件的默认值 (包含断行阈值、每行最大字符等)
                        if self.video_settings:
                            cfg.update(self.video_settings)
                        
                        # 2.1 生成标准字幕（始终）
                        builder = SubtitleSegmentBuilder(config=cfg)
                        standard_segments = builder.build_segments(chars, starts, ends, word_level=False)
                        standard_srt_path = base_path + ".srt"
                        SubtitleWriter.write_srt(standard_srt_path, standard_segments)
                        message = f"标准字幕已保存: {standard_srt_path}"
                        logger.info(message)
                        
                        # 2.2 生成逐词字幕（可选）
                        if self.word_level:
                            word_segments = builder.build_segments(
                                chars, starts, ends, 
                                word_level=True, 
                                words_per_line=self.words_per_line
                            )
                            word_srt_path = base_path + "_word.srt"
                            SubtitleWriter.write_srt(word_srt_path, word_segments)
                            message = f"逐词字幕已保存: {word_srt_path}"
                            logger.info(message)
                        
                        # 2.3 生成翻译字幕（可选）
                        if self.translate:
                            full_cfg = load_project_config()
                            groq_cfg = full_cfg.get('groq', {})
                            api_key = self.groq_api_key or groq_cfg.get('api_key') or os.getenv("GROQ_API_KEY")
                            model = self.groq_model or groq_cfg.get('model', 'openai/gpt-oss-120b')
                            
                            if api_key:
                                # ✨ 关键改进：翻译时使用完整句子分段（ignore_line_length=True）
                                # 这样可以避免被行长度限制打断的不完整句子，提高翻译准确性
                                translation_segments = builder.build_segments(
                                    chars, starts, ends, 
                                    word_level=False,
                                    ignore_line_length=True  # 忽略行长度限制，只按标点和停顿分割
                                )
                                
                                try:
                                    translator = TranslationManager(api_key=api_key, model=model)
                                    translated_segments = translator.translate_segments(translation_segments)
                                    trans_srt_path = base_path + "_cn.srt"
                                    SubtitleWriter.write_srt(trans_srt_path, translated_segments)
                                    message = f"翻译字幕已保存: {trans_srt_path}"
                                    logger.info(message)
                                except Exception as e:
                                    logger.error(f"翻译失败: {e}")
                                    self.error.emit(f"翻译失败: {e}")
                            else:
                                logger.warning("未找到 Groq API Key，跳过翻译。请在 config.toml 中配置 [groq] api_key。")
                        
                        # 2.4 导出为 FCPXML（可选）
                        if self.export_xml:
                            try:
                                from .SrtsToFcpxml import SrtsToFcpxml
                                xml_path = base_path + ".fcpxml"
                                
                                # 读取标准字幕
                                with open(standard_srt_path, 'r', encoding='utf-8') as f:
                                    src_content = f.read()
                                
                                # 收集翻译内容（如果有）
                                trans_contents = []
                                trans_srt_path = base_path + "_cn.srt"
                                if os.path.exists(trans_srt_path):
                                    with open(trans_srt_path, 'r', encoding='utf-8') as f:
                                        trans_contents.append(f.read())
                                
                                # Extract keywords if enabled
                                if self.keyword_highlight:
                                    # Use configured Groq key, or fall back to env/config
                                    full_cfg = load_project_config()
                                    groq_cfg = full_cfg.get('groq', {})
                                    g_key = self.groq_api_key or groq_cfg.get('api_key') or os.getenv("GROQ_API_KEY")
                                    if g_key:
                                        logger.info("正在使用 Groq 分析重点关键词...")
                                        try:
                                            keywords = extract_keywords(self.text, g_key, model=self.groq_model or "openai/gpt-oss-120b")
                                            logger.info(f"提取到的关键词: {keywords}")
                                            self.video_settings['keywords'] = keywords
                                        except Exception as e:
                                            logger.error(f"关键词提取失败: {e}")
                                            self.error.emit(f"关键词提取失败: {e}")
                                    else:
                                        logger.warning("未配置 Groq Key，跳过关键词高亮提取。")

                                SrtsToFcpxml(src_content, trans_contents, xml_path, False, xml_style_settings=self.xml_style_settings, video_settings=self.video_settings)
                                message = f"FCPXML 已导出: {xml_path}"
                                logger.info(message)
                            except ImportError:
                                logger.error("导出XML失败: 未找到 SrtsToFcpxml 模块或依赖缺失")
                            except Exception as e:
                                logger.error(f"导出XML出错: {e}")
                
                except Exception as e:
                    logger.error(f"字幕/后续处理生成失败: {e}")
                    self.error.emit(f"字幕处理失败: {e}")

            self.finished.emit(self.save_path)
        except Exception as e:
            self.error.emit(f"处理响应时出错: {str(e)}")

 

class SFXWorker(QThread):
    """从 ElevenLabs API 生成音效
    根据 API 文档: POST /v1/sound-generation
    """
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, api_key=None, prompt=None, duration=None, save_path=None, output_format=None):
        super().__init__()
        cfg = load_project_config().get('elevenlabs', {})
        self.api_key = api_key or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")
        self.prompt = prompt
        self.duration = duration
        self.save_path = save_path
        self.output_format = output_format or cfg.get('default_output_format') or "mp3_44100_128"

    def run(self):
        url = "https://api.elevenlabs.io/v1/sound-generation"
        # 使用更宽松的 Accept，并将 output_format 作为 query 参数（符合文档）
        headers = {"Accept": "audio/*", "Content-Type": "application/json", "xi-api-key": self.api_key}
        # 根据 API 文档，必须提供 `text` 字段；为兼容性同时保留 `prompt`。支持可选字段：loop, prompt_influence, duration_seconds, model_id
        data = {
            "text": self.prompt,
            "prompt": self.prompt,
            "duration_seconds": self.duration,
            "loop": False,
            "prompt_influence": 0.3,
            "model_id": "eleven_text_to_sound_v2",
        }
        params = {"output_format": self.output_format}
        try:
            response = requests.post(url, json=data, headers=headers, params=params, timeout=120)
            # 接受所有 2xx 状态为成功
            if 200 <= response.status_code < 300:
                os.makedirs(os.path.dirname(self.save_path) or ".", exist_ok=True)
                with open(self.save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                self.finished.emit(self.save_path)
            else:
                # 尝试解析响应为 JSON 以得到更友好的错误信息
                try:
                    resp_text = response.json()
                except Exception:
                    resp_text = response.text

                if response.status_code == 404:
                    self.error.emit(
                        f"SFX 生成失败 (404 Not Found)。可能原因：API 路径已更改或当前 API Key 无音效生成权限。响应: {resp_text}"
                    )
                elif response.status_code == 422:
                    # 验证错误，通常表示请求体缺少或格式错误的必需字段
                    self.error.emit(
                        f"SFX 生成失败 (422 Unprocessable Entity)。请检查请求体（需要字段 'text'，并确保其它字段合法）。响应: {resp_text}"
                    )
                else:
                    self.error.emit(f"SFX 生成失败 ({response.status_code}): {resp_text}")
        except Exception as e:
            self.error.emit(str(e))


# ============================================================================
# ModelListWorker: 从 API 获取可用模型列表及其功能
# ============================================================================
class ModelListWorker(QThread):
    """
    从 ElevenLabs API 获取可用模型列表
    根据 API 文档: GET /v1/models
    """
    finished = Signal(list)  # 发送 (model_id, model_info_dict) 元组列表
    error = Signal(str)

    def __init__(self, api_key=None):
        super().__init__()
        cfg = load_project_config().get('elevenlabs', {})
        self.api_key = api_key or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")

    def run(self):
        url = "https://api.elevenlabs.io/v1/models"
        headers = {
            "xi-api-key": self.api_key,
            "Accept": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                models_list = []
                
                # 响应是一个数组
                if isinstance(data, list):
                    for model in data:
                        model_id = model.get('model_id')
                        if model_id:
                            models_list.append({
                                'model_id': model_id,
                                'name': model.get('name', model_id),
                                'description': model.get('description', ''),
                                'can_do_text_to_speech': model.get('can_do_text_to_speech', False),
                                'can_do_voice_conversion': model.get('can_do_voice_conversion', False),
                                'can_use_style': model.get('can_use_style', False),
                                'can_use_speaker_boost': model.get('can_use_speaker_boost', False),
                                'serves_pro_voices': model.get('serves_pro_voices', False),
                                'requires_alpha_access': model.get('requires_alpha_access', False),
                                'token_cost_factor': model.get('token_cost_factor', 1.0),
                                'maximum_text_length_per_request': model.get('maximum_text_length_per_request', 1000),
                                'max_characters_request_free_user': model.get('max_characters_request_free_user'),
                                'max_characters_request_subscribed_user': model.get('max_characters_request_subscribed_user'),
                                'languages': model.get('languages', []),  # 列表
                                'concurrency_group': model.get('concurrency_group', ''),
                            })
                
                if not models_list:
                    self.error.emit("未能从 API 响应中解析任何模型。")
                    return
                
                logger.info(f"成功获取 {len(models_list)} 个模型")
                self.finished.emit(models_list)
            else:
                self.error.emit(f"获取模型列表失败 ({response.status_code}): {response.text}")
        except Exception as e:
            self.error.emit(f"获取模型列表异常: {str(e)}")


class VoiceListWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, api_key=None):
        super().__init__()
        cfg = load_project_config().get('elevenlabs', {})
        self.api_key = api_key or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")

    def run(self):
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": self.api_key, "Accept": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                voices_list = []
                if isinstance(data, dict) and "voices" in data:
                    raw = data["voices"]
                elif isinstance(data, list):
                    raw = data
                else:
                    raw = []

                for v in raw:
                    vid = v.get("voice_id") or v.get("id") or v.get("uuid")
                    name = v.get("name") or v.get("label") or vid
                    preview_url = v.get("preview_url")
                    if vid and name:
                        voices_list.append((name, vid, preview_url))

                self.finished.emit(voices_list)
            else:
                self.error.emit(f"获取声音列表失败 ({response.status_code}): {response.text}")
        except Exception as e:
            self.error.emit(str(e))
