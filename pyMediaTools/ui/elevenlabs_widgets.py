import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTextEdit, QScrollArea, QFrame,
                               QSizePolicy, QMessageBox)
from PySide6.QtCore import Qt, QMimeData, QSettings, QRectF
from PySide6.QtGui import (QDrag, QSyntaxHighlighter, QTextCharFormat, QColor, 
                           QPainter, QPainterPath, QPen, QBrush, QFontMetrics, QFont)

from ..logging_config import get_logger
from ..core.groq_analysis import EmotionAnalysisWorker

logger = get_logger(__name__)

class EmotionTagButton(QPushButton):
    """可拖动的情绪标签按钮（支持按组设置颜色）"""
    def __init__(self, emotion_key, emotion_info, group='emotion', parent=None):
        super().__init__(parent)
        self.emotion_key = emotion_key
        self.emotion_info = emotion_info
        self.group = group
        # 显示中文+表情
        self.setText(f"{emotion_info.get('emoji','')} {emotion_info.get('name','')}")
        self.setToolTip(emotion_info.get('description',''))
        self.setCheckable(False)
        # 根据组设置不同颜色
        if self.group == 'emotion':
            bg = '#FFB86B'  # 浅橙色
            border = '#E79A40'
            fg = '#4a2b00'
            hover_bg = '#E7A45B'
        else:
            bg = '#6DD3C3'  # 浅青色
            border = '#49b3a3'
            fg = '#003633'
            hover_bg = '#59BCAB'

        self.setStyleSheet(f"""
            QPushButton {{
                padding: 5px 10px;
                border-radius: 4px;
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
        """)
    
    def mouseMoveEvent(self, event):
        """支持拖动 - 拖动时使用中文+表情，但提交时会转换为英文"""
        if event.buttons() == Qt.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            # 拖动数据中同时包含英文标签（用于API）和计算位置
            display_text = f"{self.emotion_info['emoji']} {self.emotion_info['name']}"
            mime_data.setText(f"[{self.emotion_key}] ")  # 为了兼容，保留英文标签在文本上
            # 使用自定义MIME类型来传递完整信息
            mime_data.setData("application/x-emotion-tag", f"{self.emotion_key}|{display_text}".encode())
            drag.setMimeData(mime_data)
            drag.exec(Qt.CopyAction)


