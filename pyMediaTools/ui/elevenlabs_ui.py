import os
import datetime
import uuid
import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTextEdit, QComboBox, QMessageBox, QProgressBar, QFileDialog, QSlider,
                               QGroupBox, QSizePolicy, QSpinBox, QCheckBox, QTabWidget, QScrollArea, QFrame,
                               QFontComboBox, QColorDialog, QDoubleSpinBox, QGridLayout, QDialog, QDialogButtonBox, QInputDialog)
from PySide6.QtCore import Qt, QUrl, QSettings, QTimer, QSize, QRectF, QMimeData, QPoint
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen, QBrush, QFontMetrics, QDrag, QTextCharFormat, QSyntaxHighlighter
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from ..core.elevenlabs import (QuotaWorker, TTSWorker, SFXWorker, VoiceListWorker, 
                               ModelListWorker, LibrarySearchWorker, LibraryAddWorker)
from ..core.groq_analysis import EmotionAnalysisWorker
from ..utils import load_project_config
from .styles import apply_common_style
from ..logging_config import get_logger

# Import extracted components
from .elevenlabs_widgets import (EmotionTagButton, EmotionHighlightTextEdit, 
                                EmotionSyntaxHighlighter, EmotionTagManager, 
                                SubtitlePreviewLabel)
from .elevenlabs_dialogs import (VoiceSettingsDialog, SubtitleSettingsDialog, 
                                VoiceLibraryDialog)

logger = get_logger(__name__)





class ElevenLabsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_audio_path = None
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # ⭐ 新增：存储从API获取的模型信息
        self.models_info = {}  # { model_id: {model_data} }
        self.current_model_features = {  # 当前选择的模型的功能信息
            'can_use_style': True,
            'can_use_speaker_boost': True,
        }
        
        # XML 样式设置字典
        self.xml_styles = {
            'source': {
                'alignment': 'center',
                'fontColor': (1.0, 1.0, 1.0, 1.0),
                'font': 'Arial',
                'fontSize': 50,
                'bold': False,
                'italic': False,
                'strokeColor': (0.0, 0.0, 0.0, 1.0),
                'strokeWidth': 2.0,
                'useStroke': False,
                'lineSpacing': 0,
                'pos': -45,
                'shadowColor': (0.0, 0.0, 0.0, 0.5),
                'shadowOffset': (2, 2),
                'useShadow': True,
                'backgroundColor': (0.0, 0.0, 0.0, 0.0),
                'useBackground': False,
                'backgroundPadding': 0,
            },
            'translate': {
                'alignment': 'center',
                'fontColor': (1.0, 1.0, 1.0, 1.0),
                'font': 'Arial',
                'fontSize': 40,
                'bold': False,
                'italic': False,
                'strokeColor': (0.0, 0.0, 0.0, 1.0),
                'strokeWidth': 2.0,
                'useStroke': True,
                'lineSpacing': 0,
                'pos': -38,
                'shadowColor': (0.0, 0.0, 0.0, 0.5),
                'shadowOffset': (2, 2),
                'useShadow': True,
                'backgroundColor': (0.0, 0.0, 0.0, 0.0),
                'useBackground': True,
                'backgroundPadding': 0,
            },
            'highlight': {
                'alignment': 'center',
                'fontColor': (1.0, 1.0, 0.0, 1.0),
                'font': 'Arial',
                'fontSize': 50,
                'bold': True,
                'italic': False,
                'strokeColor': (0.0, 0.0, 0.0, 1.0),
                'strokeWidth': 2.0,
                'useStroke': False,
                'lineSpacing': 0,
                'pos': -45,
                'shadowColor': (0.0, 0.0, 0.0, 0.5),
                'shadowOffset': (2, 2),
                'useShadow': True,
                'backgroundColor': (0.0, 0.0, 0.0, 0.0),
                'useBackground': False,
                'backgroundPadding': 0,
            }
        }
        
        # 视频设置 (默认竖屏)
        self.video_settings = {
            'fps': 30,
            'width': 1080,
            'height': 1920,
            'srt_pause_threshold': 0.2,  # 停顿阈值
            'srt_max_chars': 40,         # 单行最大字符数
        }
        
        # 语音设定 (默认值)
        self.voice_settings = {
            'stability': 0.5,
            'similarity_boost': 0.75,
            'style': 0.0,
            'use_speaker_boost': True,
            'speed': 1.0
        }
        
        # Groq 设定 (默认值)
        groq_qsettings = QSettings("pyMediaTools", "Groq")
        self.groq_settings = {
            'api_key': groq_qsettings.value("api_key", ""),
            'model': groq_qsettings.value("model", "openai/gpt-oss-120b")
        }
        
        # 尝试从 config.toml 加载默认样式配置
        cfg = load_project_config()
        if 'xml_styles' in cfg and isinstance(cfg['xml_styles'], dict):
            for key, val in cfg['xml_styles'].items():
                if key in self.xml_styles and isinstance(val, dict):
                    self.xml_styles[key].update(val)
        
        # 创建预览标签（用于对话框）
        self.preview_label = SubtitlePreviewLabel()
        self.active_subtitle_dialog = None
        
        self.setup_ui()
        self.apply_styles()
        
        # 1. 程序启动时如有读取到api自动刷新
        #     仅在存在非空 API Key 时执行，并且使用 silent 模式避免
        #     因无效/失效 Key 或网络问题而弹出错误对话框。
        if self.key_input.text().strip():
            self.load_voices(show_errors=False)

    def apply_styles(self):
        apply_common_style(self)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 15)
        main_layout.setSpacing(15)

        # # 标题
        # title = QLabel("ElevenLabs 语音合成")
        # title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        # main_layout.addWidget(title)

        # 1. API 配置区
        top_bar = QGroupBox("API 配置")
        top_layout = QVBoxLayout(top_bar)
        
        key_layout = QHBoxLayout()
        key_label = QLabel("API Key:")
        
        # 初始化设置并加载保存的 Key
        self.settings = QSettings("pyMediaTools", "ElevenLabs")
        saved_key = self.settings.value("api_key", "")
        # 优先级: 环境变量 > 本地保存 > 空
        initial_key = os.getenv("ELEVENLABS_API_KEY", "") or saved_key
        
        self.key_input = QLineEdit(initial_key)
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("sk-...")
        self.key_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.btn_save_key = QPushButton("💾 保存")
        self.btn_save_key.setFixedWidth(80)
        self.btn_save_key.clicked.connect(self.save_api_key)
        
        self.btn_load_voices = QPushButton("🔄 刷新配置")
        self.btn_load_voices.setToolTip("验证 Key 并获取声音列表和额度")
        self.btn_load_voices.clicked.connect(self.load_voices)

        key_layout.addWidget(key_label)
        key_layout.addWidget(self.key_input)
        key_layout.addWidget(self.btn_save_key)
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
        tabs_widget = QTabWidget()

        # --- TTS 区域 ---
        tts_group = QWidget() # 使用 Widget 做内部容器
        tts_inner_layout = QVBoxLayout(tts_group)
        tts_inner_layout.setContentsMargins(10, 15, 10, 10) # 给tab内一些边距
        tts_inner_layout.setSpacing(10)

        # 声音选择
        voice_layout = QHBoxLayout()
        voice_layout.addWidget(QLabel("选择声音:"))
        self.combo_voices = QComboBox()
        self.combo_voices.setPlaceholderText("请先刷新配置...")
        self.combo_voices.activated.connect(self.on_voice_combo_activated)
        voice_layout.addWidget(self.combo_voices, 1)
        # 模型选择
        self.combo_model = QComboBox()
        self.combo_model.setPlaceholderText("正在从 API 加载模型...")
        self.combo_model.setEnabled(False)
        voice_layout.addWidget(self.combo_model, 1)
        # ⭐ 连接模型选择变化信号（加载完成后会启用）
        self.combo_model.currentIndexChanged.connect(self.on_model_changed)
        # voice_layout.addWidget(self.combo_model)

        self.btn_voice_settings = QPushButton("⚙️ 语音设定")
        # self.btn_voice_settings.setFixedWidth(100)
        self.btn_voice_settings.setToolTip("调整语音生成参数")
        self.btn_voice_settings.clicked.connect(self.open_voice_settings)
        voice_layout.addWidget(self.btn_voice_settings)

        self.btn_preview_voice = QPushButton("🔊 试听")
        self.btn_preview_voice.setFixedWidth(80)
        self.btn_preview_voice.setToolTip("播放官方样本 (不消耗额度)")
        self.btn_preview_voice.clicked.connect(self.preview_current_voice)
        voice_layout.addWidget(self.btn_preview_voice)

        tts_inner_layout.addLayout(voice_layout)

        # ⭐ 新增：模型、语言选择
        model_lang_layout = QHBoxLayout()
        # model_lang_layout.setSpacing(10)
        
        # 模型选择
        # model_lang_layout.addWidget(QLabel("选择模型:"))
        # self.combo_model = QComboBox()
        # model_lang_layout.addWidget(self.combo_model, 1)
        # from ..core.elevenlabs import ELEVENLABS_MODELS
        # for model_id, info in ELEVENLABS_MODELS.items():
            # self.combo_model.addItem(f"{info['name']} - {info['description']}", model_id)
        # 默认选择推荐模型
        # for i in range(self.combo_model.count()):
        #     model_id = self.combo_model.itemData(i)
        #     if ELEVENLABS_MODELS[model_id].get('recommended'):
        #         self.combo_model.setCurrentIndex(i)
        #         break
        # # ⭐ 连接模型选择变化信号
        # self.combo_model.currentIndexChanged.connect(self.on_model_changed)
        # model_lang_layout.addWidget(self.combo_model)
        
        # 设置第 3 列可以拉伸，占用剩余空间（保留用于右侧对齐）
        # model_lang_layout.setColumnStretch(3, 1)

        # tts_inner_layout.addLayout(model_lang_layout)

        # ⭐ 新增：情绪/语气 标签管理器（合并并显示在模型选择下一行）
        # 直接放置 EmotionTagManager 到主界面，默认禁用（仅v3模型支持）
        self.emotion_manager = EmotionTagManager(self)
        self.emotion_manager.setEnabled(False)
        tts_inner_layout.addWidget(self.emotion_manager)

        # 文本输入
        # 5. 优化文本输入框，在窗口缩放时自动调节文本框高度
        self.tts_text_input = EmotionHighlightTextEdit()
        self.tts_text_input.setPlaceholderText("请输入文本内容...")
        self.tts_text_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # ⭐ 关联文本编辑框到情绪管理器
        self.emotion_manager.set_text_edit(self.tts_text_input)
        tts_inner_layout.addWidget(self.tts_text_input)

        # 字幕选项
        sub_opts_layout = QHBoxLayout()
        self.chk_translate = QCheckBox("自动翻译 (中)")
        self.chk_word_level = QCheckBox("逐词字幕")
        
        self.lbl_words_per_line = QLabel("每行词数:")
        self.spin_words_per_line = QSpinBox()
        self.spin_words_per_line.setRange(1, 5)
        self.spin_words_per_line.setValue(1)
        self.spin_words_per_line.setEnabled(False)
        self.lbl_words_per_line.setEnabled(False)

        self.chk_export_xml = QCheckBox("导出 XML (DaVinci/FCP)")
        self.chk_keyword_highlight = QCheckBox("高亮关键词")
        # Make highlight dependent on XML export
        self.chk_keyword_highlight.setEnabled(False)
        self.chk_export_xml.toggled.connect(self.chk_keyword_highlight.setEnabled)

        self.chk_word_level.toggled.connect(self.spin_words_per_line.setEnabled)
        self.chk_word_level.toggled.connect(self.lbl_words_per_line.setEnabled)

        sub_opts_layout.addWidget(self.chk_translate)
        sub_opts_layout.addWidget(self.chk_word_level)
        sub_opts_layout.addWidget(self.lbl_words_per_line)
        sub_opts_layout.addWidget(self.spin_words_per_line)
        sub_opts_layout.addWidget(self.chk_export_xml)
        sub_opts_layout.addWidget(self.chk_keyword_highlight)
        
        sub_opts_layout.addStretch()

        # 字幕设置按钮
        self.btn_subtitle_settings = QPushButton("⚙️ 字幕设置")
        self.btn_subtitle_settings.setToolTip("配置 Groq API、模型和 XML 样式")
        self.btn_subtitle_settings.clicked.connect(self.open_subtitle_settings)
        sub_opts_layout.addWidget(self.btn_subtitle_settings)
        
        tts_inner_layout.addLayout(sub_opts_layout)

        # 保存与生成
        tts_action_layout = QHBoxLayout()
        self.tts_save_input = QLineEdit(self._generate_filename("tts"))
        self.btn_tts_browse = QPushButton("...")
        self.btn_tts_browse.setFixedWidth(40)
        self.btn_tts_browse.clicked.connect(lambda: self.browse_save_path(self.tts_save_input, "Audio (*.mp3)"))
        self.btn_tts_default = QPushButton("默认路径")
        # self.btn_tts_default.setFixedWidth(110)
        self.btn_tts_default.clicked.connect(lambda: self.choose_default_save_path(self.tts_save_input))
        
        self.btn_tts_generate = QPushButton("生成语音")
        self.btn_tts_generate.setObjectName("PrimaryButton")
        self.btn_tts_generate.clicked.connect(self.generate_tts_audio)
        
        tts_action_layout.addWidget(QLabel("保存至:"))
        tts_action_layout.addWidget(self.tts_save_input)
        tts_action_layout.addWidget(self.btn_tts_browse)
        tts_action_layout.addWidget(self.btn_tts_default)
        tts_action_layout.addWidget(self.btn_tts_generate)
        tts_inner_layout.addLayout(tts_action_layout)

        # --- SFX 区域 ---
        sfx_group = QWidget()
        sfx_inner_layout = QVBoxLayout(sfx_group)
        sfx_inner_layout.setContentsMargins(10, 15, 10, 10)
        sfx_inner_layout.setSpacing(10)

        # 提示词与时长
        sfx_input_layout = QHBoxLayout()
        self.sfx_prompt_input = QTextEdit()
        self.sfx_prompt_input.setPlaceholderText("描述音效，例如: footsteps on wood floor...")
        
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
        self.btn_sfx_default = QPushButton("默认路径")
        self.btn_sfx_default.setFixedWidth(110)
        self.btn_sfx_default.clicked.connect(lambda: self.choose_default_save_path(self.sfx_save_input))
        
        self.btn_sfx_generate = QPushButton("生成音效")
        self.btn_sfx_generate.setObjectName("PrimaryButton")
        self.btn_sfx_generate.clicked.connect(self.generate_sfx_audio)

        sfx_action_layout.addWidget(QLabel("保存至:"))
        sfx_action_layout.addWidget(self.sfx_save_input)
        sfx_action_layout.addWidget(self.btn_sfx_browse)
        sfx_action_layout.addWidget(self.btn_sfx_default)
        sfx_action_layout.addWidget(self.btn_sfx_generate)
        sfx_inner_layout.addLayout(sfx_action_layout)

        # 如果存在已保存的默认目录，则填充保存路径输入框以便一键生成
        default_dir = self.settings.value("default_save_path", "")
        if default_dir:
            try:
                self.tts_save_input.setText(os.path.join(default_dir, self._generate_filename("tts")))
                self.sfx_save_input.setText(os.path.join(default_dir, self._generate_filename("sfx")))
            except Exception:
                pass
        
        # 将两个功能区添加到 Tab
        tabs_widget.addTab(tts_group, "🗣️ 文本转语音 (TTS)")
        tabs_widget.addTab(sfx_group, "🎵 音效生成 (SFX)")

        main_layout.addWidget(tabs_widget)

        # 3. 底部播放控制条
        bottom_panel = QWidget()
        bottom_panel.setObjectName("BottomPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(10, 5, 10, 5)
        
        self.btn_play = QPushButton("▶ 播放")
        self.btn_play.setEnabled(False)
        self.btn_play.setFixedWidth(80)
        self.btn_play.clicked.connect(self.play_audio)
        
        # 4. 播放按钮可以在右侧增加一个播放条显示时长和实时进度并且可以交互
        self.lbl_current_time = QLabel("00:00")
        self.slider_seek = QSlider(Qt.Orientation.Horizontal)
        self.slider_seek.setRange(0, 0)
        self.slider_seek.setEnabled(False)
        
        # 交互优化：按下暂停更新，释放跳转，拖动/点击更新UI
        self.slider_seek.sliderPressed.connect(self.on_slider_pressed)
        self.slider_seek.sliderReleased.connect(self.on_slider_released)
        self.slider_seek.valueChanged.connect(self.on_slider_value_changed)
        
        self.lbl_total_time = QLabel("00:00")
        
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setStyleSheet("color: palette(mid); font-style: italic;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_status.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        bottom_layout.addWidget(self.btn_play)
        bottom_layout.addWidget(self.lbl_current_time)
        bottom_layout.addWidget(self.slider_seek, 3)
        bottom_layout.addWidget(self.lbl_total_time)
        bottom_layout.addWidget(self.lbl_status, 1)
        main_layout.addWidget(bottom_panel)
        
        # 定时器用于平滑更新进度 (50ms = 20fps)
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(50)
        self.update_timer.timeout.connect(self.update_ui_from_player)
        
        self.is_seeking = False
        self.updating_slider = False

        # 连接播放器信号
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.player.playbackStateChanged.connect(self.on_playback_state_changed)

    def _generate_filename(self, prefix):
        return f"{prefix}_{datetime.date.today()}_{str(uuid.uuid4())[:4]}.mp3"

    def browse_save_path(self, line_edit, filter_str):
        initial_path = line_edit.text()
        # 如果当前为空，尝试使用保存的默认目录
        if not initial_path:
            default_dir = self.settings.value("default_save_path", "")
            if default_dir:
                # 补一个默认文件名
                initial_path = os.path.join(default_dir, self._generate_filename("tts"))
        fname, _ = QFileDialog.getSaveFileName(self, "选择保存路径", initial_path, filter_str)
        if fname:
            line_edit.setText(fname)

    def get_current_api_key(self):
        """Return the effective API key from input, config or environment."""
        cfg = load_project_config().get('elevenlabs', {})
        return self.key_input.text().strip() or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")

    def load_voices(self, show_errors=True):
        """Load model/voice/usage data from ElevenLabs.

        Parameters
        ----------
        show_errors : bool
            When False errors emitted by workers during this call will only be
            logged instead of popping up a dialog. This is used for the
            automatic startup refresh so that a missing/invalid key or network
            outage does not annoy the user.
        """
        api_key = self.get_current_api_key()
        if not api_key:
            if show_errors:
                QMessageBox.warning(self, "缺少 Key", "请输入 API Key (或在 config.toml / 环境变量中配置)")
            return

        self.set_ui_busy(True, "正在加载模型、声音和额度...")
        
        # ⭐ 新增：用于追踪两个 worker 是否都完成
        self.models_loaded = False
        self.voices_loaded = False

        # 根据 show_errors 决定是否在 on_error 中弹窗
        self._suppress_errors = not show_errors
        
        # 同时加载模型列表和声音列表
        self.model_worker = ModelListWorker(api_key)
        self.model_worker.finished.connect(self.on_models_loaded)
        self.model_worker.error.connect(self.on_error)
        
        self.voice_worker = VoiceListWorker(api_key)
        self.voice_worker.finished.connect(self.on_voices_loaded)
        self.voice_worker.error.connect(self.on_error)
        
        # 启动两个 worker
        self.model_worker.start()
        self.voice_worker.start()
        
        # 一并刷新额度，传递 show_errors 标识
        self.refresh_quota_only(api_key, show_errors=show_errors)

    def choose_default_save_path(self, line_edit):
        """选择一个默认保存目录，并把当前行编辑框的路径设为该目录下的默认文件名。"""
        directory = QFileDialog.getExistingDirectory(self, "选择默认保存目录", os.path.expanduser("~"))
        if directory:
            # persist to settings
            self.settings.setValue("default_save_path", directory)
            # 更新当前行编辑框为该目录下一个新文件名
            fname = os.path.join(directory, self._generate_filename("tts"))
            line_edit.setText(fname)
            QMessageBox.information(self, "已设置", f"默认保存路径已设置为: {directory}")

    def refresh_quota_only(self, api_key=None, show_errors=True):
        """Query remaining quota.  If no key is available this function will
        silently update the UI but not perform a network call.

        Parameters
        ----------
        api_key : str or None
            Optional explicit API key to use.
        show_errors : bool
            If False any errors from the quota worker are logged instead of
            shown in a dialog.
        """
        if not api_key:
             cfg = load_project_config().get('elevenlabs', {})
             api_key = self.key_input.text().strip() or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")

        if not api_key:
            # no key -> nothing to contact, reset UI and quit early
            logger.info("跳过额度查询：未配置 API Key")
            self.quota_label.setText("未设置API Key")
            self.quota_bar.setValue(0)
            return
        
        self.quota_worker = QuotaWorker(api_key)
        self.quota_worker.quota_info.connect(self.on_quota_loaded)
        if show_errors:
            self.quota_worker.error.connect(self.on_error)
        else:
            self.quota_worker.error.connect(lambda msg: logger.warning(f"(silent) {msg}"))
        self.quota_worker.start()

    def on_voices_loaded(self, voices):
        self.voices_loaded = True
        self.combo_voices.blockSignals(True)
        self.combo_voices.clear()
        
        for item in voices:
            # 兼容处理：解包 (name, vid, preview_url, category)
            if len(item) >= 4:
                name, vid, preview_url, category = item[:4]
            elif len(item) == 3:
                name, vid, preview_url = item
                category = "unspecified"
            else:
                name, vid = item
                preview_url = category = None
            
            # 如果是 premade (官方自带且免费)，添加标识
            display_name = name
            if category == "premade":
                display_name += " (Free)"
            
            self.combo_voices.addItem(display_name, vid)
            if preview_url:
                self.combo_voices.setItemData(self.combo_voices.count() - 1, preview_url, Qt.UserRole + 1)
        
        # 添加“更多声音”选项
        self.combo_voices.insertSeparator(self.combo_voices.count())
        self.combo_voices.addItem("✨ 更多声音 (探索声音库)...", "more_voices")
        
        self.combo_voices.blockSignals(False)
        self._check_all_loaded()
    
    def on_voice_combo_activated(self, index):
        """当用户点击声音下拉列表项时"""
        data = self.combo_voices.itemData(index)
        if data == "more_voices":
            # 重置选择到上一个，避免停留在“更多声音”项上
            # 这里简单重置到第一项，稍后如果有更好的逻辑可以优化
            if index > 0:
                self.combo_voices.setCurrentIndex(0)
            self.open_voice_library()
    
    def on_models_loaded(self, models):
        """当模型列表成功加载时的回调"""
        self.models_loaded = True
        self.models_info = {}  # 清空旧数据
        
        # 仅保留支持TTS的模型
        tts_models = [m for m in models if m.get('can_do_text_to_speech', False)]
        
        if not tts_models:
            logger.warning("未找到支持TTS的模型")
            self.on_error("未找到支持TTS的模型")
            return
        
        # 清空并重新填充模型选择框
        self.combo_model.blockSignals(True)
        self.combo_model.clear()
        
        for model in tts_models:
            model_id = model.get('model_id')
            if model_id:
                self.models_info[model_id] = model
                display_name = model.get('name', model_id)
                display_text = f"{display_name}"
                self.combo_model.addItem(display_text, model_id)
        
        # 默认选择第二个支持TTS的模型
        if self.combo_model.count() > 1:
            self.combo_model.setCurrentIndex(1)
        
        self.combo_model.blockSignals(False)
        # 启用模型下拉（现在已由 API 填充）
        try:
            self.combo_model.setEnabled(True)
        except Exception:
            pass

        # 触发模型变化处理逻辑
        self.on_model_changed()
        
        logger.info(f"已加载 {len(tts_models)} 个支持TTS的模型")
        self._check_all_loaded()
    
    def _check_all_loaded(self):
        """检查两个 worker 是否都完成，如果完成则更新 UI 状态"""
        if self.models_loaded and self.voices_loaded:
            self.set_ui_busy(False, "加载完成")

    def open_voice_library(self):
        """打开声音库搜索对话框"""
        api_key = self.get_current_api_key()
        if not api_key:
            QMessageBox.warning(self, "缺少 Key", "请输入 API Key 以访问声音库")
            return
            
        dialog = VoiceLibraryDialog(self, api_key=api_key)
        # Apply style to dialog
        apply_common_style(dialog)
        
        if dialog.exec() == QDialog.Accepted:
            # 如果在对话框中成功添加了声音，刷新本地声音列表
            self.load_voices()
    
    def on_model_changed(self):
        """当选择的模型改变时，更新可用功能和语言列表"""
        model_id = self.combo_model.currentData()
        if not model_id:
            return
        
        model_info = self.models_info.get(model_id, {})
        model_name = model_info.get('name', model_id)

        # 保存当前模型信息以供对话框使用
        self.current_model_info = model_info
        
        # 检查模型是否支持TTS
        can_tts = model_info.get('can_do_text_to_speech', False)
        if not can_tts:
            QMessageBox.warning(self, "模型不支持TTS", 
                               f"选中的模型 '{model_name}' 不支持文本转语音功能。")
        
        # ⭐ 检查是否是v3模型，支持情绪标签
        is_v3 = 'v3' in model_id.lower()
        # 启用/禁用合并后的情绪管理器
        self.emotion_manager.setEnabled(is_v3)
        
        # 更新提示文本
        if is_v3:
            logger.info(f"模型 '{model_name}' 支持情绪标签功能")
        else:
            logger.info(f"模型 '{model_name}' 不支持情绪标签，该功能已禁用")
        
        # 根据模型功能启用/禁用对应选项
        self.update_feature_availability(model_info)
        
        # 更新可用语言列表
        self.update_available_languages(model_info)
    
    def update_feature_availability(self, model_info):
        """根据模型信息启用/禁用相关功能"""
        # 风格选项（VoiceSettingsDialog中）- 目前先保持，之后可以在对话框中处理
        can_use_style = model_info.get('can_use_style', False)
        
        # 扬声器增强（VoiceSettingsDialog中）
        can_use_speaker_boost = model_info.get('can_use_speaker_boost', False)
        
        # 记录这些信息以供VoiceSettingsDialog使用
        self.current_model_features = {
            'can_use_style': can_use_style,
            'can_use_speaker_boost': can_use_speaker_boost,
            'can_do_voice_conversion': model_info.get('can_do_voice_conversion', False),
        }
        
        # 显示模型信息
        max_chars = model_info.get('maximum_text_length_per_request', 999999)
        logger.info(f"模型: {model_info.get('name')}, 支持风格: {can_use_style}, "
                   f"支持扬声器增强: {can_use_speaker_boost}, 最大字符数: {max_chars}")
    
    def update_available_languages(self, model_info):
        """根据模型支持的语言列表更新语言选择框"""
        languages = model_info.get('languages', [])
        
        if not languages:
            # 如果模型没有指定语言列表，保持现有的全部语言选项
            logger.warning(f"模型 {model_info.get('name')} 未提供支持的语言列表")
            self.available_languages = []
            return
        # 构建可用语言列表并存储，实际的下拉由 VoiceSettingsDialog 在打开时处理
        from ..core.elevenlabs import LANGUAGE_CODES
        supported = []
        for lang in languages:
            lang_id = lang.get('language_id') if isinstance(lang, dict) else lang
            # 查找对应的语言名称
            name = None
            for k, v in LANGUAGE_CODES.items():
                # 兼容 code->name 或 name->code
                if v == lang_id:
                    name = k
                    break
                if k == lang_id:
                    name = v
                    break
            if not name:
                name = lang_id
            supported.append((name, lang_id))

        self.available_languages = sorted(supported)
        logger.info(f"模型支持 {len(self.available_languages)} 种语言")

        
    def save_api_key(self):
        key = self.key_input.text().strip()
        self.settings.setValue("api_key", key)
        QMessageBox.information(self, "保存成功", "API Key 已保存到本地配置，下次启动将自动加载。")

    def update_char_count(self):
        text = self.tts_text_input.toPlainText()
        count = len(text)
        self.lbl_char_count.setText(f"字符数: {count}")
        # 简单提示，假设 5000 为一个常见阈值
        if count > 5000:
            self.lbl_char_count.setStyleSheet("color: #ef4444; font-weight: bold;")
        else:
            self.lbl_char_count.setStyleSheet("color: palette(mid);")

    def preview_current_voice(self):
        idx = self.combo_voices.currentIndex()
        if idx < 0: return
        
        preview_url = self.combo_voices.itemData(idx, Qt.UserRole + 1)
        if not preview_url:
            QMessageBox.information(self, "无样本", "该声音模型未提供预览样本。")
            return
            
        self.lbl_status.setText("正在试听...")
        self.player.setSource(QUrl(preview_url))
        self.player.play()
        self.btn_play.setEnabled(True)

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
            self.quota_bar.setStyleSheet("QProgressBar::chunk { background-color: #ef4444; border-radius: 5px; }")
        else:
            # 重置样式以使用默认的高亮色
            self.quota_bar.setStyleSheet("")
            # 强制刷新样式，确保从父级重新继承
            self.quota_bar.style().unpolish(self.quota_bar)
            self.quota_bar.style().polish(self.quota_bar)

    def generate_tts_audio(self):
        cfg = load_project_config().get('elevenlabs', {})
        text = self.tts_text_input.toPlainText().strip()
        save_path = self.tts_save_input.text().strip()
        voice_id = self.combo_voices.itemData(self.combo_voices.currentIndex())
        api_key = self.key_input.text().strip() or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")
        output_format = cfg.get('default_output_format')
        translate = self.chk_translate.isChecked()
        word_level = self.chk_word_level.isChecked()
        words_per_line = self.spin_words_per_line.value()

        export_xml = self.chk_export_xml.isChecked()
        keyword_highlight = self.chk_keyword_highlight.isChecked()
        
        # ⭐ 修改：获取模型、语言参数；情绪标签现在嵌入在文本中
        model_id = self.combo_model.currentData()
        # 语言参数从语音设定中获取（语言下拉已移入语音设定窗口）
        language_code = self.voice_settings.get('language_code') if isinstance(self.voice_settings, dict) else None
        # 情绪标签现在由文案中的 [emotion] 标签提供
        # API 会自动解析文本中的情绪标签，所以这里不需要单独传递 emotion 参数
        
        if not voice_id:
             QMessageBox.warning(self, "提示", "请先加载并选择一个声音模型。")
             return
        if not text:
            QMessageBox.warning(self, "提示", "请输入要转换的文本。")
            return

        self.set_ui_busy(True, "生成中...")
        self.tts_worker = TTSWorker(
            api_key=api_key, 
            voice_id=voice_id, 
            text=text, 
            save_path=save_path, 
            output_format=output_format, 
            translate=translate, 
            word_level=word_level, 
            export_xml=export_xml, 
            words_per_line=words_per_line,
            groq_api_key=self.groq_settings.get('api_key'),
            groq_model=self.groq_settings.get('model'),
            xml_style_settings=self.xml_styles, 
            video_settings=self.video_settings, 
            keyword_highlight=keyword_highlight,
            voice_settings=self.voice_settings,
            model_id=model_id,              # ⭐ 模型ID
            language_code=language_code,    # ⭐ 语言代码
            emotion=None                    # ⭐ 情绪现在嵌入在文本中，通过 [emotion] 标签指定
        )
        self.tts_worker.finished.connect(self.on_generation_success)
        self.tts_worker.error.connect(self.on_error)
        self.tts_worker.start()
    
    def open_voice_settings(self):
        """打开语音设定对话框"""
        # ⭐ 传递当前模型的功能信息
        model_features = getattr(self, 'current_model_features', {
            'can_use_style': True,
            'can_use_speaker_boost': True,
        })
        dialog = VoiceSettingsDialog(self, model_features=model_features, model_info=getattr(self, 'current_model_info', {}), available_languages=getattr(self, 'available_languages', []))
        dialog.set_settings(self.voice_settings)
        
        if dialog.exec() == QDialog.Accepted:
            # 更新语音设定
            self.voice_settings = dialog.get_settings()
            logger.info(f"语音设定已更新: {self.voice_settings}")

    def get_groq_settings(self):
        """获取当前 Groq 设置，由子组件调用"""
        return self.groq_settings

    def get_video_settings(self):
        """获取当前视频设置，由子组件调用"""
        return self.video_settings
    
    def open_subtitle_settings(self):
        """打开字幕设置对话框"""
        self.active_subtitle_dialog = SubtitleSettingsDialog(
            self,
            xml_styles=self.xml_styles,
            video_settings=self.video_settings,
            groq_settings=self.groq_settings
        )
        
        if self.active_subtitle_dialog.exec() == QDialog.Accepted:
            # 更新 Groq 设定
            self.groq_settings = self.active_subtitle_dialog.get_groq_settings()
            logger.info(f"Groq 设定已更新: {self.groq_settings}")
            
            # 更新视频设定
            self.video_settings = self.active_subtitle_dialog.get_video_settings()
            logger.info(f"视频设定已更新: {self.active_subtitle_dialog.get_video_settings()}")
        
        self.active_subtitle_dialog = None

    def generate_sfx_audio(self):
        cfg = load_project_config().get('elevenlabs', {})
        prompt = self.sfx_prompt_input.toPlainText().strip()
        duration = self.sfx_duration_input.value()
        save_path = self.sfx_save_input.text().strip()
        api_key = self.key_input.text().strip() or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")
        output_format = cfg.get('default_output_format')
        
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入音效描述。")
            return

        self.set_ui_busy(True, "生成中...")
        self.sfx_worker = SFXWorker(api_key=api_key, prompt=prompt, duration=duration, save_path=save_path, output_format=output_format)
        self.sfx_worker.finished.connect(self.on_generation_success)
        self.sfx_worker.error.connect(self.on_error)
        self.sfx_worker.start()

    def on_generation_success(self, file_path):
        self.set_ui_busy(False, "生成成功")
        self.current_audio_path = file_path
        self.btn_play.setEnabled(True)
        self.slider_seek.setEnabled(True)
        
        # 3. 解决同名文件缓存问题：先置空再加载
        self.player.stop()
        self.player.setSource(QUrl())
        self.player.setSource(QUrl.fromLocalFile(file_path))
        
        self.lbl_status.setText("已保存")
        self.lbl_status.setToolTip(f"文件保存在: {file_path}")
        
        # 自动刷新文件名以防覆盖
        if "tts" in os.path.basename(file_path):
            self.tts_save_input.setText(self._generate_filename("tts"))
        else:
            self.sfx_save_input.setText(self._generate_filename("sfx"))
            
        # 2. 每次生成音频后自动刷新额度
        #    不需要在这里因为缺少 Key 或网络问题弹出错误
        self.refresh_quota_only(show_errors=False)

    def on_error(self, error_msg):
        # 当 _suppress_errors 标志为 True 时，错误仅记录不弹窗。
        self.set_ui_busy(False, "错误")
        if getattr(self, '_suppress_errors', False):
            logger.warning(f"(suppressed) API 错误: {error_msg}")
            return
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
        else:
            self.player.play()

    def on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.update_timer.start()
            self.btn_play.setText("⏸ 暂停")
        elif state == QMediaPlayer.PausedState:
            self.update_timer.stop()
            self.btn_play.setText("▶ 继续")
        else:
            self.update_timer.stop()
            self.btn_play.setText("▶ 播放")

    def update_ui_from_player(self):
        if not self.is_seeking and self.player.playbackState() == QMediaPlayer.PlayingState:
            self.updating_slider = True
            pos = self.player.position()
            self.slider_seek.setValue(pos)
            self.lbl_current_time.setText(self._format_time(pos))
            self.updating_slider = False

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.slider_seek.setValue(0)
            self.lbl_current_time.setText("00:00")

    def on_slider_pressed(self):
        self.is_seeking = True

    def on_slider_released(self):
        self.is_seeking = False
        self.player.setPosition(self.slider_seek.value())

    def on_slider_value_changed(self, value):
        if not self.updating_slider:
            self.lbl_current_time.setText(self._format_time(value))

    def on_duration_changed(self, duration):
        self.slider_seek.setRange(0, duration)
        self.lbl_total_time.setText(self._format_time(duration))

    def _format_time(self, ms):
        seconds = (ms // 1000) % 60
        minutes = (ms // 60000)
        return f"{minutes:02d}:{seconds:02d}"

    # ========== XML 样式设置相关方法 ==========
    
    def create_style_settings_panel(self, style_type):
        """创建样式设置面板 (原文/翻译)"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # --- 1. 基础字体设置 ---
        font_group = QGroupBox("基础字体")
        font_layout = QGridLayout(font_group)
        font_layout.setSpacing(8)
        
        # 字体选择
        font_combo = QFontComboBox()
        font_combo.setCurrentFont(QFont(self.xml_styles[style_type]['font']))
        font_combo.setToolTip("选择字体")
        font_combo.currentFontChanged.connect(
            lambda font: self.update_style(style_type, 'font', font.family())
        )
        font_layout.addWidget(QLabel("字体:"), 0, 0)
        font_layout.addWidget(font_combo, 0, 1, 1, 3)
        
        # 大小 & 颜色
        size_spin = QSpinBox()
        size_spin.setRange(10, 200)
        size_spin.setValue(self.xml_styles[style_type]['fontSize'])
        size_spin.setSuffix(" px")
        size_spin.setToolTip("字体大小")
        size_spin.valueChanged.connect(
            lambda val: self.update_style(style_type, 'fontSize', val)
        )
        font_layout.addWidget(QLabel("大小:"), 1, 0)
        font_layout.addWidget(size_spin, 1, 1)
        
        font_color_btn = QPushButton()
        font_color_btn.setToolTip("字体颜色")
        self.set_button_color(font_color_btn, self.xml_styles[style_type]['fontColor'])
        font_color_btn.clicked.connect(
            lambda: self.pick_color(style_type, 'fontColor', font_color_btn)
        )
        font_layout.addWidget(QLabel("颜色:"), 1, 2)
        font_layout.addWidget(font_color_btn, 1, 3)
        
        # 样式 (粗体/斜体)
        style_layout = QHBoxLayout()
        bold_chk = QCheckBox("加粗")
        bold_chk.setToolTip("加粗")
        bold_chk.setChecked(self.xml_styles[style_type]['bold'])
        bold_chk.toggled.connect(
            lambda checked: self.update_style(style_type, 'bold', checked)
        )
        italic_chk = QCheckBox("斜体")
        italic_chk.setToolTip("斜体")
        italic_chk.setChecked(self.xml_styles[style_type]['italic'])
        italic_chk.toggled.connect(
            lambda checked: self.update_style(style_type, 'italic', checked)
        )
        style_layout.addWidget(bold_chk)
        style_layout.addWidget(italic_chk)
        style_layout.addStretch()
        font_layout.addWidget(QLabel("样式:"), 2, 0)
        font_layout.addLayout(style_layout, 2, 1, 1, 3)
        
        # 对齐 & Y轴位置
        align_combo = QComboBox()
        align_combo.addItems(['left', 'center', 'right'])
        align_combo.setCurrentText(self.xml_styles[style_type]['alignment'])
        align_combo.currentTextChanged.connect(
            lambda val: self.update_style(style_type, 'alignment', val)
        )
        font_layout.addWidget(QLabel("对齐:"), 3, 0)
        font_layout.addWidget(align_combo, 3, 1)
        
        pos_spin = QSpinBox()
        pos_spin.setRange(-1000, 1000)
        pos_spin.setValue(self.xml_styles[style_type]['pos'])
        pos_spin.setToolTip("Y轴位置 (向上为负，向下为正)")
        pos_spin.valueChanged.connect(
            lambda val: self.update_style(style_type, 'pos', val)
        )
        font_layout.addWidget(QLabel("Y轴位置:"), 3, 2)
        font_layout.addWidget(pos_spin, 3, 3)
        
        main_layout.addWidget(font_group)
        
        # --- 2. 效果设置 (描边 + 阴影) ---
        effect_group = QGroupBox("效果设置 (描边 & 阴影)")
        effect_layout = QVBoxLayout(effect_group)
        effect_layout.setSpacing(10)
        
        # 描边行
        stroke_layout = QHBoxLayout()
        stroke_chk = QCheckBox("描边")
        stroke_chk.setChecked(self.xml_styles[style_type].get('useStroke', False))
        stroke_chk.toggled.connect(
            lambda checked: self.update_style(style_type, 'useStroke', checked)
        )
        stroke_layout.addWidget(stroke_chk)
        
        stroke_width_spin = QDoubleSpinBox()
        stroke_width_spin.setRange(0, 20)
        stroke_width_spin.setValue(self.xml_styles[style_type]['strokeWidth'])
        stroke_width_spin.setSingleStep(0.5)
        stroke_width_spin.setSuffix(" px")
        stroke_width_spin.valueChanged.connect(
            lambda val: self.update_style(style_type, 'strokeWidth', val)
        )
        stroke_chk.toggled.connect(stroke_width_spin.setEnabled)
        stroke_width_spin.setEnabled(stroke_chk.isChecked())
        stroke_layout.addWidget(stroke_width_spin)
        
        stroke_color_btn = QPushButton()
        stroke_color_btn.setToolTip("描边颜色")
        stroke_color_btn.setFixedWidth(40)
        self.set_button_color(stroke_color_btn, self.xml_styles[style_type]['strokeColor'])
        stroke_color_btn.clicked.connect(
            lambda: self.pick_color(style_type, 'strokeColor', stroke_color_btn)
        )
        stroke_chk.toggled.connect(stroke_color_btn.setEnabled)
        stroke_color_btn.setEnabled(stroke_chk.isChecked())
        stroke_layout.addWidget(stroke_color_btn)
        stroke_layout.addStretch()
        
        # 阴影行
        shadow_layout = QHBoxLayout()
        shadow_chk = QCheckBox("阴影")
        shadow_chk.setChecked(self.xml_styles[style_type].get('useShadow', False))
        shadow_chk.toggled.connect(
            lambda checked: self.update_style(style_type, 'useShadow', checked)
        )
        shadow_layout.addWidget(shadow_chk)
        
        shadow_x = QSpinBox()
        shadow_x.setRange(-50, 50)
        shadow_x.setValue(self.xml_styles[style_type]['shadowOffset'][0])
        shadow_x.setPrefix("X:")
        shadow_x.setFixedWidth(60)
        shadow_x.valueChanged.connect(
            lambda val: self.update_shadow_offset(style_type, val, None)
        )
        shadow_chk.toggled.connect(shadow_x.setEnabled)
        shadow_x.setEnabled(shadow_chk.isChecked())
        shadow_layout.addWidget(shadow_x)
        
        shadow_y = QSpinBox()
        shadow_y.setRange(-50, 50)
        shadow_y.setValue(self.xml_styles[style_type]['shadowOffset'][1])
        shadow_y.setPrefix("Y:")
        shadow_y.setFixedWidth(60)
        shadow_y.valueChanged.connect(
            lambda val: self.update_shadow_offset(style_type, None, val)
        )
        shadow_chk.toggled.connect(shadow_y.setEnabled)
        shadow_y.setEnabled(shadow_chk.isChecked())
        shadow_layout.addWidget(shadow_y)
        
        shadow_color_btn = QPushButton()
        shadow_color_btn.setToolTip("阴影颜色")
        shadow_color_btn.setFixedWidth(40)
        self.set_button_color(shadow_color_btn, self.xml_styles[style_type]['shadowColor'])
        shadow_color_btn.clicked.connect(
            lambda: self.pick_color(style_type, 'shadowColor', shadow_color_btn)
        )
        shadow_chk.toggled.connect(shadow_color_btn.setEnabled)
        shadow_color_btn.setEnabled(shadow_chk.isChecked())
        shadow_layout.addWidget(shadow_color_btn)
        shadow_layout.addStretch()
        
        effect_layout.addLayout(stroke_layout)
        effect_layout.addLayout(shadow_layout)
        main_layout.addWidget(effect_group)
        
        main_layout.addStretch()
        return widget
        
        main_layout.addStretch()
        
        return widget
    
    def set_button_color(self, button, color_tuple):
        """设置按钮的背景颜色以反映 RGBA 颜色"""
        if isinstance(color_tuple, (list, tuple)) and len(color_tuple) >= 4:
            r, g, b, a = int(color_tuple[0]*255), int(color_tuple[1]*255), int(color_tuple[2]*255), int(color_tuple[3]*255)
        else:
            r, g, b, a = 255, 255, 255, 255
        
        qcolor = QColor(r, g, b, a)
        button.setStyleSheet(f"background-color: {qcolor.name()}; border-radius: 4px;")
        button.setFixedHeight(32)
    
    def pick_color(self, style_type, key, button):
        """打开颜色选择对话框"""
        current_color = self.xml_styles[style_type][key]
        if isinstance(current_color, (list, tuple)):
            r, g, b, a = int(current_color[0]*255), int(current_color[1]*255), int(current_color[2]*255), int(current_color[3]*255)
            initial_color = QColor(r, g, b, a)
        else:
            initial_color = QColor(255, 255, 255, 255)
        
        color = QColorDialog.getColor(initial_color, self, f"选择{key}颜色")
        if color.isValid():
            r, g, b, a = color.getRgb()
            color_tuple = (r/255.0, g/255.0, b/255.0, a/255.0)
            self.update_style(style_type, key, color_tuple)
            self.set_button_color(button, color_tuple)
    
    def update_style(self, style_type, key, value):
        """更新样式设置并刷新预览"""
        self.xml_styles[style_type][key] = value
        self.update_preview()
    
    def update_shadow_offset(self, style_type, x=None, y=None):
        """更新阴影偏移"""
        current = list(self.xml_styles[style_type]['shadowOffset'])
        if x is not None:
            current[0] = x
        if y is not None:
            current[1] = y
        self.xml_styles[style_type]['shadowOffset'] = tuple(current)
        self.update_preview()
    
    def on_video_settings_changed(self):
        """更新视频设置"""
        try:
            self.video_settings['fps'] = int(self.combo_fps.currentText())
        except:
            self.video_settings['fps'] = 30

    def on_resolution_preset_changed(self, index):
        preset = self.combo_res.currentText()
        is_vertical = self.chk_vertical.isChecked()
        
        w, h = 1920, 1080 # Default
        
        if "1080p" in preset:
            w, h = 1920, 1080
        elif "2K" in preset:
            w, h = 2560, 1440
        elif "4K" in preset:
            w, h = 3840, 2160

        if is_vertical:
            w, h = h, w
            
        self.video_settings['width'] = w
        self.video_settings['height'] = h

    def on_vertical_toggled(self, checked):
        # 重新触发一次分辨率选择逻辑以应用翻转
        self.on_resolution_preset_changed(self.combo_res.currentIndex())

    def update_preview(self):  
        """更新预览窗口 - 支持对话框和主窗口"""
        # 如果对话框打开，更新对话框内的预览
        if hasattr(self, 'active_subtitle_dialog') and self.active_subtitle_dialog and self.active_subtitle_dialog.isVisible():
            dialog = self.active_subtitle_dialog
            current_tab = dialog.tabs.currentIndex()
            # Tab 0 是常规设置，1-3 是样式设置
            if 1 <= current_tab <= 3:
                style_types = ['source', 'translate', 'highlight']
                style_type = style_types[current_tab - 1]
                if style_type in self.xml_styles:
                    dialog.dialog_preview_label.update_style(self.xml_styles[style_type])
            return

        # 否则更新主界面的预览
        if not hasattr(self, 'preview_label') or not self.preview_label:
            return
        
        style_type = 'source'  # 默认使用原文样式
        if style_type in self.xml_styles:
            self.preview_label.update_style(self.xml_styles[style_type])