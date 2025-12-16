import os
import requests
import base64
import json
from PySide6.QtCore import QThread, Signal


class QuotaWorker(QThread):
    quota_info = Signal(int, int)  # (usage, limit)
    error = Signal(str)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

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

    def __init__(self, api_key, voice_id, text, save_path):
        super().__init__()
        self.api_key = api_key
        self.voice_id = voice_id
        self.text = text
        self.save_path = save_path
        self.output_format = "mp3_44100_128"

    def run(self):
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        data = {
            "text": self.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
            "output_format": self.output_format
        }

        try:
            response = requests.post(url, json=data, headers=headers, timeout=120)
            if response.status_code != 200:
                self.error.emit(f"TTS 生成失败 ({response.status_code}): {response.text}")
                return

            content_type = response.headers.get("Content-Type", "")
            audio_bytes = None

            if "application/json" in content_type or response.text.strip().startswith("{"):
                try:
                    resp_json = response.json()
                except Exception:
                    self.error.emit("无法解析 TTS 返回的 JSON。")
                    return

                audio_b64 = resp_json.get("audio") or resp_json.get("audio_base64") or resp_json.get("audioBytes")
                if isinstance(audio_b64, str) and audio_b64.strip():
                    try:
                        audio_bytes = base64.b64decode(audio_b64)
                    except Exception:
                        self.error.emit("无法解码返回的音频 base64 数据。")
                        return

            elif "audio/" in content_type or "application/octet-stream" in content_type:
                audio_bytes = response.content
            else:
                try:
                    resp_json = response.json()
                    audio_b64 = resp_json.get("audio") or resp_json.get("audio_base64")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                except Exception:
                    audio_bytes = response.content

            if not audio_bytes:
                self.error.emit("未能从 TTS 响应中提取音频。")
                return

            try:
                os.makedirs(os.path.dirname(self.save_path) or ".", exist_ok=True)
                with open(self.save_path, "wb") as f:
                    f.write(audio_bytes)
            except Exception as e:
                self.error.emit(f"保存音频失败: {str(e)}")
                return

            # SRT 生成功能已移除；仅保存音频并返回成功路径
            self.finished.emit(self.save_path) 

        except Exception as e:
            self.error.emit(str(e))

    # SRT 生成功能已移除 — 保持此位置为空以便未来扩展（例如：外部字幕服务）
    # pass


class SFXWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, api_key, prompt, duration, save_path):
        super().__init__()
        self.api_key = api_key
        self.prompt = prompt
        self.duration = duration
        self.save_path = save_path
        self.output_format = "mp3_44100_128"

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

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

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