class EmotionSyntaxHighlighter(QSyntaxHighlighter):
    """情绪标签的语法高亮器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        from ..core.elevenlabs import EMOTION_DISPLAY_MAP
        self.emotion_map = EMOTION_DISPLAY_MAP
    
    def highlightBlock(self, text):
        """对文本块进行高亮"""
        # 匹配所有的[...]格式，包括带空格的标签
        pattern = r'\[([^\[\]]+)\]'
        for match in re.finditer(pattern, text):
            start = match.start()
            length = match.end() - start
            emotion_key = match.group(1)
            
            # 检查是否是有效的情绪标签
            if emotion_key in self.emotion_map:
                # 创建高亮格式
                fmt = QTextCharFormat()
                fmt.setBackground(QColor("#FFE4B5"))  # 浅橙色背景
                fmt.setForeground(QColor("#FF8C00"))  # 深橙色文字
                fmt.setFontWeight(600)  # 加粗
                
                # 应用高亮
                self.setFormat(start, length, fmt)


class EmotionHighlightTextEdit(QTextEdit):
    """支持情绪标签高亮显示的文本编辑器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # 创建情绪标签的语法高亮器
        self.emotion_highlighter = EmotionSyntaxHighlighter(self.document())
    
    def dragEnterEvent(self, event):
        """处理拖入事件"""
        if event.mimeData().hasText() or event.mimeData().hasFormat("application/x-emotion-tag"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """处理拖动中事件 - 更新光标位置到鼠标位置"""
        if event.mimeData().hasText() or event.mimeData().hasFormat("application/x-emotion-tag"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """处理拖放释放事件"""
        if event.mimeData().hasFormat("application/x-emotion-tag"):
            raw = event.mimeData().data("application/x-emotion-tag")
            try:
                data = bytes(raw).decode()
            except Exception:
                try:
                    data = raw.data().decode()
                except Exception:
                    data = str(raw)
            emotion_key, _ = data.split('|')
            pos = event.position().toPoint()
            cursor = self.cursorForPosition(pos)
            cursor.insertText(f"[{emotion_key}] ")
            self.setTextCursor(cursor)
            event.accept()
        elif event.mimeData().hasText():
            emotion_tag = event.mimeData().text()
            pos = event.position().toPoint()
            cursor = self.cursorForPosition(pos)
            cursor.insertText(emotion_tag)
            self.setTextCursor(cursor)
            event.accept()
        else:
            event.ignore()


class EmotionTagManager(QWidget):
    """情绪标签管理器 - 用于v3模型的情绪标签管理"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text_edit = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        self.btn_auto_insert = QPushButton("优化情绪")
        self.btn_auto_insert.setToolTip("分析文案，自动在合适位置插入情绪标签 (使用 Groq AI)")
        self.btn_auto_insert.clicked.connect(self.auto_insert_emotions)
        top_row.addWidget(self.btn_auto_insert)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedHeight(45)

        scroll_content = QWidget()
        self.tags_layout = QHBoxLayout(scroll_content)
        self.tags_layout.setContentsMargins(2, 2, 2, 2)
        self.tags_layout.setSpacing(4)
        self.scroll.setWidget(scroll_content)

        top_row.addWidget(self.scroll, 1)

        self.btn_group_emotion = QPushButton("情绪")
        self.btn_group_tone = QPushButton("语气")
        self.btn_group_emotion.setCheckable(True)
        self.btn_group_tone.setCheckable(True)
        self.btn_group_emotion.setChecked(True)
        self.btn_group_emotion.clicked.connect(lambda: self.show_group('emotion'))
        self.btn_group_tone.clicked.connect(lambda: self.show_group('tone'))
        top_row.addWidget(self.btn_group_emotion)
        top_row.addWidget(self.btn_group_tone)

        top_widget = QWidget()
        top_widget.setLayout(top_row)
        top_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_widget.setFixedHeight(55)
        layout.addWidget(top_widget)

        self.groups = {
            'emotion': [
                'happy','sad','excited','angry','whisper','annoyed','appalled','thoughtful','surprised'
            ],
            'tone': [
                'laughing','chuckles','sighs','clears throat','short pause','long pause','exhales sharply','inhales deeply'
            ]
        }

        self.current_group = 'emotion'
        self._populate_tags()
    
    def set_text_edit(self, text_edit):
        self.text_edit = text_edit
    
    def _populate_tags(self):
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        for tag in self.groups.get(self.current_group, []):
            from ..core.elevenlabs import EMOTION_OPTIONS
            emotion_info = EMOTION_OPTIONS.get(tag, {'name': tag, 'description': tag, 'emoji': ''})
            btn = EmotionTagButton(tag, emotion_info, group=self.current_group, parent=self)
            btn.clicked.connect(lambda checked, t=tag: self._insert_tag(t))
            self.tags_layout.addWidget(btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.tags_layout.addWidget(spacer)

    def show_group(self, group_name):
        if group_name not in self.groups:
            return
        self.current_group = group_name
        self.btn_group_emotion.setChecked(group_name == 'emotion')
        self.btn_group_tone.setChecked(group_name == 'tone')
        self._populate_tags()

    def auto_insert_emotions(self):
        """异步调用 Groq API 分析文本并插入情绪标签"""
        if not self.text_edit:
            return
            
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "请先输入需要分析的文本。")
            return

        # 查找提供 Groq 设置的祖先组件 (通常是 ElevenLabsWidget)
        parent_ui = self.parent()
        while parent_ui and not hasattr(parent_ui, 'get_groq_settings'):
            parent_ui = parent_ui.parent()
            
        if not parent_ui:
            # 如果在父级树中没找到，回退到 window()
            parent_ui = self.window()
            
        if not hasattr(parent_ui, 'get_groq_settings'):
            QMessageBox.warning(self, "错误", "无法获取 Groq 配置。")
            return
            
        groq_cfg = parent_ui.get_groq_settings()
        if not groq_cfg.get('api_key'):
            QMessageBox.warning(self, "错误", "请先在'字幕设置 -> 常规'中配置 Groq API Key。")
            return

        self.btn_auto_insert.setEnabled(False)
        self.btn_auto_insert.setText("分析中...")
        
        self.worker = EmotionAnalysisWorker(
            api_key=groq_cfg['api_key'],
            model=groq_cfg['model'],
            text=text
        )
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_analysis_error)
        self.worker.start()

    def on_analysis_finished(self, improved_text):
        self.btn_auto_insert.setEnabled(True)
        self.btn_auto_insert.setText("优化情绪")
        
        if improved_text:
            self.text_edit.setPlainText(improved_text)
            QMessageBox.information(self, "完成", "情绪优化已完成，已更新文本。")
        else:
            QMessageBox.warning(self, "提示", "AI 未返回优化后的文本，请稍后重试。")

    def on_analysis_error(self, error_msg):
        self.btn_auto_insert.setEnabled(True)
        self.btn_auto_insert.setText("优化情绪")
        QMessageBox.warning(self, "分析失败", f"Groq API 调用失败: {error_msg}")

    def get_emotion_tags(self):
        if not self.text_edit:
            return {}
        text = self.text_edit.toPlainText()
        pattern = r'\[(\w+)\]'
        matches = re.findall(pattern, text)
        return {emotion: text.count(f'[{emotion}]') for emotion in matches}


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

        s = self.style_data
        if not s:
            super().paintEvent(event)
            return

        font = QFont(s.get('font', 'Arial'), s.get('fontSize', 50))
        font.setBold(s.get('bold', False))
        font.setItalic(s.get('italic', False))
        painter.setFont(font)

        fc = s.get('fontColor', (1, 1, 1, 1))
        font_color = QColor.fromRgbF(*fc)
        
        if s.get('useBackground', False):
            bc = s.get('backgroundColor', (0, 0, 0, 0))
            bg_color = QColor.fromRgbF(*bc)
            padding = s.get('backgroundPadding', 0)
            
            metrics = QFontMetrics(font)
            line_height = metrics.height()
            lines = self.text().split('\n')
            max_width = 0
            total_height = len(lines) * line_height + (len(lines) - 1) * s.get('lineSpacing', 0)
            
            for line in lines:
                max_width = max(max_width, metrics.horizontalAdvance(line))
            
            cx, cy = self.width() / 2, self.height() / 2
            bg_rect = QRectF(cx - max_width/2 - padding, cy - total_height/2 - padding, 
                             max_width + padding*2, total_height + padding*2)
            
            painter.setBrush(QBrush(bg_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bg_rect, 8, 8)

        path = QPainterPath()
        metrics = QFontMetrics(font)
        line_height = metrics.height()
        lines = self.text().split('\n')
        spacing = s.get('lineSpacing', 0)
        content_height = len(lines) * line_height + (len(lines) - 1) * spacing
        y = (self.height() - content_height) / 2 + metrics.ascent()
        
        for line in lines:
            text_width = metrics.horizontalAdvance(line)
            x = (self.width() - text_width) / 2
            path.addText(x, y, font, line)
            y += line_height + spacing

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

        if s.get('useStroke', False):
            stc = s.get('strokeColor', (0, 0, 0, 1))
            stroke_color = QColor.fromRgbF(*stc)
            stroke_width = s.get('strokeWidth', 0)
            
            if stroke_width > 0:
                pen = QPen(stroke_color, stroke_width)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(path)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(font_color))
        painter.drawPath(path)
