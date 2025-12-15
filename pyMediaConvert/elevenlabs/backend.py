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
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/with-timestamps"
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
            alignment = None

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

                alignment = resp_json.get("alignment") or resp_json.get("timestamps") or resp_json.get("words") or resp_json.get("segments")

            elif "audio/" in content_type or "application/octet-stream" in content_type:
                audio_bytes = response.content
                alignment = None
            else:
                try:
                    resp_json = response.json()
                    audio_b64 = resp_json.get("audio") or resp_json.get("audio_base64")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        alignment = resp_json.get("alignment") or resp_json.get("timestamps")
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

            if alignment:
                srt_path = os.path.splitext(self.save_path)[0] + ".srt"
                try:
                    self._write_srt(alignment, srt_path)
                except Exception as e:
                    # SRT 失败不阻止成功返回，但报告错误
                    self.error.emit(f"SRT 生成失败: {str(e)}")
                    self.finished.emit(self.save_path)
                    return

            self.finished.emit(self.save_path)

        except Exception as e:
            self.error.emit(str(e))

    def _format_timestamp(self, seconds_val):
        try:
            if isinstance(seconds_val, str):
                if ":" in seconds_val:
                    parts = seconds_val.split(":")
                    parts = [float(p) for p in parts]
                    if len(parts) == 3:
                        h, m, s = parts
                    elif len(parts) == 2:
                        h = 0
                        m, s = parts
                    else:
                        h = m = 0
                        s = parts[0]
                    total = h * 3600 + m * 60 + s
                else:
                    total = float(seconds_val)
            else:
                total = float(seconds_val)
        except Exception:
            total = 0.0

        ms = int(round(total * 1000))
        hh = ms // 3600000
        mm = (ms % 3600000) // 60000
        ss = (ms % 60000) // 1000
        mmm = ms % 1000
        return f"{hh:02d}:{mm:02d}:{ss:02d},{mmm:03d}"

    def _write_srt(self, alignment, srt_path):
        import unicodedata

        def to_float(v, default=None):
            try:
                return float(v)
            except Exception:
                return default

        def is_combining_mark(ch):
            cat = unicodedata.category(ch)
            return cat.startswith("M")

        def grapheme_clusters(chars_list):
            clusters = []
            i = 0
            while i < len(chars_list):
                cluster_text = chars_list[i]["char"]
                cluster_start = chars_list[i]["start"]
                cluster_end = chars_list[i]["end"]
                j = i + 1
                while j < len(chars_list) and is_combining_mark(chars_list[j]["char"]):
                    cluster_text += chars_list[j]["char"]
                    cluster_end = chars_list[j]["end"]
                    j += 1
                clusters.append({"text": cluster_text, "start": cluster_start, "end": cluster_end})
                i = j
            return clusters

        norm = alignment.get("normalized_alignment") if isinstance(alignment, dict) else alignment
        entries = []
        idx = 1

        if isinstance(norm, dict) and "characters" in norm:
            chars = norm.get("characters", [])
            starts = norm.get("character_start_times_seconds", norm.get("character_start_times", []))
            ends = norm.get("character_end_times_seconds", norm.get("character_end_times", []))
            char_items = []
            for i, ch in enumerate(chars):
                st = to_float(starts[i]) if i < len(starts) else None
                ed = to_float(ends[i]) if i < len(ends) else None
                char_items.append({"char": ch, "start": st, "end": ed})

            clusters = grapheme_clusters(char_items)
            text = alignment.get("text", "") if isinstance(alignment, dict) else ""
            lines = text.split("\n") if text else [text]
            cluster_idx = 0
            for line in lines:
                if not line.strip():
                    continue
                line_text = []
                line_start = None
                line_end = None
                for ch in line:
                    if is_combining_mark(ch):
                        continue
                    if ch.isspace() or (ch in "，。！？,!?.;；、\"'()（）"):
                        line_text.append(ch)
                        continue
                    if cluster_idx < len(clusters):
                        cluster = clusters[cluster_idx]
                        line_text.append(cluster["text"])
                        if line_start is None:
                            line_start = cluster["start"]
                        line_end = cluster["end"]
                        cluster_idx += 1
                    else:
                        line_text.append(ch)
                        if line_start is None:
                            line_start = 0.0
                        line_end = (line_start or 0.0) + 0.05
                text_line = "".join(line_text).strip()
                if not text_line:
                    continue
                if line_start is None:
                    line_start = 0.0
                if line_end is None:
                    line_end = line_start + 0.8
                start_ts = self._format_timestamp(line_start)
                end_ts = self._format_timestamp(line_end)
                entries.append((idx, start_ts, end_ts, text_line))
                idx += 1
        else:
            text = alignment.get("text", "") if isinstance(alignment, dict) else (alignment or "")
            lines = text.split("\n") if text else [text]
            for line in lines:
                text_line = line.strip()
                if not text_line:
                    continue
                start_ts = self._format_timestamp(0.0)
                end_ts = self._format_timestamp(5.0)
                entries.append((idx, start_ts, end_ts, text_line))
                idx += 1

        if not entries:
            entries = [(1, "00:00:00,000", "00:00:05,000", (alignment or "")[:200])]

        with open(srt_path, "w", encoding="utf-8") as fh:
            for i, start_ts, end_ts, text_str in entries:
                fh.write(f"{i}\n{start_ts} --> {end_ts}\n{text_str}\n\n")


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
        url = "https://api.elevenlabs.io/v1/audio-generation"
        headers = {"Accept": "audio/wav", "Content-Type": "application/json", "xi-api-key": self.api_key}
        data = {"prompt": self.prompt, "duration_seconds": self.duration, "model_id": "eleven_turbo_v2", "output_format": self.output_format}
        try:
            response = requests.post(url, json=data, headers=headers, timeout=120)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(self.save_path) or ".", exist_ok=True)
                with open(self.save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                self.finished.emit(self.save_path)
            else:
                self.error.emit(f"SFX 生成失败 ({response.status_code}): {response.text}")
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
