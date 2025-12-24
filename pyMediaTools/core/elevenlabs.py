"""
ElevenLabs API
"""
import os
import requests
import base64
import json
from PySide6.QtCore import QThread, Signal
from ..utils import load_project_config


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

    def __init__(self, api_key=None, voice_id=None, text=None, save_path=None, output_format=None):
        super().__init__()
        cfg = load_project_config().get('elevenlabs', {})
        self.api_key = api_key or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")
        self.voice_id = voice_id
        self.text = text
        self.save_path = save_path
        self.output_format = output_format or cfg.get('default_output_format') or "mp3_44100_128"

    def run(self):
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

            # 生成字幕
            alignment = resp_json.get("alignment")
            if alignment:
                try:
                    srt_path = os.path.splitext(self.save_path)[0] + ".srt"
                    self.create_srt(alignment, srt_path)
                except Exception as e:
                    print(f"字幕生成失败: {e}")

            self.finished.emit(self.save_path)

        except Exception as e:
            self.error.emit(str(e))

    def create_srt(self, alignment, filename):
        """基于 alignment 数据生成 SRT 字幕"""
        chars = alignment.get('characters', [])
        starts = alignment.get('character_start_times_seconds', [])
        ends = alignment.get('character_end_times_seconds', [])
        
        if not chars or not starts or not ends:
            return

        cfg = load_project_config().get('elevenlabs', {})

        # 标点符号集合
        DELIMITERS = cfg.get('srt_delimiters', [" ", "।", "？", "?", "!", "！", ",", "，", '"', "“", "”"])
        SENTENCE_ENDERS = cfg.get('srt_sentence_enders', ["।", "？", "?", "!", "！"])
        MAX_CHARS_PER_LINE = cfg.get('srt_max_chars', 35)
        PAUSE_THRESHOLD = cfg.get('srt_pause_threshold', 0.3)

        sentences = []
        current_line_text = ""
        current_line_start = None
        current_word_text = ""
        current_word_start = None

        count = len(chars)

        for i, char in enumerate(chars):
            if current_word_start is None:
                current_word_start = starts[i]
            
            current_word_text += char

            # 检测停顿 (当前字符结束到下一字符开始的时间差)
            is_pause = False
            if i < count - 1:
                silence = starts[i+1] - ends[i]
                if silence >= PAUSE_THRESHOLD:
                    is_pause = True

            is_delimiter = char in DELIMITERS
            is_last_char = (i == count - 1)

            # 如果遇到分隔符、最后一个字符、或者检测到明显停顿，都视为单词/片段结束
            if is_delimiter or is_last_char or is_pause:
                if current_line_start is None:
                    current_line_start = current_word_start
                
                current_line_text += current_word_text
                current_line_end = ends[i]

                is_sentence_end = char in SENTENCE_ENDERS
                is_too_long = len(current_line_text) >= MAX_CHARS_PER_LINE

                # 换行条件：句末标点、行太长、最后字符、或者有停顿
                if is_sentence_end or is_too_long or is_last_char or is_pause:
                    clean_text = current_line_text.strip()
                    if clean_text:
                        sentences.append({
                            "text": clean_text,
                            "start": current_line_start,
                            "end": current_line_end
                        })
                    current_line_text = ""
                    current_line_start = None
                
                current_word_text = ""
                current_word_start = None

        with open(filename, "w", encoding="utf-8") as f:
            for idx, s in enumerate(sentences):
                f.write(f"{idx + 1}\n")
                f.write(f"{self._format_time(s['start'])} --> {self._format_time(s['end'])}\n")
                f.write(f"{s['text']}\n\n")

    def _format_time(self, seconds):
        """将秒数转换为 SRT 时间格式 HH:MM:SS,mmm"""
        mils = int((seconds % 1) * 1000)
        secs = int(seconds % 60)
        mins = int((seconds / 60) % 60)
        hours = int(seconds / 3600)
        return f"{hours:02d}:{mins:02d}:{secs:02d},{mils:03d}"


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
                    if vid and name:
                        voices_list.append((name, vid))

                self.finished.emit(voices_list)
            else:
                self.error.emit(f"获取声音列表失败 ({response.status_code}): {response.text}")
        except Exception as e:
            self.error.emit(str(e))
