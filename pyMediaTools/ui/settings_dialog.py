import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QLineEdit, QFormLayout, QGroupBox, QSpinBox, 
                               QDoubleSpinBox, QMessageBox, QTabWidget, QWidget)
from PySide6.QtCore import Qt, QSettings
from .styles import apply_common_style

class GlobalSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("全局设置 / Global Settings")
        self.resize(500, 450)
        
        self.settings_el = QSettings("pyMediaTools", "ElevenLabs")
        self.settings_groq = QSettings("pyMediaTools", "Groq")
        self.settings_gladia = QSettings("pyMediaTools", "Gladia")
        self.settings_global = QSettings("pyMediaTools", "GlobalSettings")
        
        self.init_ui()
        apply_common_style(self)

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
        self.eleven_api_edit.setEchoMode(QLineEdit.Password)
        self.eleven_api_edit.setText(self.settings_el.value("api_key", ""))
        el_layout.addRow("API Key:", self.eleven_api_edit)
        api_layout.addWidget(el_group)

        # Gladia Settings（语音识别）
        gladia_group = QGroupBox("Gladia 语音识别")
        gladia_layout = QFormLayout(gladia_group)
        self.gladia_api_edit = QLineEdit()
        self.gladia_api_edit.setEchoMode(QLineEdit.Password)
        self.gladia_api_edit.setPlaceholderText("在 app.gladia.io 申请")
        self.gladia_api_edit.setText(self.settings_gladia.value("api_key", ""))
        gladia_layout.addRow("API Key:", self.gladia_api_edit)
        api_layout.addWidget(gladia_group)

        # Groq Settings（LLM 翻译 / Groq 相关）
        groq_group = QGroupBox("Groq LLM (翻译功能)")
        groq_layout = QFormLayout(groq_group)
        self.groq_api_edit = QLineEdit()
        self.groq_api_edit.setEchoMode(QLineEdit.Password)
        self.groq_api_edit.setPlaceholderText("在 console.groq.com 申请")
        self.groq_api_edit.setText(self.settings_groq.value("api_key", ""))
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
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setProperty("primary", "true")
        save_btn.clicked.connect(self.save_settings)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        main_layout.addLayout(btn_layout)

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

        QMessageBox.information(self, "成功", "全局设置已生效！\n(部分需重新打开对应模块或重启生效)")
        self.accept()
