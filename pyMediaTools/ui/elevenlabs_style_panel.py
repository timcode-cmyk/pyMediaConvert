"""
elevenlabs_style_panel.py
~~~~~~~~~~~~~~~~~~~~~~~~~
FCPXML 字幕 XML 样式编辑器面板与默认样式构造器。
从 elevenlabs_ui.py 拆分独立，解除对话框与主窗体的反向紧耦合。
"""

import copy
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


DEFAULT_XML_STYLES = {
    "source": {
        "alignment": "center",
        "fontColor": (1.0, 1.0, 1.0, 1.0),
        "font": "Arial",
        "fontSize": 50,
        "bold": False,
        "italic": False,
        "strokeColor": (0.0, 0.0, 0.0, 1.0),
        "strokeWidth": 2.0,
        "useStroke": False,
        "lineSpacing": 0,
        "pos": -45,
        "shadowColor": (0.0, 0.0, 0.0, 0.5),
        "shadowOffset": (2, 2),
        "useShadow": True,
        "backgroundColor": (0.0, 0.0, 0.0, 0.0),
        "useBackground": False,
        "backgroundPadding": 0,
    },
    "translate": {
        "alignment": "center",
        "fontColor": (1.0, 1.0, 1.0, 1.0),
        "font": "Arial",
        "fontSize": 40,
        "bold": False,
        "italic": False,
        "strokeColor": (0.0, 0.0, 0.0, 1.0),
        "strokeWidth": 2.0,
        "useStroke": True,
        "lineSpacing": 0,
        "pos": -38,
        "shadowColor": (0.0, 0.0, 0.0, 0.5),
        "shadowOffset": (2, 2),
        "useShadow": True,
        "backgroundColor": (0.0, 0.0, 0.0, 0.0),
        "useBackground": True,
        "backgroundPadding": 0,
    },
    "highlight": {
        "alignment": "center",
        "fontColor": (1.0, 1.0, 0.0, 1.0),
        "font": "Arial",
        "fontSize": 50,
        "bold": True,
        "italic": False,
        "strokeColor": (0.0, 0.0, 0.0, 1.0),
        "strokeWidth": 2.0,
        "useStroke": False,
        "lineSpacing": 0,
        "pos": -45,
        "shadowColor": (0.0, 0.0, 0.0, 0.5),
        "shadowOffset": (2, 2),
        "useShadow": True,
        "backgroundColor": (0.0, 0.0, 0.0, 0.0),
        "useBackground": False,
        "backgroundPadding": 0,
    },
}


def build_default_xml_styles() -> dict:
    """返回默认 XML 字幕样式配置字典的深拷贝。"""
    return copy.deepcopy(DEFAULT_XML_STYLES)


