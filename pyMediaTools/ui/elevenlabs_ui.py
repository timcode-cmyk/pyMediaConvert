import os
import datetime
import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QTextEdit, QComboBox, QMessageBox, QProgressBar, QFileDialog, QSlider,
                               QGroupBox, QSizePolicy, QSpinBox, QCheckBox, QTabWidget, QScrollArea, QFrame,
                               QFontComboBox, QColorDialog, QDoubleSpinBox, QGridLayout, QDialog, QDialogButtonBox)
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
        self.setMinimumHeight(80)
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

class VoiceSettingsDialog(QDialog):
    """语音设定对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("语音设定")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        # 初始化默认值
        self.stability = 50
        self.similarity = 75
        self.style = 0
        self.speed = 100
        self.speaker_boost = True
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("调整语音生成参数")
        title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(title_label)
        
        # 设置网格
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        
        # 稳定性 (Stability)
        stability_label = QLabel("稳定性:")
        stability_label.setToolTip("控制声音的稳定性和随机性。较低值引入更多情感变化，较高值可能导致单调")
        self.slider_stability = QSlider(Qt.Horizontal)
        self.slider_stability.setRange(0, 100)
        self.slider_stability.setValue(self.stability)
        self.slider_stability.setTickPosition(QSlider.TicksBelow)
        self.slider_stability.setTickInterval(10)
        self.lbl_stability_value = QLabel(f"{self.stability}%")
        self.slider_stability.valueChanged.connect(
            lambda val: self.lbl_stability_value.setText(f"{val}%")
        )
        grid_layout.addWidget(stability_label, 0, 0)
        grid_layout.addWidget(self.slider_stability, 0, 1)
        grid_layout.addWidget(self.lbl_stability_value, 0, 2)
        
        # 相似度提升 (Similarity Boost)
        similarity_label = QLabel("相似度提升:")
        similarity_label.setToolTip("AI 应多紧密地复制原始声音")
        self.slider_similarity = QSlider(Qt.Horizontal)
        self.slider_similarity.setRange(0, 100)
        self.slider_similarity.setValue(self.similarity)
        self.slider_similarity.setTickPosition(QSlider.TicksBelow)
        self.slider_similarity.setTickInterval(10)
        self.lbl_similarity_value = QLabel(f"{self.similarity}%")
        self.slider_similarity.valueChanged.connect(
            lambda val: self.lbl_similarity_value.setText(f"{val}%")
        )
        grid_layout.addWidget(similarity_label, 1, 0)
        grid_layout.addWidget(self.slider_similarity, 1, 1)
        grid_layout.addWidget(self.lbl_similarity_value, 1, 2)
        
        # 风格 (Style)
        style_label = QLabel("风格:")
        style_label.setToolTip("风格夸张程度（增加计算资源消耗）")
        self.slider_style = QSlider(Qt.Horizontal)
        self.slider_style.setRange(0, 100)
        self.slider_style.setValue(self.style)
        self.slider_style.setTickPosition(QSlider.TicksBelow)
        self.slider_style.setTickInterval(10)
        self.lbl_style_value = QLabel(f"{self.style}%")
        self.slider_style.valueChanged.connect(
            lambda val: self.lbl_style_value.setText(f"{val}%")
        )
        grid_layout.addWidget(style_label, 2, 0)
        grid_layout.addWidget(self.slider_style, 2, 1)
        grid_layout.addWidget(self.lbl_style_value, 2, 2)
        
        # 速度 (Speed)
        speed_label = QLabel("速度:")
        speed_label.setToolTip("调整语音速度（0.7-1.2，默认1.0为正常速度）")
        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setRange(70, 120)
        self.slider_speed.setValue(self.speed)
        self.slider_speed.setTickPosition(QSlider.TicksBelow)
        self.slider_speed.setTickInterval(10)
        self.lbl_speed_value = QLabel(f"{self.speed/100:.2f}")
        self.slider_speed.valueChanged.connect(
            lambda val: self.lbl_speed_value.setText(f"{val/100:.2f}")
        )
        grid_layout.addWidget(speed_label, 3, 0)
        grid_layout.addWidget(self.slider_speed, 3, 1)
        grid_layout.addWidget(self.lbl_speed_value, 3, 2)
        
        layout.addLayout(grid_layout)
        
        # 扬声器增强 (Speaker Boost)
        self.chk_speaker_boost = QCheckBox("扬声器增强")
        self.chk_speaker_boost.setChecked(self.speaker_boost)
        self.chk_speaker_boost.setToolTip("增强与原始扬声器的相似性（会略微增加延迟）")
        layout.addWidget(self.chk_speaker_boost)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_settings(self):
        """获取当前设置"""
        return {
            'stability': self.slider_stability.value() / 100.0,
            'similarity_boost': self.slider_similarity.value() / 100.0,
            'style': self.slider_style.value() / 100.0,
            'use_speaker_boost': self.chk_speaker_boost.isChecked(),
            'speed': self.slider_speed.value() / 100.0
        }
    
    def set_settings(self, settings):
        """设置对话框的值"""
        if 'stability' in settings:
            val = int(settings['stability'] * 100)
            self.slider_stability.setValue(val)
            self.stability = val
        if 'similarity_boost' in settings:
            val = int(settings['similarity_boost'] * 100)
            self.slider_similarity.setValue(val)
            self.similarity = val
        if 'style' in settings:
            val = int(settings['style'] * 100)
            self.slider_style.setValue(val)
            self.style = val
        if 'speed' in settings:
            val = int(settings['speed'] * 100)
            self.slider_speed.setValue(val)
            self.speed = val
        if 'use_speaker_boost' in settings:
            self.chk_speaker_boost.setChecked(settings['use_speaker_boost'])
            self.speaker_boost = settings['use_speaker_boost']

class SubtitleSettingsDialog(QDialog):
    """字幕设置对话框 - 整合 Groq 配置和 XML 样式设置"""
    def __init__(self, parent=None, xml_styles=None, video_settings=None, groq_settings=None):
        super().__init__(parent)
        self.setWindowTitle("字幕设置")
        self.setModal(True)
        self.setMinimumSize(700, 700)  # 增加高度以防止内容被压缩
        
        self.parent_widget = parent
        self.xml_styles = xml_styles or {}
        self.video_settings = video_settings or {}
        self.groq_settings = groq_settings or {'api_key': '', 'model': 'openai/gpt-oss-120b'}
        
        # QSettings for Groq persistence
        self.groq_qsettings = QSettings("pyMediaTools", "Groq")
        
        self.setup_ui()
        self.load_groq_settings()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题
        title_label = QLabel("字幕与样式设置")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(title_label)
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # Tab 1: 常规设置 (Groq + 视频)
        self.general_tab = self.create_general_settings_tab()
        self.tabs.addTab(self.general_tab, "常规设置")
        
        # Tab 2-4: XML 样式设置 (从父控件获取)
        if self.parent_widget and hasattr(self.parent_widget, 'create_style_settings_panel'):
            # 为每个样式面板增加滚动区域，防止被压缩切字
            def wrap_with_scroll(widget):
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QFrame.NoFrame)
                scroll.setWidget(widget)
                return scroll

            source_tab = wrap_with_scroll(self.parent_widget.create_style_settings_panel('source'))
            self.tabs.addTab(source_tab, "原文样式")
            
            trans_tab = wrap_with_scroll(self.parent_widget.create_style_settings_panel('translate'))
            self.tabs.addTab(trans_tab, "翻译样式")
            
            highlight_tab = wrap_with_scroll(self.parent_widget.create_style_settings_panel('highlight'))
            self.tabs.addTab(highlight_tab, "高亮样式")
        
        self.tabs.setCurrentIndex(0)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        layout.addWidget(self.tabs)
        
        # 预览面板 (创建新的预览标签，避免Qt对象生命周期问题)
        self.preview_group = QGroupBox("样式预览")
        preview_layout = QVBoxLayout(self.preview_group)
        self.dialog_preview_label = SubtitlePreviewLabel()
        preview_layout.addWidget(self.dialog_preview_label)
        layout.addWidget(self.preview_group)
        
        # 初始可见性设置
        self.on_tab_changed(self.tabs.currentIndex())
        
        # 如果父控件有预览更新方法，连接样式变化事件
        if self.parent_widget and hasattr(self.parent_widget, 'update_preview'):
            # 初始化预览
            current_tab = self.tabs.currentIndex()
            if current_tab >= 1 and current_tab <= 3:  # XML style tabs
                style_types = ['source', 'translate', 'highlight']
                if current_tab - 1 < len(style_types):
                    style_type = style_types[current_tab - 1]
                    if style_type in self.xml_styles:
                        self.dialog_preview_label.update_style(self.xml_styles[style_type])
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def on_tab_changed(self, index):
        """当标签页切换时更新预览显示"""
        if hasattr(self, 'preview_group'):
            # 只有切换到样式设置页 (1, 2, 3) 时显示预览，常规设置 (0) 隐藏
            self.preview_group.setVisible(index > 0)
        
        # 触发父窗口的整体预览更新逻辑
        if self.parent_widget and hasattr(self.parent_widget, 'update_preview'):
            self.parent_widget.update_preview()
    
    def create_general_settings_tab(self):
        """创建常规设置标签页 (Groq + 视频)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Scroll Area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)
        
        # --- 1. Groq 配置 ---
        groq_group = QGroupBox("Groq API 配置")
        groq_layout = QVBoxLayout(groq_group)
        
        # API Key
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("API Key:"))
        self.groq_api_input = QLineEdit()
        self.groq_api_input.setEchoMode(QLineEdit.Password)
        self.groq_api_input.setPlaceholderText("gsk_...")
        key_layout.addWidget(self.groq_api_input, 1)
        self.btn_save_groq = QPushButton("💾 保存")
        self.btn_save_groq.setFixedWidth(80)
        self.btn_save_groq.clicked.connect(self.save_groq_api_key)
        key_layout.addWidget(self.btn_save_groq)
        groq_layout.addLayout(key_layout)
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("选择模型:"))
        self.groq_model_combo = QComboBox()
        self.groq_model_combo.addItems([
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile",
            "meta-llama/llama-guard-4-12b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b"
        ])
        self.groq_model_combo.setCurrentText(self.groq_settings.get('model', 'openai/gpt-oss-120b'))
        model_layout.addWidget(self.groq_model_combo, 1)
        groq_layout.addLayout(model_layout)
        
        # 模型说明
        model_info = QLabel(
            "• llama-3.1-8b-instant: 快速响应\n"
            "• llama-3.3-70b-versatile: 平衡性能和质量\n"
            "• meta-llama/llama-guard-4-12b: 内容审核\n"
            "• openai/gpt-oss-120b: 推荐使用，大模型，最高质量\n"
            "• openai/gpt-oss-20b: 中型模型"
        )
        model_info.setStyleSheet("color: palette(mid); font-size: 11pt; font-weight: bold;")
        groq_layout.addWidget(model_info)
        
        scroll_layout.addWidget(groq_group)
        
        # --- 2. 视频参数 ---
        video_group = QGroupBox("视频参数设置")
        video_layout = QGridLayout(video_group)
        video_layout.setSpacing(10)
        
        video_layout.addWidget(QLabel("帧率 (FPS):"), 0, 0)
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["24", "25", "30", "60"])
        fps_str = str(self.video_settings.get('fps', 30))
        if self.combo_fps.findText(fps_str) != -1:
            self.combo_fps.setCurrentText(fps_str)
        video_layout.addWidget(self.combo_fps, 0, 1)
        
        video_layout.addWidget(QLabel("目标分辨率:"), 1, 0)
        self.combo_res = QComboBox()
        self.combo_res.addItems(["1080p (1920x1080)", "2K (2560x1440)", "4K (3840x2160)"])
        # 根据当前 width/height 设置初始分辨率
        w, h = self.video_settings.get('width', 1080), self.video_settings.get('height', 1920)
        max_dim = max(w, h)
        if max_dim >= 3840: self.combo_res.setCurrentIndex(2)
        elif max_dim >= 2560: self.combo_res.setCurrentIndex(1)
        else: self.combo_res.setCurrentIndex(0)
        video_layout.addWidget(self.combo_res, 1, 1)
        
        self.chk_vertical = QCheckBox("使用竖屏分辨率 (旋转画布)")
        # 默认启用竖屏
        is_vert = w < h
        self.chk_vertical.setChecked(is_vert)
        video_layout.addWidget(self.chk_vertical, 2, 0, 1, 2)
        
        scroll_layout.addWidget(video_group)

        # --- 3. 字幕切分规则 ---
        split_group = QGroupBox("字幕切分规则")
        split_layout = QVBoxLayout(split_group)
        split_layout.setSpacing(12)
        
        # 断行阈值
        pause_item_layout = QVBoxLayout()
        pause_head_layout = QHBoxLayout()
        pause_head_layout.addWidget(QLabel("<b>断行阈值 (停顿时间)</b>"))
        pause_head_layout.addStretch()
        self.lbl_pause_val = QLabel(f"{self.video_settings.get('srt_pause_threshold', 0.2):.2f}s")
        self.lbl_pause_val.setStyleSheet("color: #3b82f6; font-weight: bold;")
        pause_head_layout.addWidget(self.lbl_pause_val)
        pause_item_layout.addLayout(pause_head_layout)
        
        pause_slider_layout = QHBoxLayout()
        self.pause_slider = QSlider(Qt.Horizontal)
        self.pause_slider.setRange(0, 100)
        self.pause_slider.setValue(int(self.video_settings.get('srt_pause_threshold', 0.2) * 100))
        pause_slider_layout.addWidget(self.pause_slider)
        pause_item_layout.addLayout(pause_slider_layout)
        
        pause_info = QLabel("说明: 词间停顿超过此阈值即触发换行")
        pause_info.setStyleSheet("color: palette(mid); font-size: 9pt;")
        pause_item_layout.addWidget(pause_info)
        split_layout.addLayout(pause_item_layout)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: palette(midlight);")
        split_layout.addWidget(line)
        
        # 最大字符数
        max_chars_item_layout = QVBoxLayout()
        max_chars_head_layout = QHBoxLayout()
        max_chars_head_layout.addWidget(QLabel("<b>每行最大字符数</b>"))
        max_chars_head_layout.addStretch()
        self.lbl_max_chars_val = QLabel(str(self.video_settings.get('srt_max_chars', 35)))
        self.lbl_max_chars_val.setStyleSheet("color: #3b82f6; font-weight: bold;")
        max_chars_head_layout.addWidget(self.lbl_max_chars_val)
        max_chars_item_layout.addLayout(max_chars_head_layout)
        
        max_chars_slider_layout = QHBoxLayout()
        self.max_chars_slider = QSlider(Qt.Horizontal)
        self.max_chars_slider.setRange(20, 50)
        self.max_chars_slider.setValue(int(self.video_settings.get('srt_max_chars', 35)))
        max_chars_slider_layout.addWidget(self.max_chars_slider)
        max_chars_item_layout.addLayout(max_chars_slider_layout)
        
        max_chars_info = QLabel("说明: 单行超过此长度将尝试换行")
        max_chars_info.setStyleSheet("color: palette(mid); font-size: 9pt;")
        max_chars_item_layout.addWidget(max_chars_info)
        split_layout.addLayout(max_chars_item_layout)
        
        self.pause_slider.valueChanged.connect(self.on_pause_changed)
        self.max_chars_slider.valueChanged.connect(self.on_max_chars_changed)
        
        scroll_layout.addWidget(split_group)
        
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        return widget

    def on_pause_changed(self, value):
        """断行阈值数值变化回调"""
        duration = value / 100.0
        self.lbl_pause_val.setText(f"{duration:.2f}s")

    def on_max_chars_changed(self, value):
        """最大字符数变化回调"""
        self.lbl_max_chars_val.setText(str(value))
    
    def load_groq_settings(self):
        """从 QSettings 加载 Groq 配置"""
        saved_key = self.groq_qsettings.value("api_key", "")
        saved_model = self.groq_qsettings.value("model", "openai/gpt-oss-120b")
        
        if saved_key:
            self.groq_api_input.setText(saved_key)
            self.groq_settings['api_key'] = saved_key
        
        if saved_model:
            self.groq_model_combo.setCurrentText(saved_model)
            self.groq_settings['model'] = saved_model
    
    def save_groq_api_key(self):
        """保存 Groq API Key 到 QSettings"""
        api_key = self.groq_api_input.text().strip()
        self.groq_qsettings.setValue("api_key", api_key)
        QMessageBox.information(self, "保存成功", "Groq API Key 已保存到本地配置。")
    
    def get_groq_settings(self):
        """获取当前 Groq 设置"""
        # Also save model to QSettings
        model = self.groq_model_combo.currentText()
        self.groq_qsettings.setValue("model", model)
        
        return {
            'api_key': self.groq_api_input.text().strip(),
            'model': model
        }
    
    def get_video_settings(self):
        """获取视频设置"""
        width, height = 1920, 1080
        res_text = self.combo_res.currentText()
        if "2K" in res_text:
            width, height = 2560, 1440
        elif "4K" in res_text:
            width, height = 3840, 2160
        
        if self.chk_vertical.isChecked():
            width, height = height, width
        
        return {
            'fps': int(self.combo_fps.currentText()),
            'width': width,
            'height': height,
            'srt_pause_threshold': self.pause_slider.value() / 100.0,
            'srt_max_chars': self.max_chars_slider.value()
        }

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
        
        # 视频设置 (默认竖屏)
        self.video_settings = {
            'fps': 30,
            'width': 1080,
            'height': 1920,
            'srt_pause_threshold': 0.2,  # 停顿阈值
            'srt_max_chars': 35,         # 单行最大字符数
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
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
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
            voice_settings=self.voice_settings
        )
        self.tts_worker.finished.connect(self.on_generation_success)
        self.tts_worker.error.connect(self.on_error)
        self.tts_worker.start()
    
    def open_voice_settings(self):
        """打开语音设定对话框"""
        dialog = VoiceSettingsDialog(self)
        dialog.set_settings(self.voice_settings)
        
        if dialog.exec() == QDialog.Accepted:
            # 更新语音设定
            self.voice_settings = dialog.get_settings()
            logger.info(f"语音设定已更新: {self.voice_settings}")
    
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