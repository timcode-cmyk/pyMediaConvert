import os
import sys
import platform
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import QObject, Signal, Slot
from pyMediaTools import get_logger

logger = get_logger(__name__)

__all__ = ["ThemeManager", "apply_common_style"]

class ThemeManager(QObject):
    _instance = None
    
    # Colors for substitution
    DARK_ACCENT = "#7C4DFF"        # Deep Purple / Blueish
    DARK_HIGHLIGHT = "#9E79FF"
    DARK_PRESSED = "#651FFF"
    
    LIGHT_ACCENT = "#2962FF"       # Bright Blue
    LIGHT_HIGHLIGHT = "#448AFF"
    LIGHT_PRESSED = "#0039CB"

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ThemeManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        super().__init__()
        self._initialized = True
        self.current_theme = "dark" # Default fallback
        
    def _get_base_font(self):
        sys_name = platform.system()
        if sys_name == 'Darwin':
            return "SF Pro Text, Helvetica Neue, Helvetica, Arial, sans-serif"
        elif sys_name == 'Windows':
            return "Segoe UI, Microsoft YaHei, sans-serif"
        else:
            return "Roboto, Noto Sans, Arial, sans-serif"

    def detect_system_theme(self) -> str:
        """
        Detects whether the system is in Dark Mode or Light Mode.
        Returns 'dark' or 'light'.
        """
        try:
            # macOS specific check
            if sys.platform == "darwin":
                import subprocess
                cmd = 'defaults read -g AppleInterfaceStyle'
                try:
                    result = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL)
                    if b"Dark" in result:
                        return "dark"
                except subprocess.CalledProcessError:
                    return "light" # Returns error if key doesn't exist (Light mode)
                    
            # Windows/Linux fallback: Check QPalette if app is initialized
            app = QApplication.instance()
            if app:
                palette = app.palette()
                bg_color = palette.color(QPalette.Window)
                # If background is dark, assume dark mode
                if bg_color.lightness() < 128:
                    return "dark"
                    
        except Exception as e:
            logger.warning(f"Failed to detect system theme: {e}")
        
        return "light" # Default strict fallback

    def load_stylesheet(self, theme_name: str) -> str:
        """Loads and processes the QSS file."""
        try:
            current_dir = Path(__file__).parent
            qss_path = current_dir / "qt_styles" / f"{theme_name}.qss"
            
            if not qss_path.exists():
                logger.error(f"Stylesheet not found: {qss_path}")
                return ""
                
            with open(qss_path, 'r', encoding='utf-8') as f:
                qss = f.read()
                
            # Perform substitutions
            font = self._get_base_font()
            
            if theme_name == "dark":
                accent = self.DARK_ACCENT
                highlight = self.DARK_HIGHLIGHT
                pressed = self.DARK_PRESSED
            else:
                accent = self.LIGHT_ACCENT
                highlight = self.LIGHT_HIGHLIGHT
                pressed = self.LIGHT_PRESSED
                
            qss = qss.replace("{{font_family}}", font)
            qss = qss.replace("{{accent_color}}", accent)
            qss = qss.replace("{{accent_hightlight}}", highlight)
            qss = qss.replace("{{accent_pressed}}", pressed)
            
            return qss
        except Exception as e:
            logger.error(f"Error loading stylesheet: {e}")
            return ""

    def apply_theme(self, app: QApplication = None):
        """Detects system theme and applies the corresponding stylesheet."""
        if not app:
            app = QApplication.instance()
            
        theme = self.detect_system_theme()
        self.current_theme = theme
        logger.info(f"Applying theme: {theme}")
        
        qss = self.load_stylesheet(theme)
        if qss and app:
            app.setStyleSheet(qss)


# Backward compatibility wrapper
def apply_common_style(widget, font_size: int = 14):
    """
    Deprecated: The ThemeManager now handles global styling on the QApplication.
    This function is kept to avoid breaking imports, but it delegates to ThemeManager
    if the app stylesheet isn't set, or does nothing if it is.
    """
    # Simply ensure the global theme is applied
    pass
