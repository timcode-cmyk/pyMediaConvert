import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QSpinBox, QDoubleSpinBox, QComboBox, QFontComboBox,
    QCheckBox, QPushButton, QGraphicsView, QGraphicsScene,
    QGraphicsPathItem, QGraphicsItemGroup, QColorDialog, QFileDialog,
    QMessageBox, QGridLayout, QSizePolicy
)
from PySide6.QtGui import (
    QColor, QFont, QPainterPath, QPainterPathStroker, QPen, QBrush,
    QTransform, QPainter, QFontMetrics
)
from PySide6.QtCore import Qt, Signal

from pyMediaTools.ui.styles import apply_common_style

class ColorPicker(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color_str, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 30)
        self._color_str = color_str
        self._color = self.parse_color(color_str)
        self.update_appearance()
        self.clicked.connect(self.choose_color)

    @staticmethod
    def parse_color(color_str):
        hex_str = color_str[2:-1].upper()
        if len(hex_str) == 6:
            a, b, g, r = 0, *map(lambda x: int(x, 16), [hex_str[i:i+2] for i in range(0,6,2)])
        elif len(hex_str) == 8:
            a, b, g, r = map(lambda x: int(x, 16), [hex_str[i:i+2] for i in range(0,8,2)])
        else:
            return QColor(255, 255, 255, 255)
        return QColor(r, g, b, max(0, min(255, 255 - a)))

    def choose_color(self):
        color = QColorDialog.getColor(self._color, self, "选择颜色", QColorDialog.ShowAlphaChannel)
        if color.isValid():
            self._color = color
            a, r, g, b = 255 - color.alpha(), color.red(), color.green(), color.blue()
            if a == 0:
                self._color_str = f"&H{b:02X}{g:02X}{r:02X}&"
            else:
                self._color_str = f"&H{a:02X}{b:02X}{g:02X}{r:02X}&"
            self.update_appearance()
            self.colorChanged.emit(self._color_str)

    def update_appearance(self):
        c = self._color
        text_color = "black" if (c.red() * 0.299 + c.green() * 0.587 + c.blue() * 0.114) > 186 else "white"
        self.setStyleSheet(f"background-color: rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()}); "
                           f"color: {text_color}; border: 1px solid gray; border-radius: 4px;")
        self.setText(self._color_str)

class PreviewWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.scene.setBackgroundBrush(QBrush(QColor(40, 40, 40)))
        
        self.text = "Hello\n你好啊"
        self.current_style = {}
        self.preview_group = None

    def update_preview(self, style_dict):
        self.current_style = style_dict
        self.scene.clear()
        
        font = QFont(style_dict['Fontname'], int(style_dict['Fontsize']))
        font.setBold(style_dict.get('Bold', 0) == -1)
        font.setItalic(style_dict.get('Italic', 0) == -1)
        font.setUnderline(style_dict.get('Underline', 0) == -1)
        font.setStrikeOut(style_dict.get('StrikeOut', 0) == -1)
        
        fill_color = ColorPicker.parse_color(style_dict['PrimaryColour'])
        outline_color = ColorPicker.parse_color(style_dict['OutlineColour'])
        shadow_color = ColorPicker.parse_color(style_dict['BackColour'])
        
        outline = float(style_dict.get('Outline', 0))
        shadow = float(style_dict.get('Shadow', 0))
        scale_x = float(style_dict.get('ScaleX', 100)) / 100.0
        scale_y = float(style_dict.get('ScaleY', 100)) / 100.0
        angle = -float(style_dict.get('Angle', 0))
        
        path = QPainterPath()
        y_offset = 0
        fm = QFontMetrics(font)
        for line in self.text.split('\n'):
            path.addText(0, y_offset, font, line)
            y_offset += fm.lineSpacing()
            
        boundary = path.boundingRect()
        path.translate(-boundary.center())
        
        self.preview_group = QGraphicsItemGroup()
        self.scene.addItem(self.preview_group)
        
        if style_dict.get('BorderStyle', 1) == 1:
            if shadow > 0:
                stroker = QPainterPathStroker()
                stroker.setWidth(outline * 2)
                shadow_outline_path = stroker.createStroke(path)
                
                s_fill = QGraphicsPathItem(path)
                s_fill.setBrush(QBrush(shadow_color))
                s_fill.setPen(QPen(Qt.NoPen))
                s_out = QGraphicsPathItem(shadow_outline_path)
                s_out.setBrush(QBrush(shadow_color))
                s_out.setPen(QPen(Qt.NoPen))
                
                s_fill.moveBy(shadow, shadow)
                s_out.moveBy(shadow, shadow)
                self.preview_group.addToGroup(s_fill)
                self.preview_group.addToGroup(s_out)
            
            if outline > 0:
                stroker = QPainterPathStroker()
                stroker.setWidth(outline * 2)
                outline_path = stroker.createStroke(path)
                out = QGraphicsPathItem(outline_path)
                out.setBrush(QBrush(outline_color))
                out.setPen(QPen(Qt.NoPen))
                self.preview_group.addToGroup(out)
        else:
            # Opaque Border box
            box = QGraphicsPathItem(path)
            brz = box.boundingRect()
            brz.adjust(-outline, -outline, outline, outline)
            bg_rect = self.scene.addRect(brz, QPen(Qt.NoPen), QBrush(outline_color))
            self.preview_group.addToGroup(bg_rect)
            
        fill_item = QGraphicsPathItem(path)
        fill_item.setBrush(QBrush(fill_color))
        fill_item.setPen(QPen(Qt.NoPen))
        self.preview_group.addToGroup(fill_item)
        
        t = QTransform()
        t.scale(scale_x, scale_y)
        t.rotate(angle)
        self.preview_group.setTransform(t)
        
        self.center_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scene.setSceneRect(0, 0, self.width()-5, self.height()-5)
        self.center_preview()

    def center_preview(self):
        if self.preview_group:
            self.preview_group.setPos(self.width() / 2, self.height() / 2)


class ASSEditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        apply_common_style(self)
        self.loaded_subtitle_file = None
        self.init_ui()
        self.update_preview()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # Left Panel - Forms
        left_layout = QVBoxLayout()
        form_group = QGroupBox("ASS 样式属性")
        form = QFormLayout()

        self.w_font = QFontComboBox()
        self.w_font.setCurrentFont(QFont("Arial"))
        self.w_size = QSpinBox()
        self.w_size.setRange(1, 300)
        self.w_size.setValue(40)
        
        self.w_color1 = ColorPicker("&H00FFFFFF&")
        self.w_color2 = ColorPicker("&H000000FF&")
        self.w_color3 = ColorPicker("&H00000000&")
        self.w_color4 = ColorPicker("&H80000000&")
        
        color_layout = QHBoxLayout()
        color_layout.addWidget(self.w_color1)
        color_layout.addWidget(self.w_color2)
        color_layout.addWidget(self.w_color3)
        color_layout.addWidget(self.w_color4)
        
        self.w_bold = QCheckBox("加粗")
        self.w_italic = QCheckBox("斜体")
        self.w_underline = QCheckBox("下划线")
        self.w_strikeout = QCheckBox("删除线")
        text_styles = QHBoxLayout()
        text_styles.addWidget(self.w_bold)
        text_styles.addWidget(self.w_italic)
        text_styles.addWidget(self.w_underline)
        text_styles.addWidget(self.w_strikeout)
        
        self.w_outline = QDoubleSpinBox()
        self.w_outline.setValue(2.0)
        self.w_shadow = QDoubleSpinBox()
        self.w_shadow.setValue(1.5)
        self.w_scalex = QSpinBox()
        self.w_scalex.setRange(1, 1000)
        self.w_scalex.setValue(100)
        self.w_scaley = QSpinBox()
        self.w_scaley.setRange(1, 1000)
        self.w_scaley.setValue(100)
        self.w_angle = QDoubleSpinBox()
        self.w_angle.setRange(-360, 360)
        
        self.w_bgstyle = QComboBox()
        self.w_bgstyle.addItem("描边+阴影", 1)
        self.w_bgstyle.addItem("不透明背景框", 3)
        
        self.w_align = QComboBox()
        for i in range(1, 10):
            self.w_align.addItem(f"对齐方式 {i}", i)
        self.w_align.setCurrentIndex(1) # Default alignment 2
            
        self.w_margin_l = QSpinBox(); self.w_margin_l.setMaximum(9999); self.w_margin_l.setValue(10)
        self.w_margin_r = QSpinBox(); self.w_margin_r.setMaximum(9999); self.w_margin_r.setValue(10)
        self.w_margin_v = QSpinBox(); self.w_margin_v.setMaximum(9999); self.w_margin_v.setValue(10)

        form.addRow("字体 (Fontname):", self.w_font)
        form.addRow("字号 (Fontsize):", self.w_size)
        form.addRow("颜色(主/辅/边/阴):", color_layout)
        form.addRow("文本样式:", text_styles)
        form.addRow("描边 (Outline):", self.w_outline)
        form.addRow("阴影 (Shadow):", self.w_shadow)
        form.addRow("缩放 X% (ScaleX):", self.w_scalex)
        form.addRow("缩放 Y% (ScaleY):", self.w_scaley)
        form.addRow("旋转角度 (Angle):", self.w_angle)
        form.addRow("背景框 (BorderStyle):", self.w_bgstyle)
        form.addRow("对齐模式 (Alignment):", self.w_align)
        
        margin_layout = QHBoxLayout()
        margin_layout.addWidget(QLabel("左(L):")); margin_layout.addWidget(self.w_margin_l)
        margin_layout.addWidget(QLabel("右(R):")); margin_layout.addWidget(self.w_margin_r)
        margin_layout.addWidget(QLabel("垂直(V):")); margin_layout.addWidget(self.w_margin_v)
        form.addRow("字幕边距:", margin_layout)

        form_group.setLayout(form)
        left_layout.addWidget(form_group)
        left_layout.addStretch()

        # Connect signals for updating preview
        for w in [self.w_font, self.w_size, self.w_outline, self.w_shadow, 
                  self.w_scalex, self.w_scaley, self.w_angle, self.w_bgstyle, self.w_align]:
            if isinstance(w, (QSpinBox, QDoubleSpinBox, QComboBox, QFontComboBox)):
                if hasattr(w, 'valueChanged'): w.valueChanged.connect(self.update_preview)
                if hasattr(w, 'currentIndexChanged'): w.currentIndexChanged.connect(self.update_preview)
                if hasattr(w, 'currentFontChanged'): w.currentFontChanged.connect(self.update_preview)

        for w in [self.w_bold, self.w_italic, self.w_underline, self.w_strikeout]:
            w.stateChanged.connect(self.update_preview)
            
        for w in [self.w_color1, self.w_color2, self.w_color3, self.w_color4]:
            w.colorChanged.connect(self.update_preview)

        # Right Panel - Preview & Subtitle Load
        right_layout = QVBoxLayout()
        self.preview_widget = PreviewWidget()
        self.preview_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        file_layout = QHBoxLayout()
        self.import_btn = QPushButton("导入字幕 (SRT/VTT/ASS)")
        self.import_btn.setObjectName("PrimaryButton")
        self.import_btn.clicked.connect(self.import_subtitle)
        self.file_label = QLabel("当前未导入字幕 - 保存测试效果")
        file_layout.addWidget(self.import_btn)
        file_layout.addWidget(self.file_label)
        
        save_btn = QPushButton("保存为 ASS 文件")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_ass)
        
        right_layout.addWidget(self.preview_widget, stretch=1)
        right_layout.addLayout(file_layout)
        right_layout.addWidget(save_btn)

        main_layout.addLayout(left_layout, stretch=1)
        main_layout.addLayout(right_layout, stretch=2)

    def get_current_style(self):
        return {
            'Name': 'Default',
            'Fontname': self.w_font.currentFont().family(),
            'Fontsize': self.w_size.value(),
            'PrimaryColour': self.w_color1._color_str,
            'SecondaryColour': self.w_color2._color_str,
            'OutlineColour': self.w_color3._color_str,
            'BackColour': self.w_color4._color_str,
            'Bold': -1 if self.w_bold.isChecked() else 0,
            'Italic': -1 if self.w_italic.isChecked() else 0,
            'Underline': -1 if self.w_underline.isChecked() else 0,
            'StrikeOut': -1 if self.w_strikeout.isChecked() else 0,
            'ScaleX': self.w_scalex.value(),
            'ScaleY': self.w_scaley.value(),
            'Spacing': 0,
            'Angle': self.w_angle.value(),
            'BorderStyle': self.w_bgstyle.currentData(),
            'Outline': self.w_outline.value(),
            'Shadow': self.w_shadow.value(),
            'Alignment': self.w_align.currentData(),
            'MarginL': self.w_margin_l.value(),
            'MarginR': self.w_margin_r.value(),
            'MarginV': self.w_margin_v.value(),
            'Encoding': 1
        }

    def update_preview(self, *args):
        try:
            style = self.get_current_style()
            self.preview_widget.update_preview(style)
        except Exception as e:
            print("Preview generation error:", e)

    def import_subtitle(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "选择字幕文件", "", "Subtitle files (*.srt *.vtt *.ass);;All Files (*)")
        if filepath:
            self.loaded_subtitle_file = filepath
            self.file_label.setText(f"已导入: {os.path.basename(filepath)}")
            self.file_label.setToolTip(filepath)

    def _parse_time_srt(self, t):
        t = t.strip()
        h, m, sms = t.split(':')
        s, ms = sms.replace(',', '.').split('.')
        return f"{int(h):d}:{int(m):02d}:{int(s):02d}.{ms.ljust(2,'0')[:2]}"

    def _parse_time_vtt(self, t):
        t = t.strip()
        parts = t.split(':')
        if len(parts) == 3:
            h, m, sms = parts
        else:
            h = '00'
            m, sms = parts
        s, ms = sms.split('.')
        return f"{int(h):d}:{int(m):02d}:{int(s):02d}.{ms.ljust(2,'0')[:2]}"

    def _parse_sub_file(self, path):
        ext = path.split('.')[-1].lower()
        events = []
        with open(path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            lines = [l.strip() for l in f.readlines()]
            
        if ext == 'srt':
            idx = 0
            while idx < len(lines):
                if lines[idx].isdigit():
                    idx += 1
                    if idx < len(lines) and '-->' in lines[idx]:
                        t1, t2 = lines[idx].split('-->')
                        start = self._parse_time_srt(t1)
                        end = self._parse_time_srt(t2)
                        idx += 1
                        texts = []
                        while idx < len(lines) and lines[idx]:
                            texts.append(lines[idx])
                            idx += 1
                        events.append((start, end, r"\N".join(texts)))
                idx += 1
        elif ext == 'vtt':
            idx = 0
            while idx < len(lines):
                if '-->' in lines[idx]:
                    t1, t2 = lines[idx].split('-->')
                    start = self._parse_time_vtt(t1.split()[0])
                    end = self._parse_time_vtt(t2.split()[0])
                    idx += 1
                    texts = []
                    while idx < len(lines) and lines[idx]:
                        texts.append(lines[idx])
                        idx += 1
                    events.append((start, end, r"\N".join(texts)))
                idx += 1
        elif ext == 'ass':
            for line in lines:
                if line.startswith("Dialogue:"):
                    parts = line[len("Dialogue:"):].split(',', 9)
                    if len(parts) >= 10:
                        events.append((parts[1].strip(), parts[2].strip(), parts[9].strip()))
        return events

    def save_ass(self):
        style = self.get_current_style()
        default_out_path = "output-styled.ass"
        
        if self.loaded_subtitle_file:
            base, _ = os.path.splitext(self.loaded_subtitle_file)
            default_out_path = base + "-edit.ass"
            
        out_path, _ = QFileDialog.getSaveFileName(self, "保存为 ASS 文件", default_out_path, "ASS Files (*.ass)")
        if not out_path:
            return
            
        try:
            events = []
            if self.loaded_subtitle_file:
                events = self._parse_sub_file(self.loaded_subtitle_file)
            else:
                events = [("0:00:01.00", "0:00:05.00", "测试字幕生成成功")]

            style_fmt = ["Name", "Fontname", "Fontsize", "PrimaryColour", "SecondaryColour", 
                         "OutlineColour", "BackColour", "Bold", "Italic", "Underline", "StrikeOut", 
                         "ScaleX", "ScaleY", "Spacing", "Angle", "BorderStyle", "Outline", "Shadow", 
                         "Alignment", "MarginL", "MarginR", "MarginV", "Encoding"]
            style_vals = [str(style[k]) for k in style_fmt]
            style_line = "Style: " + ",".join(style_vals)

            ass_content = f"""[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: {', '.join(style_fmt)}
{style_line}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            for start, end, text in events:
                ass_content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"

            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(ass_content)
                
            QMessageBox.information(self, "成功", f"ASS 文件已保存至:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存出错:\n{str(e)}")
