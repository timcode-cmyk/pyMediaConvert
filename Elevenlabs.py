import sys
import os
import requests
import json
import base64
import datetime
import uuid

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QTextEdit, QComboBox, QMessageBox, QProgressBar, 
                               QFileDialog, QTabWidget, QSpinBox, QGroupBox)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# --- 辅助类：API Worker Threads ---

class QuotaWorker(QThread):
    """用于获取用户剩余额度的线程"""
    quota_info = Signal(int, int) # (usage, limit)
    error = Signal(str)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        url = "https://api.elevenlabs.io/v1/user"
        headers = {"xi-api-key": self.api_key}
        
        try:
            response = requests.get(url, headers=headers)
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
    """用于生成语音（Text-to-Speech）的线程，生成音频并可同时保存对齐数据为 SRT 字幕"""
    finished = Signal(str)  # 返回保存的文件路径
    error = Signal(str)

    def __init__(self, api_key, voice_id, text, save_path):
        super().__init__()
        self.api_key = api_key
        self.voice_id = voice_id
        self.text = text
        self.save_path = save_path
        # 建议使用 PCM 采样格式标签（与服务器协商），此处保持原值
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

            # 情况 A: 返回 JSON（包含 base64 音频 + alignment）
            if "application/json" in content_type or response.text.strip().startswith("{"):
                try:
                    resp_json = response.json()
                except Exception:
                    self.error.emit("无法解析 TTS 返回的 JSON。")
                    return

                # 常见字段名兼容
                audio_b64 = resp_json.get("audio") or resp_json.get("audio_base64") or resp_json.get("audioBytes")
                if isinstance(audio_b64, str) and audio_b64.strip():
                    try:
                        audio_bytes = base64.b64decode(audio_b64)
                    except Exception:
                        self.error.emit("无法解码返回的音频 base64 数据。")
                        return

                # alignment 可能在多个字段名下
                alignment = resp_json.get("alignment") or resp_json.get("timestamps") or resp_json.get("words") or resp_json.get("segments")

            # 情况 B: 直接返回音频二进制（可能没有 alignment）
            elif "audio/" in content_type or "application/octet-stream" in content_type:
                audio_bytes = response.content
                # 如果服务器同时返回 alignment，通常会随 JSON 一并返回；二进制响应通常没有 alignment
                alignment = None
            else:
                # 兜底：尝试解析为 JSON first，然后回退到二进制
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

            # 写入音频文件
            try:
                # 确保目录存在
                os.makedirs(os.path.dirname(self.save_path) or ".", exist_ok=True)
                with open(self.save_path, "wb") as f:
                    f.write(audio_bytes)
            except Exception as e:
                self.error.emit(f"保存音频失败: {str(e)}")
                return

            # 若有 alignment 数据，则生成 SRT 文件（路径与 wav 同名，扩展名 .srt）
            if alignment:
                srt_path = os.path.splitext(self.save_path)[0] + ".srt"
                try:
                    self._write_srt(alignment, srt_path)
                except Exception as e:
                    # SRT 生成失败不影响音频文件使用，但记录错误
                    # 这里仅发出错误信息（可根据需要改为警告）
                    self.error.emit(f"SRT 生成失败: {str(e)}")
                    # 仍然继续 emit finished（因为音频已保存）
                    # 注意 UI 上会显示错误弹窗并且仍会播放音频
                    self.finished.emit(self.save_path)
                    return

            # 成功
            self.finished.emit(self.save_path)

        except Exception as e:
            self.error.emit(str(e))

    def _format_timestamp(self, seconds_val):
        """把秒数（float）转换为 SRT 时间格式 HH:MM:SS,mmm"""
        try:
            # 如果传入的是字符串形式的时间戳，尝试转换
            if isinstance(seconds_val, str):
                # 常见格式： "00:00:01.230" 或 "1.23"
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
        """
        将 alignment 数据写为 SRT。
        根据输入文本中的换行符（\n）进行断行，每行一个 SRT 条目。
        对每行内容使用 grapheme cluster 级时间戳进行对齐（解决印地语重音符号的拆分问题）。
        """
        import unicodedata
        import re

        def to_float(v, default=None):
            try:
                return float(v)
            except Exception:
                return default

        def is_combining_mark(ch):
            """检查是否为组合标记（重音符、matras 等）"""
            cat = unicodedata.category(ch)
            return cat.startswith("M")  # Mn, Mc, Me

        def grapheme_clusters(chars_list):
            """
            将 characters 数组转换为 grapheme cluster 列表。
            每个 cluster 包含一个基字符 + 所有后续组合标记。
            返回 [(text, start, end), ...]
            """
            clusters = []
            i = 0
            while i < len(chars_list):
                cluster_text = chars_list[i]["char"]
                cluster_start = chars_list[i]["start"]
                cluster_end = chars_list[i]["end"]

                # 向后收集所有组合标记
                j = i + 1
                while j < len(chars_list) and is_combining_mark(chars_list[j]["char"]):
                    cluster_text += chars_list[j]["char"]
                    cluster_end = chars_list[j]["end"]  # 更新 end 为最后一个 mark 的 end
                    j += 1

                clusters.append({
                    "text": cluster_text,
                    "start": cluster_start,
                    "end": cluster_end
                })
                i = j

            return clusters

        # 优先使用 normalized_alignment
        norm = None
        if isinstance(alignment, dict):
            norm = alignment.get("normalized_alignment") or alignment
        else:
            norm = alignment

        entries = []
        idx = 1

        # 检查是否为字符级对齐数据
        if isinstance(norm, dict) and "characters" in norm and ("character_start_times_seconds" in norm or "character_start_times" in norm):
            chars = norm.get("characters", [])
            starts = norm.get("character_start_times_seconds", norm.get("character_start_times", []))
            ends = norm.get("character_end_times_seconds", norm.get("character_end_times", []))

            # 构造字符项列表
            char_items = []
            for i, ch in enumerate(chars):
                st = to_float(starts[i]) if i < len(starts) else None
                ed = to_float(ends[i]) if i < len(ends) else None
                char_items.append({"char": ch, "start": st, "end": ed})

            # 转换为 grapheme cluster（自动合并重音符号）
            clusters = grapheme_clusters(char_items)

            # 按原始文本的换行符分割
            lines = self.text.split("\n")
            cluster_idx = 0

            for line in lines:
                if not line.strip():
                    continue

                # 为这一行收集 grapheme clusters 及时间戳
                line_text = []
                line_start = None
                line_end = None

                for ch in line:
                    # 跳过组合标记（它们已在 cluster 中处理）
                    if is_combining_mark(ch):
                        continue

                    # 跳过标点和空格（不消耗 cluster）
                    if ch.isspace() or (ch in "，。！？,!?.;；、\"'\"'（）()"):
                        line_text.append(ch)
                        continue

                    # 从 clusters 取对应项
                    if cluster_idx < len(clusters):
                        cluster = clusters[cluster_idx]
                        line_text.append(cluster["text"])
                        if line_start is None:
                            line_start = cluster["start"]
                        line_end = cluster["end"]
                        cluster_idx += 1
                    else:
                        # clusters 用尽，使用原字符（估算时间）
                        line_text.append(ch)
                        if line_start is None:
                            line_start = 0.0
                        line_end = (line_start or 0.0) + 0.05

                text_line = "".join(line_text).strip()
                if not text_line:
                    continue

                # 使用该行首末 cluster 的时间戳
                if line_start is None:
                    line_start = 0.0
                if line_end is None:
                    line_end = line_start + 0.8

                start_ts = self._format_timestamp(line_start)
                end_ts = self._format_timestamp(line_end)
                entries.append((idx, start_ts, end_ts, text_line))
                idx += 1

        else:
            # 回退：若无字符级对齐，则按输入文本的换行分割
            lines = self.text.split("\n")
            for line in lines:
                text_line = line.strip()
                if not text_line:
                    continue
                start_ts = self._format_timestamp(0.0)
                end_ts = self._format_timestamp(5.0)
                entries.append((idx, start_ts, end_ts, text_line))
                idx += 1

        # 如果仍然没有 entries，生成默认单条字幕
        if not entries:
            entries = [(1, "00:00:00,000", "00:00:05,000", (self.text or "")[:200])]

        # 写入 SRT 文件
        with open(srt_path, "w", encoding="utf-8") as fh:
            for i, start_ts, end_ts, text_str in entries:
                fh.write(f"{i}\n{start_ts} --> {end_ts}\n{text_str}\n\n")
