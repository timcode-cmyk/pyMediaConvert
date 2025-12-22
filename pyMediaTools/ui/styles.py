import platform
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette

__all__ = ["generate_common_qss", "apply_common_style"]


def _get_base_font():
    sys_name = platform.system()
    if sys_name == 'Darwin':
        return "SF Pro Text, Helvetica Neue, Helvetica, Arial, sans-serif"
    elif sys_name == 'Windows':
        return "Segoe UI, Microsoft YaHei, sans-serif"
    else:
        return "Roboto, Noto Sans, Arial, sans-serif"


def generate_common_qss(app: QApplication = None, font_size: int = 14) -> str:
    """Generate a common QSS string using the application's palette.

    Returns a string suitable for widget.setStyleSheet(...).
    """
    if app is None:
        app = QApplication.instance()
    palette = app.palette()

    accent_color = palette.color(QPalette.Highlight).name()
    bg_color = palette.color(QPalette.Window)
    is_dark = bg_color.lightness() < 128

    input_bg = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(0, 0, 0, 0.03)"
    border_color = "rgba(255, 255, 255, 0.15)" if is_dark else "rgba(0, 0, 0, 0.15)"
    group_bg = "rgba(255, 255, 255, 0.03)" if is_dark else "rgba(255, 255, 255, 0.6)"

    base_font = _get_base_font()

    qss = f"""
    QWidget {{
        font-family: "{base_font}";
        font-size: {font_size}px;
        color: palette(text);
    }}

    QGroupBox {{
        background-color: {group_bg};
        border: 1px solid {border_color};
        border-radius: 8px;
        margin-top: 1.2em;
        padding: 12px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        padding: 0 5px;
        left: 10px;
        font-weight: bold;
        color: {accent_color};
    }}

    QLineEdit, QComboBox, QSpinBox, QTextEdit, QTableWidget {{
        background-color: {input_bg};
        border: 1px solid {border_color};
        border-radius: 6px;
        padding: 6px;
        selection-background-color: {accent_color};
    }}
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
        border: 1px solid {accent_color};
    }}

    QPushButton {{
        background-color: {input_bg};
        border: 1px solid {border_color};
        border-radius: 6px;
        padding: 8px 14px;
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

    QPushButton#StartStopButton {{
        font-size: 15px;
        padding: 10px;
        border: none;
        color: white;
    }}
    QPushButton#StartStopButton[converting="false"] {{
        background-color: {accent_color};
    }}
    QPushButton#StartStopButton[converting="false"]:hover {{
        background-color: palette(link-visited);
    }}
    QPushButton#StartStopButton[converting="true"] {{
        background-color: #ef4444;
    }}
    QPushButton#StartStopButton[converting="true"]:hover {{
        background-color: #dc2626;
    }}

    QProgressBar {{
        border: 1px solid {border_color};
        border-radius: 6px;
        text-align: center;
        background-color: {input_bg};
        height: 16px;
        color: palette(text);
        font-size: 12px;
    }}
    QProgressBar::chunk {{
        background-color: {accent_color};
        border-radius: 5px;
    }}

    DropLineEdit {{
        border: 2px dashed {border_color};
        background-color: rgba(0,0,0,0.02);
        color: palette(mid);
        font-weight: bold;
    }}
    DropLineEdit:hover {{
        border-color: {accent_color};
        background-color: rgba(100, 100, 255, 0.05);
    }}

    QLabel#StatusLabel {{
        font-weight: bold;
        color: {accent_color};
    }}

    /* Bottom panel for SFX/TTS and similar widgets */
    #BottomPanel {{
        background-color: {group_bg};
        border-radius: 8px;
        padding: 10px;
    }}
    """

    return qss


def apply_common_style(widget, font_size: int = 14):
    """Apply generated QSS to a widget (usually the top-level widget of a UI area)."""
    app = QApplication.instance()
    qss = generate_common_qss(app=app, font_size=font_size)
    widget.setStyleSheet(qss)