class SubtitleStylePanel(QWidget):
    """字幕样式设置面板（原文/翻译/高亮通用）。"""

    style_changed = Signal(str)

    def __init__(self, style_type: str, xml_styles: dict, parent=None):
        super().__init__(parent)
        self.style_type = style_type
        self.xml_styles = xml_styles
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)

        style_cfg = self.xml_styles[self.style_type]

        # --- 1. 基础字体设置 ---
        font_group = QGroupBox("基础字体")
        font_layout = QGridLayout(font_group)
        font_layout.setSpacing(8)

        font_combo = QFontComboBox()
        font_combo.setCurrentFont(QFont(style_cfg["font"]))
        font_combo.setToolTip("选择字体")
        font_combo.currentFontChanged.connect(
            lambda font: self.update_style("font", font.family())
        )
        font_layout.addWidget(QLabel("字体:"), 0, 0)
        font_layout.addWidget(font_combo, 0, 1, 1, 3)

        size_spin = QSpinBox()
        size_spin.setRange(10, 200)
        size_spin.setValue(style_cfg["fontSize"])
        size_spin.setSuffix(" px")
        size_spin.setToolTip("字体大小")
        size_spin.valueChanged.connect(lambda val: self.update_style("fontSize", val))
        font_layout.addWidget(QLabel("大小:"), 1, 0)
        font_layout.addWidget(size_spin, 1, 1)

        font_color_btn = QPushButton()
        font_color_btn.setToolTip("字体颜色")
        self.set_button_color(font_color_btn, style_cfg["fontColor"])
        font_color_btn.clicked.connect(
            lambda: self.pick_color("fontColor", font_color_btn)
        )
        font_layout.addWidget(QLabel("颜色:"), 1, 2)
        font_layout.addWidget(font_color_btn, 1, 3)

        style_layout = QHBoxLayout()
        bold_chk = QCheckBox("加粗")
        bold_chk.setToolTip("加粗")
        bold_chk.setChecked(style_cfg["bold"])
        bold_chk.toggled.connect(lambda checked: self.update_style("bold", checked))
        italic_chk = QCheckBox("斜体")
        italic_chk.setToolTip("斜体")
        italic_chk.setChecked(style_cfg["italic"])
        italic_chk.toggled.connect(lambda checked: self.update_style("italic", checked))
        style_layout.addWidget(bold_chk)
        style_layout.addWidget(italic_chk)
        style_layout.addStretch()
        font_layout.addWidget(QLabel("样式:"), 2, 0)
        font_layout.addLayout(style_layout, 2, 1, 1, 3)

        align_combo = QComboBox()
        align_combo.addItems(["left", "center", "right"])
        align_combo.setCurrentText(style_cfg["alignment"])
        align_combo.currentTextChanged.connect(
            lambda val: self.update_style("alignment", val)
        )
        font_layout.addWidget(QLabel("对齐:"), 3, 0)
        font_layout.addWidget(align_combo, 3, 1)

        pos_spin = QSpinBox()
        pos_spin.setRange(-1000, 1000)
        pos_spin.setValue(style_cfg["pos"])
        pos_spin.setToolTip("Y轴位置 (向上为负，向下为正)")
        pos_spin.valueChanged.connect(lambda val: self.update_style("pos", val))
        font_layout.addWidget(QLabel("Y轴位置:"), 3, 2)
        font_layout.addWidget(pos_spin, 3, 3)

        main_layout.addWidget(font_group)

        # --- 2. 效果设置 (描边 + 阴影) ---
        effect_group = QGroupBox("效果设置 (描边 & 阴影)")
        effect_layout = QVBoxLayout(effect_group)
        effect_layout.setSpacing(10)

        stroke_layout = QHBoxLayout()
        stroke_chk = QCheckBox("描边")
        stroke_chk.setChecked(style_cfg.get("useStroke", False))
        stroke_chk.toggled.connect(
            lambda checked: self.update_style("useStroke", checked)
        )
        stroke_layout.addWidget(stroke_chk)

        stroke_width_spin = QDoubleSpinBox()
        stroke_width_spin.setRange(0, 20)
        stroke_width_spin.setValue(style_cfg["strokeWidth"])
        stroke_width_spin.setSingleStep(0.5)
        stroke_width_spin.setSuffix(" px")
        stroke_width_spin.valueChanged.connect(
            lambda val: self.update_style("strokeWidth", val)
        )
        stroke_chk.toggled.connect(stroke_width_spin.setEnabled)
        stroke_width_spin.setEnabled(stroke_chk.isChecked())
        stroke_layout.addWidget(stroke_width_spin)

        stroke_color_btn = QPushButton()
        stroke_color_btn.setToolTip("描边颜色")
        stroke_color_btn.setFixedWidth(40)
        self.set_button_color(stroke_color_btn, style_cfg["strokeColor"])
        stroke_color_btn.clicked.connect(
            lambda: self.pick_color("strokeColor", stroke_color_btn)
        )
        stroke_chk.toggled.connect(stroke_color_btn.setEnabled)
        stroke_color_btn.setEnabled(stroke_chk.isChecked())
        stroke_layout.addWidget(stroke_color_btn)
        stroke_layout.addStretch()

        shadow_layout = QHBoxLayout()
        shadow_chk = QCheckBox("阴影")
        shadow_chk.setChecked(style_cfg.get("useShadow", False))
        shadow_chk.toggled.connect(
            lambda checked: self.update_style("useShadow", checked)
        )
        shadow_layout.addWidget(shadow_chk)

        shadow_x = QSpinBox()
        shadow_x.setRange(-50, 50)
        shadow_x.setValue(style_cfg["shadowOffset"][0])
        shadow_x.setPrefix("X:")
        shadow_x.setFixedWidth(60)
        shadow_x.valueChanged.connect(
            lambda val: self.update_shadow_offset(val, None)
        )
        shadow_chk.toggled.connect(shadow_x.setEnabled)
        shadow_x.setEnabled(shadow_chk.isChecked())
        shadow_layout.addWidget(shadow_x)

        shadow_y = QSpinBox()
        shadow_y.setRange(-50, 50)
        shadow_y.setValue(style_cfg["shadowOffset"][1])
        shadow_y.setPrefix("Y:")
        shadow_y.setFixedWidth(60)
        shadow_y.valueChanged.connect(
            lambda val: self.update_shadow_offset(None, val)
        )
        shadow_chk.toggled.connect(shadow_y.setEnabled)
        shadow_y.setEnabled(shadow_chk.isChecked())
        shadow_layout.addWidget(shadow_y)

        shadow_color_btn = QPushButton()
        shadow_color_btn.setToolTip("阴影颜色")
        shadow_color_btn.setFixedWidth(40)
        self.set_button_color(shadow_color_btn, style_cfg["shadowColor"])
        shadow_color_btn.clicked.connect(
            lambda: self.pick_color("shadowColor", shadow_color_btn)
        )
        shadow_chk.toggled.connect(shadow_color_btn.setEnabled)
        shadow_color_btn.setEnabled(shadow_chk.isChecked())
        shadow_layout.addWidget(shadow_color_btn)
        shadow_layout.addStretch()

        effect_layout.addLayout(stroke_layout)
        effect_layout.addLayout(shadow_layout)
        main_layout.addWidget(effect_group)
        main_layout.addStretch()

    @staticmethod
    def set_button_color(button: QPushButton, color_tuple):
        """设置按钮的背景颜色以反映 RGBA 颜色。"""
        if isinstance(color_tuple, (list, tuple)) and len(color_tuple) >= 4:
            r, g, b, a = (
                int(color_tuple[0] * 255),
                int(color_tuple[1] * 255),
                int(color_tuple[2] * 255),
                int(color_tuple[3] * 255),
            )
        else:
            r, g, b, a = 255, 255, 255, 255

        qcolor = QColor(r, g, b, a)
        button.setStyleSheet(f"background-color: {qcolor.name()}; border-radius: 4px;")
        button.setFixedHeight(32)

    def pick_color(self, key: str, button: QPushButton):
        """打开颜色选择对话框。"""
        current_color = self.xml_styles[self.style_type][key]
        if isinstance(current_color, (list, tuple)):
            r, g, b, a = (
                int(current_color[0] * 255),
                int(current_color[1] * 255),
                int(current_color[2] * 255),
                int(current_color[3] * 255),
            )
            initial_color = QColor(r, g, b, a)
        else:
            initial_color = QColor(255, 255, 255, 255)

        color = QColorDialog.getColor(initial_color, self, f"选择{key}颜色")
        if color.isValid():
            r, g, b, a = color.getRgb()
            color_tuple = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
            self.update_style(key, color_tuple)
            self.set_button_color(button, color_tuple)

    def update_style(self, key: str, value):
        """更新样式设置并通知刷新预览。"""
        self.xml_styles[self.style_type][key] = value
        self.style_changed.emit(self.style_type)

    def update_shadow_offset(self, x=None, y=None):
        """更新阴影偏移并通知刷新预览。"""
        current = list(self.xml_styles[self.style_type]["shadowOffset"])
        if x is not None:
            current[0] = x
        if y is not None:
            current[1] = y
        self.xml_styles[self.style_type]["shadowOffset"] = tuple(current)
        self.style_changed.emit(self.style_type)