class SFXWorker(QThread):
    """用于生成音效（Sound Effects）的线程"""
    finished = Signal(str) # 返回保存的文件路径
    error = Signal(str)

    def __init__(self, api_key, prompt, duration, save_path):
        super().__init__()
        self.api_key = api_key
        self.prompt = prompt
        self.duration = duration
        self.save_path = save_path
        self.output_format = "mp3_44100_128"

    def run(self):
        # 注意：音效 API 地址不同
        url = "https://api.elevenlabs.io/v1/audio-generation" 
        
        headers = {
            "Accept": "audio/wav",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "prompt": self.prompt,
            "duration_seconds": self.duration,
            "model_id": "eleven_turbo_v2",
            "output_format": self.output_format # SFX 专有模型
        }

        try:
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
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
    """
    用于在后台获取声音列表的线程
    """
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
                # 兼容返回格式：{"voices": [...]} 或直接返回列表
                voices_list = []
                if isinstance(data, dict) and "voices" in data:
                    raw = data["voices"]
                elif isinstance(data, list):
                    raw = data
                else:
                    raw = []

                for v in raw:
                    # 尝试使用常见字段名
                    vid = v.get("voice_id") or v.get("id") or v.get("uuid")
                    name = v.get("name") or v.get("label") or vid
                    if vid and name:
                        voices_list.append((name, vid))

                self.finished.emit(voices_list)
            else:
                self.error.emit(f"获取声音列表失败 ({response.status_code}): {response.text}")
        except Exception as e:
            self.error.emit(str(e))
