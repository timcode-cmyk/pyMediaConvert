import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QLineEdit, QFormLayout, QGroupBox, QSpinBox, 
                               QDoubleSpinBox, QMessageBox, QTabWidget, QWidget)
from PySide6.QtCore import Qt, QSettings, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from .styles import apply_common_style
from ..utils import get_user_config_path, get_user_config_dir, get_env_override, reset_user_config


class GlobalSettingsDialog(QDialog):
    settings_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("全局设置 / Global Settings")
        self.resize(520, 480)
        
        self.settings_el = QSettings("pyMediaTools", "ElevenLabs")
        self.settings_groq = QSettings("pyMediaTools", "Groq")
        self.settings_gladia = QSettings("pyMediaTools", "Gladia")
        self.settings_global = QSettings("pyMediaTools", "GlobalSettings")
        
        self.init_ui()
        apply_common_style(self)

    def _configure_api_input(self, line_edit: QLineEdit, saved_val: str, env_names: tuple[str, ...], default_placeholder: str):
        line_edit.setEchoMode(QLineEdit.Password)
        line_edit.setText(saved_val)
        env_val = get_env_override(env_names)
        if env_val:
            line_edit.setPlaceholderText(f"已检测到环境变量 ({env_names[0]})，优先级高于本地配置")
        else:
            line_edit.setPlaceholderText(default_placeholder)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        self.tabs = QTabWidget()
        
        # --- Tab: API Keys ---
        api_tab = QWidget()
        api_layout = QVBoxLayout(api_tab)
        
        # ElevenLabs Settings
        el_group = QGroupBox("ElevenLabs 语音合成")
        el_layout = QFormLayout(el_group)
        self.eleven_api_edit = QLineEdit()
        self._configure_api_input(
            self.eleven_api_edit,
            self.settings_el.value("api_key", ""),
            ("PYMEDIA_ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY"),
            "sk_...（本地未设置时可使用环境变量）",
        )
        el_layout.addRow("API Key:", self.eleven_api_edit)
        api_layout.addWidget(el_group)

        # Gladia Settings（语音识别）
        gladia_group = QGroupBox("Gladia 语音识别")
        gladia_layout = QFormLayout(gladia_group)
        self.gladia_api_edit = QLineEdit()
        self._configure_api_input(
            self.gladia_api_edit,
            self.settings_gladia.value("api_key", ""),
            ("PYMEDIA_GLADIA_API_KEY", "GLADIA_API_KEY"),
            "在 app.gladia.io 申请",
        )
        gladia_layout.addRow("API Key:", self.gladia_api_edit)
        api_layout.addWidget(gladia_group)

        # Groq Settings（LLM 翻译 / Groq 相关）
        groq_group = QGroupBox("Groq LLM (翻译功能)")
        groq_layout = QFormLayout(groq_group)
        self.groq_api_edit = QLineEdit()
        self._configure_api_input(
            self.groq_api_edit,
            self.settings_groq.value("api_key", ""),
            ("PYMEDIA_GROQ_API_KEY", "GROQ_API_KEY"),
            "在 console.groq.com 申请",
        )
        groq_layout.addRow("API Key:", self.groq_api_edit)
        api_layout.addWidget(groq_group)
        
        api_layout.addStretch()
        self.tabs.addTab(api_tab, "🔑 API Keys")

        # --- Tab: 用户参数 ---
        user_tab = QWidget()
        user_layout = QVBoxLayout(user_tab)
        
        auth_group = QGroupBox("创作者信息")
        auth_layout = QFormLayout(auth_group)
        self.username_edit = QLineEdit()
        self.username_edit.setText(self.settings_global.value("username", ""))
        self.username_edit.setPlaceholderText("例如: @张三")
        auth_layout.addRow("用户名 (水印):", self.username_edit)
        user_layout.addWidget(auth_group)

        # 视频转录参数
        trans_group = QGroupBox("视频转录/字幕设置")
        trans_layout = QFormLayout(trans_group)
        self.max_chars_spin = QSpinBox()
        self.max_chars_spin.setRange(10, 100)
        self.max_chars_spin.setValue(int(self.settings_global.value("srt_max_chars", 35)))
        trans_layout.addRow("字幕单行最多字符数:", self.max_chars_spin)

        self.pause_spin = QDoubleSpinBox()
        self.pause_spin.setRange(0.05, 2.0)
        self.pause_spin.setSingleStep(0.1)
        self.pause_spin.setValue(float(self.settings_global.value("srt_pause_threshold", 0.3)))
        trans_layout.addRow("分句断行气口 (秒):", self.pause_spin)
        user_layout.addWidget(trans_group)

        # 配置文件存储与优先级说明
        cfg_group = QGroupBox("配置存储 (config.toml 为只读出厂默认)")
        cfg_layout = QVBoxLayout(cfg_group)
        cfg_path_label = QLabel(f"个性化配置路径: {get_user_config_path()}")
        cfg_path_label.setWordWrap(True)
        cfg_path_label.setStyleSheet("color: palette(mid); font-size: 12px;")
        cfg_layout.addWidget(cfg_path_label)

        cfg_btn_layout = QHBoxLayout()
        open_dir_btn = QPushButton("📂 打开配置目录")
        open_dir_btn.setCursor(Qt.PointingHandCursor)
        open_dir_btn.clicked.connect(self.open_config_dir)
        reset_btn = QPushButton("↺ 恢复默认配置")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self.handle_reset_config)
        cfg_btn_layout.addWidget(open_dir_btn)
        cfg_btn_layout.addWidget(reset_btn)
        cfg_btn_layout.addStretch()
        cfg_layout.addLayout(cfg_btn_layout)
        user_layout.addWidget(cfg_group)

        user_layout.addStretch()
        self.tabs.addTab(user_tab, "⚙️ 偏好设置")

        main_layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("💾 保存并应用")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.save_settings)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        main_layout.addLayout(btn_layout)

    def open_config_dir(self):
        cfg_dir = get_user_config_dir()
        cfg_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(cfg_dir)))

    def handle_reset_config(self):
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要清空用户的个性化覆盖配置并恢复为默认设置吗？\n(不会影响环境变量配置)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            reset_user_config()
            self.settings_global.remove("srt_max_chars")
            self.settings_global.remove("srt_pause_threshold")
            self.max_chars_spin.setValue(35)
            self.pause_spin.setValue(0.3)
            self.settings_saved.emit()
            QMessageBox.information(self, "已恢复", "已清除自定义配置并恢复出厂默认值。")

    def save_settings(self):
        # API Keys
        self.settings_el.setValue("api_key", self.eleven_api_edit.text().strip())
        self.settings_gladia.setValue("api_key", self.gladia_api_edit.text().strip())
        self.settings_groq.setValue("api_key", self.groq_api_edit.text().strip())

        # 字幕分段参数存入 GlobalSettings（供 whisper_ui 读取）
        self.settings_global.setValue("srt_max_chars", self.max_chars_spin.value())
        self.settings_global.setValue("srt_pause_threshold", self.pause_spin.value())

        # User Info
        self.settings_global.setValue("username", self.username_edit.text().strip())

        self.settings_saved.emit()
        QMessageBox.information(self, "成功", "全局设置已保存并应用！")
        self.accept()
