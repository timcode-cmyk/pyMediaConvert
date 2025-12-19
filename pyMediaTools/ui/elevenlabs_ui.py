import os
import datetime
import uuid
import platform
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QTextEdit, QComboBox, QMessageBox, QProgressBar, QFileDialog, 
                               QGroupBox, QSizePolicy, QSpinBox, QApplication)
from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from pyMediaConvert.elevenlabs.backend import QuotaWorker, TTSWorker, SFXWorker, VoiceListWorker
from pyMediaConvert.logging_config import get_logger

logger = get_logger(__name__)


class ElevenLabsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_audio_path = None
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.setup_ui()
        self.apply_styles()

    def apply_styles(self):
        """
        统一的现代化样式表，与 ConverterWidget 风格保持一致
        """
        app = QApplication.instance()
        palette = app.palette()
        
        accent_color = palette.color(QPalette.Highlight).name()
        
        bg_color = palette.color(QPalette.Window)
        is_dark = bg_color.lightness() < 128
        
        input_bg = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(0, 0, 0, 0.03)"
        border_color = "rgba(255, 255, 255, 0.15)" if is_dark else "rgba(0, 0, 0, 0.15)"
        group_bg = "rgba(255, 255, 255, 0.03)" if is_dark else "rgba(255, 255, 255, 0.6)"
        
        sys_name = platform.system()
        base_font = "Segoe UI" if sys_name == 'Windows' else "SF Pro Text" if sys_name == 'Darwin' else "Roboto"

        style = f"""
            QWidget {{
                font-family: "{base_font}", sans-serif;
                font-size: 14px;
                color: palette(text);
            }}
            
            QGroupBox {{
                background-color: {group_bg};
                border: 1px solid {border_color};
                border-radius: 8px;
                margin-top: 1.2em;
                padding: 15px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                padding: 0 5px;
                left: 10px;
                font-weight: bold;
                color: {accent_color};
            }}

            QLineEdit, QComboBox, QSpinBox, QTextEdit {{
                background-color: {input_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 8px;
                selection-background-color: {accent_color};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {accent_color};
            }}
            
            QPushButton {{
                background-color: {input_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {accent_color};
                color: white;
                border: 1px solid {accent_color};
            }}
            QPushButton#PrimaryButton {{
                background-color: {accent_color};
                color: white;
                border: none;
                padding: 10px;
                font-size: 15px;
            }}
            QPushButton#PrimaryButton:hover {{
                background-color: palette(link-visited);
            }}

            QProgressBar {{
                border: none;
                background-color: {input_bg};
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {accent_color};
                border-radius: 4px;
            }}
            
            /* 状态栏区域 */
            #BottomPanel {{
                background-color: {group_bg};
                border-radius: 8px;
                padding: 10px;
            }}
        """
        self.setStyleSheet(style)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 标题
        title = QLabel("ElevenLabs 语音合成")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        main_layout.addWidget(title)

        # 1. API 配置区
        top_bar = QGroupBox("API 配置")
        top_layout = QVBoxLayout(top_bar)
        
        key_layout = QHBoxLayout()
        key_label = QLabel("API Key:")
        self.key_input = QLineEdit(os.getenv("ELEVENLABS_API_KEY", ""))
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("sk-...")
        self.key_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.btn_load_voices = QPushButton("🔄 刷新配置")
        self.btn_load_voices.setToolTip("验证 Key 并获取声音列表和额度")
        self.btn_load_voices.clicked.connect(self.load_voices)

        key_layout.addWidget(key_label)
        key_layout.addWidget(self.key_input)
        key_layout.addWidget(self.btn_load_voices)
        
        # 额度展示
        quota_layout = QHBoxLayout()
        self.quota_label = QLabel("额度使用情况:")
        self.quota_bar = QProgressBar()
        self.quota_bar.setTextVisible(False) # 扁平化，不显示文字在条上
        self.quota_text_val = QLabel("-- / --")
        
        quota_layout.addWidget(self.quota_label)
        quota_layout.addWidget(self.quota_bar)
        quota_layout.addWidget(self.quota_text_val)
        
        top_layout.addLayout(key_layout)
        top_layout.addLayout(quota_layout)
        main_layout.addWidget(top_bar)

        # 2. 功能区 (TTS 和 SFX)
        self.tabs_box = QGroupBox("生成功能")
        tabs_layout = QVBoxLayout(self.tabs_box)
        tabs_layout.setSpacing(20)

        # --- TTS 区域 ---
        tts_group = QWidget() # 使用 Widget 做内部容器
        tts_inner_layout = QVBoxLayout(tts_group)
        tts_inner_layout.setContentsMargins(0,0,0,0)
        
        tts_header = QLabel("🗣️ 文本转语音 (TTS)")
        tts_header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        tts_inner_layout.addWidget(tts_header)

        # 声音选择
        voice_layout = QHBoxLayout()
        voice_layout.addWidget(QLabel("选择声音模型:"))
        self.combo_voices = QComboBox()
        self.combo_voices.setPlaceholderText("请先刷新配置...")
        voice_layout.addWidget(self.combo_voices, 1)
        tts_inner_layout.addLayout(voice_layout)

        # 文本输入
        self.tts_text_input = QTextEdit()
        self.tts_text_input.setPlaceholderText("请输入要转换的文本内容...")
        self.tts_text_input.setMaximumHeight(100)
        tts_inner_layout.addWidget(self.tts_text_input)

        # 保存与生成
        tts_action_layout = QHBoxLayout()
        self.tts_save_input = QLineEdit(self._generate_filename("tts"))
        self.btn_tts_browse = QPushButton("...")
        self.btn_tts_browse.setFixedWidth(40)
        self.btn_tts_browse.clicked.connect(lambda: self.browse_save_path(self.tts_save_input, "Audio (*.mp3)"))
        
        self.btn_tts_generate = QPushButton("生成语音")
        self.btn_tts_generate.setObjectName("PrimaryButton")
        self.btn_tts_generate.clicked.connect(self.generate_tts_audio)
        
        tts_action_layout.addWidget(QLabel("保存至:"))
        tts_action_layout.addWidget(self.tts_save_input)
        tts_action_layout.addWidget(self.btn_tts_browse)
        tts_action_layout.addWidget(self.btn_tts_generate)
        tts_inner_layout.addLayout(tts_action_layout)
        
        tabs_layout.addWidget(tts_group)
        
        # 分割线
        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: rgba(128,128,128,0.3);")
        tabs_layout.addWidget(line)

        # --- SFX 区域 ---
        sfx_group = QWidget()
        sfx_inner_layout = QVBoxLayout(sfx_group)
        sfx_inner_layout.setContentsMargins(0,0,0,0)
        
        sfx_header = QLabel("🎵 音效生成 (SFX)")
        sfx_header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        sfx_inner_layout.addWidget(sfx_header)

        # 提示词与时长
        sfx_input_layout = QHBoxLayout()
        self.sfx_prompt_input = QTextEdit()
        self.sfx_prompt_input.setPlaceholderText("描述音效，例如: footsteps on wood floor...")
        self.sfx_prompt_input.setMaximumHeight(60)
        
        sfx_ctrl_layout = QVBoxLayout()
        self.sfx_duration_input = QSpinBox()
        self.sfx_duration_input.setRange(1, 22) # ElevenLabs 通常限制较短
        self.sfx_duration_input.setValue(5)
        self.sfx_duration_input.setSuffix(" 秒")
        sfx_ctrl_layout.addWidget(QLabel("时长:"))
        sfx_ctrl_layout.addWidget(self.sfx_duration_input)
        sfx_ctrl_layout.addStretch()

        sfx_input_layout.addWidget(self.sfx_prompt_input, 1)
        sfx_input_layout.addLayout(sfx_ctrl_layout)
        sfx_inner_layout.addLayout(sfx_input_layout)

        # 保存与生成
        sfx_action_layout = QHBoxLayout()
        self.sfx_save_input = QLineEdit(self._generate_filename("sfx"))
        self.btn_sfx_browse = QPushButton("...")
        self.btn_sfx_browse.setFixedWidth(40)
        self.btn_sfx_browse.clicked.connect(lambda: self.browse_save_path(self.sfx_save_input, "Audio (*.mp3)"))
        
        self.btn_sfx_generate = QPushButton("生成音效")
        self.btn_sfx_generate.setObjectName("PrimaryButton")
        self.btn_sfx_generate.clicked.connect(self.generate_sfx_audio)

        sfx_action_layout.addWidget(QLabel("保存至:"))
        sfx_action_layout.addWidget(self.sfx_save_input)
        sfx_action_layout.addWidget(self.btn_sfx_browse)
        sfx_action_layout.addWidget(self.btn_sfx_generate)
        sfx_inner_layout.addLayout(sfx_action_layout)

        tabs_layout.addWidget(sfx_group)
        main_layout.addWidget(self.tabs_box)

        # 3. 底部播放控制条
        bottom_panel = QWidget()
        bottom_panel.setObjectName("BottomPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(10, 5, 10, 5)
        
        self.btn_play = QPushButton("▶ 播放")
        self.btn_play.setEnabled(False)
        self.btn_play.setFixedWidth(80)
        self.btn_play.clicked.connect(self.play_audio)
        
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setStyleSheet("color: palette(mid); font-style: italic;")
        
        bottom_layout.addWidget(self.btn_play)
        bottom_layout.addWidget(self.lbl_status, 1)
        main_layout.addWidget(bottom_panel)

    def _generate_filename(self, prefix):
        return f"{prefix}_{datetime.date.today()}_{str(uuid.uuid4())[:4]}.mp3"

    def browse_save_path(self, line_edit, filter_str):
        initial_path = line_edit.text()
        fname, _ = QFileDialog.getSaveFileName(self, "选择保存路径", initial_path, filter_str)
        if fname:
            line_edit.setText(fname)

    def load_voices(self):
        api_key = self.key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "缺少 Key", "请输入 API Key")
            return
        self.set_ui_busy(True, "正在连接 ElevenLabs...")
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

    def on_quota_loaded(self, usage, limit):
        if limit == 0:
            percent = 0
            text = "0 / 0"
        else:
            percent = int((usage / limit) * 100)
            text = f"{usage} / {limit}"
            
        self.quota_bar.setValue(percent)
        self.quota_text_val.setText(f"{text} ({percent}%)")
        
        if percent > 90:
            self.quota_bar.setStyleSheet("QProgressBar::chunk { background-color: #ef4444; }")
        else:
            # 重置样式以使用默认的高亮色
            self.quota_bar.setStyleSheet("")

    def generate_tts_audio(self):
        text = self.tts_text_input.toPlainText().strip()
        save_path = self.tts_save_input.text().strip()
        voice_id = self.combo_voices.itemData(self.combo_voices.currentIndex())
        api_key = self.key_input.text().strip()
        
        if not voice_id:
             QMessageBox.warning(self, "提示", "请先加载并选择一个声音模型。")
             return
        if not text:
            QMessageBox.warning(self, "提示", "请输入要转换的文本。")
            return

        self.set_ui_busy(True, "正在生成语音...")
        self.tts_worker = TTSWorker(api_key, voice_id, text, save_path)
        self.tts_worker.finished.connect(self.on_generation_success)
        self.tts_worker.error.connect(self.on_error)
        self.tts_worker.start()

    def generate_sfx_audio(self):
        prompt = self.sfx_prompt_input.toPlainText().strip()
        duration = self.sfx_duration_input.value()
        save_path = self.sfx_save_input.text().strip()
        api_key = self.key_input.text().strip()
        
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入音效描述。")
            return

        self.set_ui_busy(True, "正在生成音效...")
        self.sfx_worker = SFXWorker(api_key, prompt, duration, save_path)
        self.sfx_worker.finished.connect(self.on_generation_success)
        self.sfx_worker.error.connect(self.on_error)
        self.sfx_worker.start()

    def on_generation_success(self, file_path):
        self.set_ui_busy(False, "生成成功!")
        self.current_audio_path = file_path
        self.btn_play.setEnabled(True)
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.lbl_status.setText(f"已保存: {os.path.basename(file_path)}")
        
        # 自动刷新文件名以防覆盖
        if "tts" in os.path.basename(file_path):
            self.tts_save_input.setText(self._generate_filename("tts"))
        else:
            self.sfx_save_input.setText(self._generate_filename("sfx"))

    def on_error(self, error_msg):
        self.set_ui_busy(False, "发生错误")
        QMessageBox.critical(self, "API 错误", str(error_msg))

    def set_ui_busy(self, is_busy, status_text=""):
        # 禁用交互组件
        self.btn_load_voices.setEnabled(not is_busy)
        self.btn_tts_generate.setEnabled(not is_busy)
        self.btn_sfx_generate.setEnabled(not is_busy)
        self.combo_voices.setEnabled(not is_busy)
        self.tts_text_input.setEnabled(not is_busy)
        
        self.lbl_status.setText(status_text)
        if is_busy:
            self.btn_play.setEnabled(False)
            self.setCursor(Qt.WaitCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def play_audio(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.btn_play.setText("▶ 继续")
        else:
            self.player.play()
            self.btn_play.setText("⏸ 暂停")

    # 监听播放结束，重置按钮文字
    def _on_player_state_changed(self, state):
        if state == QMediaPlayer.StoppedState:
            self.btn_play.setText("▶ 播放")