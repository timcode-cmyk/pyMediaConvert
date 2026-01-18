import os
import datetime
import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QTextEdit, QComboBox, QMessageBox, QProgressBar, QFileDialog, QSlider,
                               QGroupBox, QSizePolicy, QSpinBox, QCheckBox, QTabWidget, QScrollArea,
                               QFontComboBox, QColorDialog, QDoubleSpinBox, QGridLayout)
from PySide6.QtCore import Qt, QUrl, QSettings, QTimer, QSize, QRectF
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen, QBrush, QFontMetrics
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from ..core.elevenlabs import QuotaWorker, TTSWorker, SFXWorker, VoiceListWorker
from ..utils import load_project_config
from .styles import apply_common_style
from ..logging_config import get_logger

logger = get_logger(__name__)

class SubtitlePreviewLabel(QLabel):
    """自定义预览标签，支持描边、阴影和背景绘制"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.style_data = {}
        self.setText("预览文本\nPreview Text")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(100)
        self.setMinimumWidth(300)

    def update_style(self, style_data):
        self.style_data = style_data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # 获取样式数据
        s = self.style_data
        if not s:
            super().paintEvent(event)
            return

        # 准备字体
        font = QFont(s.get('font', 'Arial'), s.get('fontSize', 50))
        font.setBold(s.get('bold', False))
        font.setItalic(s.get('italic', False))
        painter.setFont(font)

        # 准备颜色
        fc = s.get('fontColor', (1, 1, 1, 1))
        font_color = QColor.fromRgbF(*fc)
        
        # 绘制背景 (如果开启)
        if s.get('useBackground', False):
            bc = s.get('backgroundColor', (0, 0, 0, 0))
            bg_color = QColor.fromRgbF(*bc)
            padding = s.get('backgroundPadding', 0)
            
            # 简单计算文本边界 (多行处理较复杂，这里做近似背景)
            metrics = QFontMetrics(font)
            line_height = metrics.height()
            lines = self.text().split('\n')
            max_width = 0
            # 计算总高度包含行间距
            total_height = len(lines) * line_height + (len(lines) - 1) * s.get('lineSpacing', 0)
            
            for line in lines:
                max_width = max(max_width, metrics.horizontalAdvance(line))
            
            # 居中背景框
            cx, cy = self.width() / 2, self.height() / 2
            bg_rect = QRectF(cx - max_width/2 - padding, cy - total_height/2 - padding, 
                             max_width + padding*2, total_height + padding*2)
            
            painter.setBrush(QBrush(bg_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bg_rect, 8, 8)

        # 绘制文本 (支持描边和阴影)
        path = QPainterPath()
        # 简单居中绘制逻辑
        metrics = QFontMetrics(font)
        line_height = metrics.height()
        lines = self.text().split('\n')
        spacing = s.get('lineSpacing', 0)
        content_height = len(lines) * line_height + (len(lines) - 1) * spacing
        y = (self.height() - content_height) / 2 + metrics.ascent()
        
        for line in lines:
            text_width = metrics.horizontalAdvance(line)
            x = (self.width() - text_width) / 2
            
            # 将文本添加到路径
            path.addText(x, y, font, line)
            y += line_height + spacing

        # 1. 绘制阴影
        if s.get('useShadow', False):
            sc = s.get('shadowColor', (0, 0, 0, 0.5))
            shadow_color = QColor.fromRgbF(*sc)
            offset = s.get('shadowOffset', (2, 2))
            
            painter.save()
            painter.translate(offset[0], offset[1])
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(shadow_color))
            painter.drawPath(path)
            painter.restore()

        # 2. 绘制描边
        if s.get('useStroke', False):
            stc = s.get('strokeColor', (0, 0, 0, 1))
            stroke_color = QColor.fromRgbF(*stc)
            stroke_width = s.get('strokeWidth', 0)
            
            if stroke_width > 0:
                pen = QPen(stroke_color, stroke_width)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(path)

        # 3. 绘制填充 (文字本体)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(font_color))
        painter.drawPath(path)

class ElevenLabsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_audio_path = None
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
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
        
        # 视频设置
        self.video_settings = {
            'fps': 30,
            'width': 1920,
            'height': 1080,
        }
        
        # 尝试从 config.toml 加载默认样式配置
        cfg = load_project_config()
        if 'xml_styles' in cfg and isinstance(cfg['xml_styles'], dict):
            for key, val in cfg['xml_styles'].items():
                if key in self.xml_styles and isinstance(val, dict):
                    self.xml_styles[key].update(val)
        
        self.setup_ui()
        self.apply_styles()
        
        # 1. 程序启动时如有读取到api自动刷新
        if self.key_input.text().strip():
            self.load_voices()

    def apply_styles(self):
        apply_common_style(self)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 标题
        title = QLabel("ElevenLabs 语音合成")
        title.setObjectName("TitleLabel")
        main_layout.addWidget(title)

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
        voice_layout.addWidget(QLabel("选择声音模型:"))
        self.combo_voices = QComboBox()
        self.combo_voices.setPlaceholderText("请先刷新配置...")
        voice_layout.addWidget(self.combo_voices, 1)

        self.btn_preview_voice = QPushButton("🔊 试听")
        self.btn_preview_voice.setFixedWidth(80)
        self.btn_preview_voice.setToolTip("播放官方样本 (不消耗额度)")
        self.btn_preview_voice.clicked.connect(self.preview_current_voice)
        voice_layout.addWidget(self.btn_preview_voice)

        tts_inner_layout.addLayout(voice_layout)

        # 文本输入
        # 5. 优化文本输入框，在窗口缩放时自动调节文本框高度
        self.tts_text_input = QTextEdit()
        self.tts_text_input.setPlaceholderText("请输入要转换的文本内容...")
        self.tts_text_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # # 6. 文本框内增加一个实时的剩余字符长度提示
        # self.lbl_char_count = QLabel("字符数: 0")
        # self.lbl_char_count.setAlignment(Qt.AlignmentFlag.AlignRight)
        # self.tts_text_input.textChanged.connect(self.update_char_count)
        
        tts_inner_layout.addWidget(self.tts_text_input)
        # tts_inner_layout.addWidget(self.lbl_char_count)

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
        self.chk_keyword_highlight = QCheckBox("智能高亮关键词 (Groq)")
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
        tts_inner_layout.addLayout(sub_opts_layout)

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
        
        self.btn_sfx_generate = QPushButton("生成音效")
        self.btn_sfx_generate.setObjectName("PrimaryButton")
        self.btn_sfx_generate.clicked.connect(self.generate_sfx_audio)

        sfx_action_layout.addWidget(QLabel("保存至:"))
        sfx_action_layout.addWidget(self.sfx_save_input)
        sfx_action_layout.addWidget(self.btn_sfx_browse)
        sfx_action_layout.addWidget(self.btn_sfx_generate)
        sfx_inner_layout.addLayout(sfx_action_layout)
        
        # --- XML 样式设置区域 ---
        xml_group = QWidget()
        xml_inner_layout = QVBoxLayout(xml_group)
        xml_inner_layout.setContentsMargins(10, 15, 10, 10)
        xml_inner_layout.setSpacing(10)
        
        # 创建可滚动的样式设置区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(15)
        
        # 视频基本设置
        video_group = QGroupBox("视频设置")
        video_layout = QHBoxLayout(video_group)
        video_layout.setContentsMargins(5, 5, 5, 5)
        
        video_layout.addWidget(QLabel("帧率:"))
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["24", "25", "30", "60"])
        fps_str = str(self.video_settings['fps'])
        if self.combo_fps.findText(fps_str) != -1:
            self.combo_fps.setCurrentText(fps_str)
        self.combo_fps.currentTextChanged.connect(self.on_video_settings_changed)
        video_layout.addWidget(self.combo_fps)
        
        video_layout.addWidget(QLabel("分辨率:"))
        self.combo_res = QComboBox()
        self.combo_res.addItems(["1080p (1920x1080)", "2K (2560x1440)", "4K (3840x2160)"])
        self.combo_res.currentIndexChanged.connect(self.on_resolution_preset_changed)
        video_layout.addWidget(self.combo_res)
        
        self.chk_vertical = QCheckBox("使用竖屏分辨率")
        self.chk_vertical.toggled.connect(self.on_vertical_toggled)
        video_layout.addWidget(self.chk_vertical)
        
        scroll_layout.addWidget(video_group)
        
        # 原文字幕样式设置
        self.style_tabs = QTabWidget()
        
        source_style_widget = self.create_style_settings_panel('source')
        trans_style_widget = self.create_style_settings_panel('translate')
        highlight_style_widget = self.create_style_settings_panel('highlight')
        
        self.style_tabs.addTab(source_style_widget, "原文字幕样式")
        self.style_tabs.addTab(trans_style_widget, "翻译字幕样式")
        self.style_tabs.addTab(highlight_style_widget, "高亮字幕样式")
        
        scroll_layout.addWidget(self.style_tabs)
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        xml_inner_layout.addWidget(scroll_area)
        
        # 预览窗口
        preview_group = QGroupBox("样式预览")
        preview_layout = QVBoxLayout(preview_group)
        # 使用自定义预览 Label
        self.preview_label = SubtitlePreviewLabel()
        self.update_preview() # 初始化预览
        preview_layout.addWidget(self.preview_label)
        xml_inner_layout.addWidget(preview_group)
        
        # 将两个功能区添加到 Tab
        tabs_widget.addTab(tts_group, "🗣️ 文本转语音 (TTS)")
        tabs_widget.addTab(sfx_group, "🎵 音效生成 (SFX)")
        tabs_widget.addTab(xml_group, "⚙️ XML 样式设置")

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
        fname, _ = QFileDialog.getSaveFileName(self, "选择保存路径", initial_path, filter_str)
        if fname:
            line_edit.setText(fname)

    def load_voices(self):
        cfg = load_project_config().get('elevenlabs', {})
        api_key = self.key_input.text().strip() or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")
        if not api_key:
            QMessageBox.warning(self, "缺少 Key", "请输入 API Key (或在 config.toml / 环境变量中配置)")
            return
        self.set_ui_busy(True, "连接中...")
        self.voice_worker = VoiceListWorker(api_key)
        self.voice_worker.finished.connect(self.on_voices_loaded)
        self.voice_worker.error.connect(self.on_error)
        self.voice_worker.start()
        self.refresh_quota_only(api_key)

    def refresh_quota_only(self, api_key=None):
        if not api_key:
             cfg = load_project_config().get('elevenlabs', {})
             api_key = self.key_input.text().strip() or cfg.get('api_key') or os.getenv("ELEVENLABS_API_KEY", "")
        
        self.quota_worker = QuotaWorker(api_key)
        self.quota_worker.quota_info.connect(self.on_quota_loaded)
        self.quota_worker.error.connect(self.on_error)
        self.quota_worker.start()

    def on_voices_loaded(self, voices):
        self.set_ui_busy(False, "加载完成")
        self.combo_voices.clear()
        for item in voices:
            # 兼容处理：解包 (name, vid, preview_url)
            if len(item) >= 3:
                name, vid, preview_url = item[:3]
            else:
                name, vid = item
                preview_url = None
            
            self.combo_voices.addItem(name, vid)
            if preview_url:
                self.combo_voices.setItemData(self.combo_voices.count() - 1, preview_url, Qt.UserRole + 1)
        
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
        
        if not voice_id:
             QMessageBox.warning(self, "提示", "请先加载并选择一个声音模型。")
             return
        if not text:
            QMessageBox.warning(self, "提示", "请输入要转换的文本。")
            return

        self.set_ui_busy(True, "生成中...")
        self.tts_worker = TTSWorker(api_key=api_key, voice_id=voice_id, text=text, save_path=save_path, 
                                    output_format=output_format, translate=translate, word_level=word_level, export_xml=export_xml, words_per_line=words_per_line,
                                    xml_style_settings=self.xml_styles, video_settings=self.video_settings, keyword_highlight=keyword_highlight)
        self.tts_worker.finished.connect(self.on_generation_success)
        self.tts_worker.error.connect(self.on_error)
        self.tts_worker.start()

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
        self.refresh_quota_only()

    def on_error(self, error_msg):
        self.set_ui_busy(False, "错误")
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
        
        # 对齐 & 行距 & Y轴
        align_combo = QComboBox()
        align_combo.addItems(['left', 'center', 'right'])
        align_combo.setCurrentText(self.xml_styles[style_type]['alignment'])
        align_combo.currentTextChanged.connect(
            lambda val: self.update_style(style_type, 'alignment', val)
        )
        font_layout.addWidget(QLabel("对齐:"), 3, 0)
        font_layout.addWidget(align_combo, 3, 1)
        
        line_spacing_spin = QSpinBox()
        line_spacing_spin.setRange(0, 50)
        line_spacing_spin.setValue(self.xml_styles[style_type]['lineSpacing'])
        line_spacing_spin.valueChanged.connect(
            lambda val: self.update_style(style_type, 'lineSpacing', val)
        )
        font_layout.addWidget(QLabel("行距:"), 3, 2)
        font_layout.addWidget(line_spacing_spin, 3, 3)
        
        pos_spin = QSpinBox()
        pos_spin.setRange(-500, 500)
        pos_spin.setValue(self.xml_styles[style_type]['pos'])
        pos_spin.valueChanged.connect(
            lambda val: self.update_style(style_type, 'pos', val)
        )
        font_layout.addWidget(QLabel("Y轴:"), 4, 0)
        font_layout.addWidget(pos_spin, 4, 1)
        
        main_layout.addWidget(font_group)
        
        # --- 2. 描边设置 ---
        stroke_group = QGroupBox("描边")
        stroke_layout = QHBoxLayout(stroke_group)
        
        stroke_chk = QCheckBox("启用")
        stroke_chk.setChecked(self.xml_styles[style_type].get('useStroke', False))
        stroke_chk.toggled.connect(
            lambda checked: self.update_style(style_type, 'useStroke', checked)
        )
        stroke_layout.addWidget(stroke_chk)
        
        stroke_width_spin = QDoubleSpinBox()
        stroke_width_spin.setRange(0, 20)
        stroke_width_spin.setValue(self.xml_styles[style_type]['strokeWidth'])
        stroke_width_spin.setSingleStep(0.5)
        stroke_width_spin.setToolTip("描边宽度")
        stroke_width_spin.setSuffix(" px")
        stroke_width_spin.valueChanged.connect(
            lambda val: self.update_style(style_type, 'strokeWidth', val)
        )
        stroke_chk.toggled.connect(stroke_width_spin.setEnabled)
        stroke_width_spin.setEnabled(stroke_chk.isChecked())
        stroke_layout.addWidget(QLabel("宽度:"))
        stroke_layout.addWidget(stroke_width_spin)
        
        stroke_color_btn = QPushButton()
        stroke_color_btn.setToolTip("描边颜色")
        self.set_button_color(stroke_color_btn, self.xml_styles[style_type]['strokeColor'])
        stroke_color_btn.clicked.connect(
            lambda: self.pick_color(style_type, 'strokeColor', stroke_color_btn)
        )
        stroke_chk.toggled.connect(stroke_color_btn.setEnabled)
        stroke_color_btn.setEnabled(stroke_chk.isChecked())
        stroke_layout.addWidget(stroke_color_btn)
        stroke_layout.addStretch()
        
        main_layout.addWidget(stroke_group)
        
        # --- 3. 阴影设置 ---
        shadow_group = QGroupBox("阴影")
        shadow_layout = QHBoxLayout(shadow_group)
        
        shadow_chk = QCheckBox("启用")
        shadow_chk.setChecked(self.xml_styles[style_type].get('useShadow', False))
        shadow_chk.toggled.connect(
            lambda checked: self.update_style(style_type, 'useShadow', checked)
        )
        shadow_layout.addWidget(shadow_chk)
        
        shadow_color_btn = QPushButton()
        shadow_color_btn.setToolTip("阴影颜色")
        self.set_button_color(shadow_color_btn, self.xml_styles[style_type]['shadowColor'])
        shadow_color_btn.clicked.connect(
            lambda: self.pick_color(style_type, 'shadowColor', shadow_color_btn)
        )
        shadow_chk.toggled.connect(shadow_color_btn.setEnabled)
        shadow_color_btn.setEnabled(shadow_chk.isChecked())
        shadow_layout.addWidget(shadow_color_btn)
        
        shadow_x = QSpinBox()
        shadow_x.setRange(-50, 50)
        shadow_x.setValue(self.xml_styles[style_type]['shadowOffset'][0])
        shadow_x.setToolTip("阴影 X 偏移")
        shadow_x.setPrefix("X: ")
        shadow_x.valueChanged.connect(
            lambda val: self.update_shadow_offset(style_type, val, None)
        )
        shadow_chk.toggled.connect(shadow_x.setEnabled)
        shadow_x.setEnabled(shadow_chk.isChecked())
        shadow_layout.addWidget(shadow_x)
        
        shadow_y = QSpinBox()
        shadow_y.setRange(-50, 50)
        shadow_y.setValue(self.xml_styles[style_type]['shadowOffset'][1])
        shadow_y.setToolTip("阴影 Y 偏移")
        shadow_y.setPrefix("Y: ")
        shadow_y.valueChanged.connect(
            lambda val: self.update_shadow_offset(style_type, None, val)
        )
        shadow_chk.toggled.connect(shadow_y.setEnabled)
        shadow_y.setEnabled(shadow_chk.isChecked())
        shadow_layout.addWidget(shadow_y)
        shadow_layout.addStretch()
        
        main_layout.addWidget(shadow_group)
        
        # --- 4. 背景设置 ---
        bg_group = QGroupBox("背景")
        bg_layout = QHBoxLayout(bg_group)
        
        bg_chk = QCheckBox("启用")
        bg_chk.setChecked(self.xml_styles[style_type].get('useBackground', False))
        bg_chk.toggled.connect(
            lambda checked: self.update_style(style_type, 'useBackground', checked)
        )
        bg_layout.addWidget(bg_chk)
        
        bg_color_btn = QPushButton()
        bg_color_btn.setToolTip("背景颜色")
        self.set_button_color(bg_color_btn, self.xml_styles[style_type]['backgroundColor'])
        bg_color_btn.clicked.connect(
            lambda: self.pick_color(style_type, 'backgroundColor', bg_color_btn)
        )
        bg_chk.toggled.connect(bg_color_btn.setEnabled)
        bg_color_btn.setEnabled(bg_chk.isChecked())
        bg_layout.addWidget(bg_color_btn)
        
        bg_padding_spin = QSpinBox()
        bg_padding_spin.setRange(0, 100)
        bg_padding_spin.setValue(self.xml_styles[style_type]['backgroundPadding'])
        bg_padding_spin.setToolTip("背景内边距")
        bg_padding_spin.setPrefix("边距: ")
        bg_padding_spin.valueChanged.connect(
            lambda val: self.update_style(style_type, 'backgroundPadding', val)
        )
        bg_chk.toggled.connect(bg_padding_spin.setEnabled)
        bg_padding_spin.setEnabled(bg_chk.isChecked())
        bg_layout.addWidget(bg_padding_spin)
        bg_layout.addStretch()
        
        main_layout.addWidget(bg_group)
        
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
        """更新预览窗口"""
        current_tab = self.style_tabs.currentIndex()
        if current_tab == 0:
            style_type = 'source'
        elif current_tab == 1:
            style_type = 'translate'
        else:
            style_type = 'highlight'
        
        # 将当前样式数据传递给自定义 Label
        self.preview_label.update_style(self.xml_styles[style_type])