# --- 主界面类 ---

class ElevenLabsGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ElevenLabs 专业版生成器")
        self.resize(700, 600)
        self.current_audio_path = None
        
        # 音频播放器设置
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.setup_ui()
        self.load_voices() # 启动时自动加载声音和额度

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 1. 顶部：API Key 和 Quota 显示
        top_bar = QGroupBox("API 设置与额度")
        top_layout = QVBoxLayout(top_bar)
        
        key_layout = QHBoxLayout()
        self.key_input = QLineEdit(os.getenv("ELEVENLABS_API_KEY", ""))
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("在此粘贴 API Key")
        self.btn_load_voices = QPushButton("刷新声音/额度")
        self.btn_load_voices.clicked.connect(self.load_voices)
        
        key_layout.addWidget(QLabel("Key:"))
        key_layout.addWidget(self.key_input)
        key_layout.addWidget(self.btn_load_voices)
        top_layout.addLayout(key_layout)

        # 额度显示
        self.quota_label = QLabel("额度: 正在加载...")
        self.quota_bar = QProgressBar()
        self.quota_bar.setTextVisible(True)
        top_layout.addWidget(self.quota_label)
        top_layout.addWidget(self.quota_bar)
        main_layout.addWidget(top_bar)

        # 2. Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_tts_tab(), "文本转语音 (TTS)")
        self.tabs.addTab(self.create_sfx_tab(), "音效生成 (SFX)")
        main_layout.addWidget(self.tabs)

        # 3. 底部：状态和播放
        bottom_group = QGroupBox("控制台")
        bottom_layout = QHBoxLayout(bottom_group)
        self.btn_play = QPushButton("播放")
        self.btn_play.clicked.connect(self.play_audio)
        self.btn_play.setEnabled(False)
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        
        bottom_layout.addWidget(self.btn_play)
        bottom_layout.addWidget(self.lbl_status, 1)
        main_layout.addWidget(bottom_group)

    def create_tts_tab(self):
        tts_widget = QWidget()
        layout = QVBoxLayout(tts_widget)
        today = datetime.date.today()
        chair = uuid.uuid4()
        four_chair = str(chair)[:4]
        # 声音选择
        voice_layout = QHBoxLayout()
        self.combo_voices = QComboBox()
        voice_layout.addWidget(QLabel("选择声音:"))
        voice_layout.addWidget(self.combo_voices, 1)
        layout.addLayout(voice_layout)

        # 文本输入
        layout.addWidget(QLabel("输入文本:"))
        self.tts_text_input = QTextEdit()
        self.tts_text_input.setPlaceholderText("请输入要转换的文本...")
        layout.addWidget(self.tts_text_input)
        
        # 文件保存路径
        save_layout = QHBoxLayout()
        self.tts_save_input = QLineEdit(f"tts_{today}_{four_chair}.mp3")
        self.btn_tts_browse = QPushButton("选择保存路径...")
        self.btn_tts_browse.clicked.connect(lambda: self.browse_save_path(self.tts_save_input, "WAV Audio (*.mp3)"))
        
        save_layout.addWidget(QLabel("保存到:"))
        save_layout.addWidget(self.tts_save_input)
        save_layout.addWidget(self.btn_tts_browse)
        layout.addLayout(save_layout)
        
        # 生成按钮
        self.btn_tts_generate = QPushButton("生成 TTS 语音 (44.1kHz mp3)")
        self.btn_tts_generate.setMinimumHeight(35)
        self.btn_tts_generate.clicked.connect(self.generate_tts_audio)
        self.btn_tts_generate.setEnabled(False)
        
        layout.addWidget(self.btn_tts_generate)
        return tts_widget

    def create_sfx_tab(self):
        sfx_widget = QWidget()
        layout = QVBoxLayout(sfx_widget)
        today = datetime.date.today()
        # Prompt 输入
        self.sfx_prompt_input = QTextEdit()
        self.sfx_prompt_input.setPlaceholderText("请输入音效描述 (例如: '一辆跑车加速驶过的声音')...")
        layout.addWidget(QLabel("音效描述:"))
        layout.addWidget(self.sfx_prompt_input)

        # Duration 输入
        duration_layout = QHBoxLayout()
        self.sfx_duration_input = QSpinBox()
        self.sfx_duration_input.setRange(1, 10) # 1到10秒
        self.sfx_duration_input.setValue(5)
        duration_layout.addWidget(QLabel("时长 (秒, 1-10):"))
        duration_layout.addWidget(self.sfx_duration_input)
        duration_layout.addStretch(1)
        layout.addLayout(duration_layout)

        # 文件保存路径
        save_layout = QHBoxLayout()
        self.sfx_save_input = QLineEdit(f"sfx_{today}.mp3")
        self.btn_sfx_browse = QPushButton("选择保存路径...")
        self.btn_sfx_browse.clicked.connect(lambda: self.browse_save_path(self.sfx_save_input, "WAV Audio (*.mp3)"))
        
        save_layout.addWidget(QLabel("保存到:"))
        save_layout.addWidget(self.sfx_save_input)
        save_layout.addWidget(self.btn_sfx_browse)
        layout.addLayout(save_layout)

        # 生成按钮
        self.btn_sfx_generate = QPushButton("生成 SFX 音效")
        self.btn_sfx_generate.setMinimumHeight(35)
        self.btn_sfx_generate.clicked.connect(self.generate_sfx_audio)
        self.btn_sfx_generate.setEnabled(False)
        
        layout.addWidget(self.btn_sfx_generate)
        layout.addStretch(1)
        return sfx_widget

    # --- 核心逻辑：加载与生成 ---
    
    def load_voices(self):
        """刷新声音列表和用户额度"""
        api_key = self.key_input.text().strip()
        if not api_key:
            self.lbl_status.setText("请输入 API Key")
            return

        self.set_ui_busy(True, "正在加载声音和额度...")
        
        # 1. 声音列表加载
        self.voice_worker = VoiceListWorker(api_key)
        self.voice_worker.finished.connect(self.on_voices_loaded)
        self.voice_worker.error.connect(self.on_error)
        self.voice_worker.start()
        QApplication.processEvents()

        # 2. 额度加载
        self.quota_worker = QuotaWorker(api_key)
        self.quota_worker.quota_info.connect(self.on_quota_loaded)
        self.quota_worker.error.connect(self.on_error)
        self.quota_worker.start()
        QApplication.processEvents()

    def on_voices_loaded(self, voices):
        self.set_ui_busy(False, f"已加载 {len(voices)} 个声音模型")
        self.combo_voices.clear()
        
        for name, vid in voices:
            self.combo_voices.addItem(name, vid) 
        
        self.btn_tts_generate.setEnabled(True)
        self.btn_sfx_generate.setEnabled(True)


    def on_quota_loaded(self, usage, limit):
        if limit == 0:
            percent_remaining = 0
            percent_used = 100
        else:
            percent_used = (usage / limit) * 100
            percent_remaining = 100 - percent_used

        self.quota_label.setText(f"字符额度: 已用 {usage} / 总额 {limit} (剩余 {percent_remaining:.1f}%)")
        self.quota_bar.setRange(0, limit)
        self.quota_bar.setValue(usage)
        
        # 额度用尽警告
        if percent_remaining < 5:
            self.quota_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.quota_label.setStyleSheet("")


    def generate_tts_audio(self):
        text = self.tts_text_input.toPlainText().strip()
        save_path = self.tts_save_input.text().strip()
        voice_id = self.combo_voices.itemData(self.combo_voices.currentIndex())
        api_key = self.key_input.text().strip()

        if not all([text, save_path, voice_id]):
            QMessageBox.warning(self, "警告", "请确保文本、保存路径和声音都已选择。")
            return

        self.set_ui_busy(True, "正在生成 TTS 语音...")
        
        self.tts_worker = TTSWorker(api_key, voice_id, text, save_path)
        self.tts_worker.finished.connect(self.on_generation_success)
        self.tts_worker.error.connect(self.on_error)
        self.tts_worker.start()

    def generate_sfx_audio(self):
        prompt = self.sfx_prompt_input.toPlainText().strip()
        duration = self.sfx_duration_input.value()
        save_path = self.sfx_save_input.text().strip()
        api_key = self.key_input.text().strip()

        if not all([prompt, save_path]):
            QMessageBox.warning(self, "警告", "请确保输入音效描述和保存路径。")
            return

        self.set_ui_busy(True, "正在生成 SFX 音效...")

        self.sfx_worker = SFXWorker(api_key, prompt, duration, save_path)
        self.sfx_worker.finished.connect(self.on_generation_success)
        self.sfx_worker.error.connect(self.on_error)
        self.sfx_worker.start()


    # --- 通用 UI 和辅助函数 ---

    def browse_save_path(self, line_edit, filter_str):
        """打开文件对话框选择保存路径"""
        initial_path = line_edit.text()
        fname, _ = QFileDialog.getSaveFileName(self, "选择保存路径", initial_path, filter_str)
        if fname:
            line_edit.setText(fname)

    def on_generation_success(self, file_path):
        self.set_ui_busy(False, f"生成成功! 文件保存至: {os.path.basename(file_path)}")
        self.current_audio_path = file_path
        self.btn_play.setEnabled(True)
        
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.play()
        
        # 重新加载额度，显示最新的使用情况
        self.load_quota(self.key_input.text().strip()) 

    def load_quota(self, api_key):
        """单独调用额度加载，用于生成后的更新"""
        self.quota_worker = QuotaWorker(api_key)
        self.quota_worker.quota_info.connect(self.on_quota_loaded)
        self.quota_worker.error.connect(self.on_error)
        self.quota_worker.start()

    def on_error(self, error_msg):
        self.set_ui_busy(False, "发生错误")
        QMessageBox.critical(self, "错误", error_msg)

    def set_ui_busy(self, is_busy, status_text=""):
        """设置界面忙碌状态"""
        widgets = [self.btn_load_voices, self.btn_tts_generate, self.btn_sfx_generate, 
                   self.tts_text_input, self.sfx_prompt_input]
        
        for widget in widgets:
            widget.setEnabled(not is_busy)
        
        self.lbl_status.setText(status_text)
        
        # 使用进度条或设置按钮文本
        if is_busy:
            self.tabs.setEnabled(False)
            self.btn_play.setEnabled(False)
        else:
            self.tabs.setEnabled(True)

    def play_audio(self):
        """控制音频播放"""
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.btn_play.setText("继续播放")
        else:
            self.player.play()
            self.btn_play.setText("暂停播放")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ElevenLabsGUI()
    window.show()
    sys.exit(app.exec())