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


class QuotaWorker(QThread):
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
    finished = Signal(str)  # 返回保存的文件路径
    error = Signal(str)

    def __init__(self, api_key=None, voice_id=None, text=None, save_path=None, output_format=None, translate=False, word_level=False, export_xml=False, words_per_line=1, groq_api_key=None, groq_model=None, xml_style_settings=None, video_settings=None, keyword_highlight=False):
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
        data = {
            "text": self.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            "output_format": self.output_format
        }

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
                        cfg = load_project_config().get('elevenlabs', {})
                        
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
