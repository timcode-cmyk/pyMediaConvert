import os
import datetime
import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox, QMessageBox, QProgressBar, QFileDialog, QGroupBox)
from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from pyMediaConvert.elevenlabs.backend import QuotaWorker, TTSWorker, SFXWorker, VoiceListWorker


class ElevenLabsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_audio_path = None
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.setup_ui()

    def setup_ui(self):
        central_widget = self
        main_layout = QVBoxLayout(central_widget)

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

        self.quota_label = QLabel("额度: 正在加载...")
        self.quota_bar = QProgressBar()
        self.quota_bar.setTextVisible(True)
        top_layout.addWidget(self.quota_label)
        top_layout.addWidget(self.quota_bar)
        main_layout.addWidget(top_bar)

        self.tabs_box = QGroupBox()
        tabs_layout = QVBoxLayout(self.tabs_box)
        # We'll implement simple TTS and SFX areas inline to keep the widget self-contained

        # TTS area
        self.combo_voices = QComboBox()
        self.tts_text_input = QTextEdit()
        self.tts_save_input = QLineEdit(f"tts_{datetime.date.today()}_{str(uuid.uuid4())[:4]}.mp3")
        self.btn_tts_browse = QPushButton("选择保存路径...")
        self.btn_tts_browse.clicked.connect(lambda: self.browse_save_path(self.tts_save_input, "WAV Audio (*.mp3)"))
        self.btn_tts_generate = QPushButton("生成 TTS 语音 (44.1kHz mp3)")
        self.btn_tts_generate.clicked.connect(self.generate_tts_audio)

        tts_layout = QVBoxLayout()
        voice_layout = QHBoxLayout()
        voice_layout.addWidget(QLabel("选择声音:"))
        voice_layout.addWidget(self.combo_voices, 1)
        tts_layout.addLayout(voice_layout)
        tts_layout.addWidget(QLabel("输入文本:"))
        tts_layout.addWidget(self.tts_text_input)
        save_layout = QHBoxLayout()
        save_layout.addWidget(QLabel("保存到:"))
        save_layout.addWidget(self.tts_save_input)
        save_layout.addWidget(self.btn_tts_browse)
        tts_layout.addLayout(save_layout)
        tts_layout.addWidget(self.btn_tts_generate)

        # SFX area
        self.sfx_prompt_input = QTextEdit()
        self.sfx_duration_input = None
        from PySide6.QtWidgets import QSpinBox
        self.sfx_duration_input = QSpinBox()
        self.sfx_duration_input.setRange(1, 10)
        self.sfx_duration_input.setValue(5)
        self.sfx_save_input = QLineEdit(f"sfx_{datetime.date.today()}.mp3")
        self.btn_sfx_browse = QPushButton("选择保存路径...")
        self.btn_sfx_browse.clicked.connect(lambda: self.browse_save_path(self.sfx_save_input, "WAV Audio (*.mp3)"))
        self.btn_sfx_generate = QPushButton("生成 SFX 音效")
        self.btn_sfx_generate.clicked.connect(self.generate_sfx_audio)

        sfx_layout = QVBoxLayout()
        sfx_layout.addWidget(QLabel("音效描述:"))
        sfx_layout.addWidget(self.sfx_prompt_input)
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("时长 (秒, 1-10):"))
        duration_layout.addWidget(self.sfx_duration_input)
        duration_layout.addStretch(1)
        sfx_layout.addLayout(duration_layout)
        save_layout2 = QHBoxLayout()
        save_layout2.addWidget(QLabel("保存到:"))
        save_layout2.addWidget(self.sfx_save_input)
        save_layout2.addWidget(self.btn_sfx_browse)
        sfx_layout.addLayout(save_layout2)
        sfx_layout.addWidget(self.btn_sfx_generate)

        tabs_layout.addLayout(tts_layout)
        tabs_layout.addLayout(sfx_layout)

        main_layout.addWidget(self.tabs_box)

        # Bottom controls
        bottom_layout = QHBoxLayout()
        self.btn_play = QPushButton("播放")
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self.play_audio)
        self.lbl_status = QLabel("就绪")
        bottom_layout.addWidget(self.btn_play)
        bottom_layout.addWidget(self.lbl_status, 1)
        main_layout.addLayout(bottom_layout)

    def browse_save_path(self, line_edit, filter_str):
        initial_path = line_edit.text()
        fname, _ = QFileDialog.getSaveFileName(self, "选择保存路径", initial_path, filter_str)
        if fname:
            line_edit.setText(fname)

    def load_voices(self):
        api_key = self.key_input.text().strip()
        if not api_key:
            self.lbl_status.setText("请输入 API Key")
            return
        self.set_ui_busy(True, "正在加载声音和额度...")
        self.voice_worker = VoiceListWorker(api_key)
        self.voice_worker.finished.connect(self.on_voices_loaded)
        self.voice_worker.error.connect(self.on_error)
        self.voice_worker.start()
        self.quota_worker = QuotaWorker(api_key)
        self.quota_worker.quota_info.connect(self.on_quota_loaded)
        self.quota_worker.error.connect(self.on_error)
        self.quota_worker.start()

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

    def on_generation_success(self, file_path):
        self.set_ui_busy(False, f"生成成功! 文件保存至: {os.path.basename(file_path)}")
        self.current_audio_path = file_path
        self.btn_play.setEnabled(True)
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.play()

    def on_error(self, error_msg):
        self.set_ui_busy(False, "发生错误")
        QMessageBox.critical(self, "错误", error_msg)

    def set_ui_busy(self, is_busy, status_text=""):
        widgets = [getattr(self, 'btn_load_voices', None), getattr(self, 'btn_tts_generate', None), getattr(self, 'btn_sfx_generate', None), self.tts_text_input, self.sfx_prompt_input]
        for widget in widgets:
            if widget:
                widget.setEnabled(not is_busy)
        self.lbl_status.setText(status_text)
        if is_busy:
            self.btn_play.setEnabled(False)

    def play_audio(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.btn_play.setText("继续播放")
        else:
            self.player.play()
            self.btn_play.setText("暂停播放")
