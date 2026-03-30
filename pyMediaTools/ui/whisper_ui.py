"""
whisper_ui.py
~~~~~~~~~~~~~
Groq Whisper 语音识别 UI 模块

类似 ElevenLabs 界面风格：
  - 左侧：文件拖拽区 + 配置面板（API Key、语言、模型、文案输入）
  - 右侧：识别进度日志 + 可编辑结果预览 + 一键导出
"""

import os
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QComboBox, QGroupBox, QProgressBar,
    QFileDialog, QMessageBox, QCheckBox, QFrame, QScrollArea,
    QSizePolicy, QSpacerItem, QSplitter, QSpinBox, QTabWidget,
    QGridLayout, QStackedWidget,
)
from PySide6.QtCore import Qt, QThread, QSettings, QMimeData, QUrl, QSize
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent, QColor, QPalette

from ..core.whisper_transcription import (
    LANGUAGE_OPTIONS,
    TRANSLATE_TARGET_LANGUAGES,
    SUPPORTED_WHISPER_MODELS,
    DEFAULT_WORDS_PER_SEGMENT,
    WhisperWorker,
    export_srt,
    export_vtt,
    export_ass,
    export_fcpxml,
    segments_to_srt_text,
)
from .styles import apply_common_style
from ..logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 支持的媒体格式
# ---------------------------------------------------------------------------
SUPPORTED_MEDIA_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v",
    ".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac", ".wma",
}


# ---------------------------------------------------------------------------
# 拖拽放置区控件
# ---------------------------------------------------------------------------

class DropZoneWidget(QFrame):
    """大型文件拖拽区域，支持视频/音频文件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("DropZone")
        self.file_path = ""
        self._setup_ui()
        self._apply_style(hovering=False)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        self.icon_label = QLabel("🎬")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 42px; background: transparent;")

        self.title_label = QLabel("拖拽视频或音频文件至此")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; background: transparent;")

        self.sub_label = QLabel("支持: .mp4 .mov .mkv .mp3 .m4a .wav .flac 等")
        self.sub_label.setAlignment(Qt.AlignCenter)
        self.sub_label.setStyleSheet("font-size: 11px; color: #888; background: transparent;")

        self.file_label = QLabel("")
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("font-size: 11px; color: #4CAF50; font-weight: bold; background: transparent;")

        self.btn_browse = QPushButton("📂 浏览文件")
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.setFixedWidth(120)
        self.btn_browse.clicked.connect(self._browse_file)

        layout.addStretch()
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.sub_label)
        layout.addWidget(self.file_label)
        layout.addWidget(self.btn_browse, alignment=Qt.AlignCenter)
        layout.addStretch()

        self.setMinimumHeight(160)
        self.setMaximumHeight(220)

    def _apply_style(self, hovering: bool):
        border_color = "#4CAF50" if self.file_path else ("#6DD3C3" if hovering else "#555")
        bg = "rgba(109, 211, 195, 0.08)" if hovering else "transparent"
        self.setStyleSheet(f"""
            QFrame#DropZone {{
                border: 2px dashed {border_color};
                border-radius: 12px;
                background-color: {bg};
            }}
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and Path(urls[0].toLocalFile()).suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS:
                event.acceptProposedAction()
                self._apply_style(hovering=True)
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._apply_style(hovering=False)

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._set_file(path)
        self._apply_style(hovering=False)

    def _browse_file(self):
        exts = "媒体文件 (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.mp3 *.m4a *.wav *.aac *.ogg *.flac *.wma);;所有文件 (*)"
        path, _ = QFileDialog.getOpenFileName(self, "选择媒体文件", "", exts)
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        if Path(path).suffix.lower() not in SUPPORTED_MEDIA_EXTENSIONS:
            QMessageBox.warning(self, "不支持的格式", f"不支持的文件格式: {Path(path).suffix}\n支持: {', '.join(SUPPORTED_MEDIA_EXTENSIONS)}")
            return
        self.file_path = path
        name = Path(path).name
        display = name if len(name) <= 45 else name[:42] + "..."
        self.file_label.setText(f"✅ {display}")
        self.icon_label.setText("🎞️")
        self._apply_style(hovering=False)


# ---------------------------------------------------------------------------
# 日志面板
# ---------------------------------------------------------------------------

class LogPanel(QTextEdit):
    """只读日志面板，自动滚动到底部。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setObjectName("LogPanel")
        self.setMaximumHeight(160)
        self.setFont(QFont("Courier New", 10))
        self.setPlaceholderText("识别进度日志将显示在此处...")
        self.setStyleSheet("""
            QTextEdit#LogPanel {
                background: rgba(0, 0, 0, 0.25);
                border-radius: 8px;
                border: 1px solid #444;
                color: #ccc;
                padding: 8px;
            }
        """)

    def append_log(self, message: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.append(f"[{ts}] {message}")
        # 自动滚动到底部
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


# ---------------------------------------------------------------------------
# 配置区卡片
# ---------------------------------------------------------------------------

class ConfigCard(QGroupBox):
    """样式统一的配置卡片。"""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setObjectName("ConfigCard")
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(8)
        self._layout.setContentsMargins(12, 14, 12, 12)
        self.setStyleSheet("""
            QGroupBox#ConfigCard {
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #444;
                border-radius: 10px;
                margin-top: 8px;
                padding-top: 6px;
            }
            QGroupBox#ConfigCard::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
        """)

    def inner_layout(self):
        return self._layout


# ---------------------------------------------------------------------------
# 主 Widget
# ---------------------------------------------------------------------------

class WhisperWidget(QWidget):
    """
    Groq Whisper 语音识别主界面。

    布局：
      左侧 (340px) — 配置面板
      右侧 (弹性) — 进度 + 结果
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WhisperWidget")

        self._worker: WhisperWorker | None = None
        self._worker_thread: QThread | None = None
        self._current_segments = []

        # 复用 Groq QSettings（与其他模块共享 API Key）
        self._groq_settings = QSettings("pyMediaTools", "Groq")

        self._setup_ui()
        self._load_settings()
        apply_common_style(self)

    # -----------------------------------------------------------------------
    # UI 构建
    # -----------------------------------------------------------------------

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------- 左侧配置面板 ----------
        left_panel = self._build_left_panel()

        # ---------- 右侧结果面板 ----------
        right_panel = self._build_right_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 700])
        splitter.setHandleWidth(1)

        root.addWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("LeftPanel")
        panel.setFixedWidth(360)
        panel.setStyleSheet("""
            QWidget#LeftPanel {
                border-right: 1px solid #333;
            }
        """)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # ------- 标题 -------
        title = QLabel("🎤  语音识别")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #6DD3C3;")
        subtitle = QLabel("Groq Whisper 词级精度识别 · 文案对齐 · 字幕导出")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # ------- 文件区 -------
        self.drop_zone = DropZoneWidget()
        layout.addWidget(self.drop_zone)

        # ------- API Key -------
        api_card = ConfigCard("🔑 Groq API 配置")
        api_layout = api_card.inner_layout()

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("gsk_...")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setMinimumHeight(36)

        show_btn = QPushButton("👁")
        show_btn.setFixedSize(36, 36)
        show_btn.setCheckable(True)
        show_btn.setCursor(Qt.PointingHandCursor)
        show_btn.toggled.connect(
            lambda checked: self.api_key_edit.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        show_btn.setToolTip("显示/隐藏 API Key")

        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        key_row.addWidget(self.api_key_edit)
        key_row.addWidget(show_btn)
        api_layout.addLayout(key_row)

        hint = QLabel(
            '没有 Key? 前往 <a href="https://console.groq.com/keys" style="color:#6DD3C3;">console.groq.com</a> 免费获取'
        )
        hint.setOpenExternalLinks(True)
        hint.setStyleSheet("font-size: 10px; color: #888;")
        api_layout.addWidget(hint)

        # 模型选择
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("模型:"))
        self.model_combo = QComboBox()
        for m in SUPPORTED_WHISPER_MODELS:
            self.model_combo.addItem(m, m)
        self.model_combo.setToolTip("whisper-large-v3-turbo: 速度快\nwhisper-large-v3: 精度高\ndistil-whisper: 仅英文")
        model_row.addWidget(self.model_combo)
        api_layout.addLayout(model_row)

        layout.addWidget(api_card)

        # ------- 识别语言 -------
        lang_card = ConfigCard("🌐 识别语言")
        lang_layout = lang_card.inner_layout()

        self.language_combo = QComboBox()
        for code, name in LANGUAGE_OPTIONS.items():
            self.language_combo.addItem(name, code)
        self.language_combo.setCurrentIndex(0)  # "自动检测"
        lang_layout.addWidget(self.language_combo)

        layout.addWidget(lang_card)

        # ------- 参考文案 -------
        script_card = ConfigCard("📝 参考文案（可选）")
        script_layout = script_card.inner_layout()

        script_hint = QLabel(
            "输入参考文案可大幅提升识别准确率，并纠正漏词/错词。\n"
            "留空则直接使用 Whisper 原始识别结果。"
        )
        script_hint.setWordWrap(True)
        script_hint.setStyleSheet("font-size: 10px; color: #888;")
        script_layout.addWidget(script_hint)

        self.script_edit = QTextEdit()
        self.script_edit.setPlaceholderText("在此粘贴参考文案或台词脚本...")
        self.script_edit.setMinimumHeight(110)
        self.script_edit.setMaximumHeight(180)
        script_layout.addWidget(self.script_edit)

        # 每段词数
        wps_row = QHBoxLayout()
        wps_row.addWidget(QLabel("每段最多词数:"))
        self.words_per_seg_spin = QSpinBox()
        self.words_per_seg_spin.setRange(3, 50)
        self.words_per_seg_spin.setValue(DEFAULT_WORDS_PER_SEGMENT)
        self.words_per_seg_spin.setToolTip("字幕分段时每条最多包含的词数（遇到句子标点会提前切断）")
        wps_row.addWidget(self.words_per_seg_spin)
        wps_row.addStretch()
        script_layout.addLayout(wps_row)

        layout.addWidget(script_card)

        # ------- 自动翻译 -------
        trans_card = ConfigCard("🌍 自动翻译")
        trans_layout = trans_card.inner_layout()

        self.chk_translate = QCheckBox("识别后自动翻译")
        self.chk_translate.setToolTip("使用 Groq LLM 翻译字幕（需同一 API Key）")
        self.chk_translate.toggled.connect(self._on_translate_toggled)
        trans_layout.addWidget(self.chk_translate)

        self.trans_target_row = QHBoxLayout()
        self.trans_target_row.addWidget(QLabel("目标语言:"))
        self.trans_lang_combo = QComboBox()
        for code, name in TRANSLATE_TARGET_LANGUAGES.items():
            self.trans_lang_combo.addItem(name, code)
        self.trans_lang_combo.setEnabled(False)
        self.trans_target_row.addWidget(self.trans_lang_combo)
        self.trans_target_row.addStretch()
        trans_layout.addLayout(self.trans_target_row)

        layout.addWidget(trans_card)

        # ------- 导出格式 -------
        export_card = ConfigCard("📤 导出格式")
        export_layout = export_card.inner_layout()

        fmt_grid = QGridLayout()
        fmt_grid.setSpacing(6)
        self.chk_srt = QCheckBox("SRT")
        self.chk_vtt = QCheckBox("VTT")
        self.chk_ass = QCheckBox("ASS")
        self.chk_fcpxml = QCheckBox("FCPXML")
        self.chk_srt.setChecked(True)
        fmt_grid.addWidget(self.chk_srt, 0, 0)
        fmt_grid.addWidget(self.chk_vtt, 0, 1)
        fmt_grid.addWidget(self.chk_ass, 1, 0)
        fmt_grid.addWidget(self.chk_fcpxml, 1, 1)
        export_layout.addLayout(fmt_grid)

        layout.addWidget(export_card)

        layout.addStretch()

        # ------- 开始按钮 -------
        self.run_btn = QPushButton("▶  开始识别")
        self.run_btn.setObjectName("RunButton")
        self.run_btn.setMinimumHeight(48)
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.run_btn.clicked.connect(self._toggle_run)
        self.run_btn.setStyleSheet("""
            QPushButton#RunButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #2196F3);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
            }
            QPushButton#RunButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #56c75a, stop:1 #42a5f5);
            }
            QPushButton#RunButton:disabled {
                background: #555;
                color: #888;
            }
            QPushButton#RunButton[running="true"] {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e53e3e, stop:1 #c62828);
            }
        """)
        layout.addWidget(self.run_btn)

        scroll.setWidget(content)

        wrapper = QVBoxLayout(panel)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(scroll)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # ------- 标题行 -------
        header_row = QHBoxLayout()
        result_title = QLabel("识别结果")
        result_title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        header_row.addWidget(result_title)
        header_row.addStretch()

        self.copy_btn = QPushButton("📋 复制")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setFixedHeight(32)
        self.copy_btn.clicked.connect(self._copy_result)
        self.copy_btn.setEnabled(False)

        self.save_btn = QPushButton("💾 导出文件")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setFixedHeight(32)
        self.save_btn.clicked.connect(self._export_all)
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: rgba(109, 211, 195, 0.15);
                border: 1px solid #6DD3C3;
                border-radius: 6px;
                color: #6DD3C3;
                padding: 0 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(109, 211, 195, 0.25); }
            QPushButton:disabled { opacity: 0.3; border-color: #555; color: #555; }
        """)

        header_row.addWidget(self.copy_btn)
        header_row.addWidget(self.save_btn)
        layout.addLayout(header_row)

        # ------- 进度区 -------
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 3px;
                background: #333;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #2196F3);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # ------- 日志 -------
        self.log_panel = LogPanel()
        layout.addWidget(self.log_panel)

        # ------- 结果 Tab -------
        self.result_tabs = QTabWidget()
        self.result_tabs.setObjectName("ResultTabs")

        # Tab 1: SRT 预览
        self.srt_preview = QTextEdit()
        self.srt_preview.setObjectName("SrtPreview")
        self.srt_preview.setPlaceholderText(
            "识别完成后，SRT 格式预览将显示在此处。\n"
            "您可以直接在此编辑字幕内容。"
        )
        self.srt_preview.setFont(QFont("Courier New", 11))
        self.srt_preview.setStyleSheet("""
            QTextEdit#SrtPreview {
                background: rgba(0,0,0,0.15);
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px;
                color: #eee;
            }
        """)
        self.result_tabs.addTab(self.srt_preview, "SRT 预览")

        # Tab 2: JSON 词级数据
        self.json_preview = QTextEdit()
        self.json_preview.setReadOnly(True)
        self.json_preview.setFont(QFont("Courier New", 10))
        self.json_preview.setPlaceholderText("识别完成后，词级 JSON 数据将显示在此处...")
        self.json_preview.setStyleSheet("""
            QTextEdit {
                background: rgba(0,0,0,0.2);
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px;
                color: #aaa;
            }
        """)
        self.result_tabs.addTab(self.json_preview, "词级数据 (JSON)")

        layout.addWidget(self.result_tabs, 1)

        # ------- 统计信息 -------
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.stats_label)

        return panel

    # -----------------------------------------------------------------------
    # 事件处理
    # -----------------------------------------------------------------------

    def _on_translate_toggled(self, checked: bool):
        self.trans_lang_combo.setEnabled(checked)

    def _toggle_run(self):
        if self._worker_thread and self._worker_thread.isRunning():
            self._stop_worker()
        else:
            self._start_worker()

    def _start_worker(self):
        # 验证输入
        media_path = self.drop_zone.file_path
        if not media_path:
            QMessageBox.warning(self, "请选择文件", "请先拖拽或浏览选择一个媒体文件。")
            return

        api_key = self.api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "缺少 API Key", "请输入 Groq API Key。\n可前往 https://console.groq.com/keys 免费获取。")
            return

        language = self.language_combo.currentData()
        model = self.model_combo.currentData()
        user_script = self.script_edit.toPlainText().strip()
        words_per_seg = self.words_per_seg_spin.value()

        # 保存设置
        self._save_settings()

        # UI 状态切换
        self.run_btn.setText("⏹  停止")
        self.run_btn.setProperty("running", "true")
        self.run_btn.style().unpolish(self.run_btn)
        self.run_btn.style().polish(self.run_btn)

        self.progress_bar.setVisible(True)
        self.copy_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.srt_preview.clear()
        self.json_preview.clear()
        self.log_panel.clear()
        self.stats_label.setText("")
        self._current_segments = []

        self.log_panel.append_log(f"文件: {os.path.basename(media_path)}")
        self.log_panel.append_log(f"模型: {model} | 语言: {language or '自动检测'}")
        if user_script:
            self.log_panel.append_log(f"参考文案: {len(user_script)} 字符")

        # 创建 Worker
        self._worker = WhisperWorker(
            media_path=media_path,
            api_key=api_key,
            language=language if language != "auto" else "",
            model=model,
            user_script=user_script,
            words_per_segment=words_per_seg,
        )

        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._reset_run_btn)
        self._worker_thread.start()

    def _stop_worker(self):
        if self._worker:
            self._worker.cancel()
        self.log_panel.append_log("⚠️ 正在停止...")
        self.run_btn.setEnabled(False)

    def _reset_run_btn(self):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶  开始识别")
        self.run_btn.setProperty("running", "false")
        self.run_btn.style().unpolish(self.run_btn)
        self.run_btn.style().polish(self.run_btn)
        self.progress_bar.setVisible(False)

    def _on_progress(self, message: str):
        self.log_panel.append_log(message)

    def _on_finished(self, segments: list):
        self._current_segments = segments

        # 可选翻译
        if self.chk_translate.isChecked() and segments:
            self._run_translation(segments)
        else:
            self._display_segments(segments)

    def _run_translation(self, segments: list):
        """调用 TranslationManager 翻译 segments。"""
        self.log_panel.append_log("🌍 正在调用翻译 API...")
        api_key = self.api_key_edit.text().strip()
        target_lang = self.trans_lang_combo.currentData()

        try:
            from ..core.translation_manager import TranslationManager
            tm = TranslationManager(api_key=api_key)

            # TranslationManager.translate_segments 只支持中文，对于其他语言使用自定义 prompt
            if target_lang == "zh":
                translated = tm.translate_segments(segments)
            else:
                # 对其他目标语言，修改 model 和 prompt
                lang_name = TRANSLATE_TARGET_LANGUAGES.get(target_lang, target_lang)
                translated = self._translate_to_other_language(segments, api_key, lang_name)

            self._current_segments = translated
            self.log_panel.append_log(f"✅ 翻译完成 → {TRANSLATE_TARGET_LANGUAGES.get(target_lang, target_lang)}")
            self._display_segments(translated)
        except Exception as e:
            self.log_panel.append_log(f"⚠️ 翻译失败: {e}，使用原始识别结果")
            self._display_segments(segments)

    def _translate_to_other_language(self, segments: list, api_key: str, lang_name: str) -> list:
        """翻译到非中文的目标语言。"""
        from ..core.translation_manager import TranslationManager
        import requests as req_module

        tm = TranslationManager(api_key=api_key)
        # 覆盖系统提示
        batch_size = 20
        translated_segs = []

        for i in range(0, len(segments), batch_size):
            batch = segments[i:i + batch_size]
            texts = [f"{idx+1}. {s.get('text','')}" for idx, s in enumerate(batch)]
            sep = "###SEG_SEP###"
            combined = f"\n{sep}\n".join(texts)

            system_prompt = (
                f"You are a professional subtitle translator. "
                f"Translate each numbered segment into {lang_name}, preserving the numeric prefix. "
                f"Segments are separated by '{sep}'. Output only the translated segments separated by '{sep}'."
            )

            try:
                result = tm._request_with_retry(system_prompt, combined)
                if result:
                    import re
                    parts = [p.strip() for p in result.split(sep)]
                    for j, (orig, trans) in enumerate(zip(batch, parts)):
                        m = re.match(r'\s*\d+[\.:]\s*(.*)', trans, re.S)
                        txt = m.group(1).strip() if m else trans.strip()
                        updated = orig.copy()
                        updated["text"] = txt
                        translated_segs.append(updated)
                else:
                    translated_segs.extend(batch)
            except Exception:
                translated_segs.extend(batch)

        return translated_segs

    def _display_segments(self, segments: list):
        """将 segments 显示到预览面板。"""
        self._current_segments = segments

        # SRT 预览
        srt_text = segments_to_srt_text(segments)
        self.srt_preview.setPlainText(srt_text)

        # JSON 预览
        try:
            json_text = json.dumps(segments, ensure_ascii=False, indent=2)
            self.json_preview.setPlainText(json_text)
        except Exception:
            pass

        # 统计
        total_dur = segments[-1]["end"] if segments else 0
        m, s = divmod(int(total_dur), 60)
        self.stats_label.setText(
            f"共 {len(segments)} 条字幕 · 总时长 {m:02d}:{s:02d} · "
            f"{sum(len(seg['text']) for seg in segments)} 字符"
        )

        self.copy_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

    def _on_error(self, message: str):
        self.log_panel.append_log(f"❌ 错误: {message}")
        QMessageBox.critical(self, "识别失败", f"识别过程中发生错误:\n\n{message}")

    # -----------------------------------------------------------------------
    # 导出功能
    # -----------------------------------------------------------------------

    def _copy_result(self):
        from PySide6.QtWidgets import QApplication
        text = self.srt_preview.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.copy_btn.setText("✅ 已复制")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self.copy_btn.setText("📋 复制"))

    def _export_all(self):
        if not self._current_segments:
            QMessageBox.warning(self, "无内容", "没有可导出的识别结果。")
            return

        # 应用预览中的手动编辑（从 SRT 文本重新解析 segments）
        edited_text = self.srt_preview.toPlainText()
        segments_to_export = self._parse_srt_text(edited_text) or self._current_segments

        # 确定哪些格式需要导出
        formats = []
        if self.chk_srt.isChecked():
            formats.append("srt")
        if self.chk_vtt.isChecked():
            formats.append("vtt")
        if self.chk_ass.isChecked():
            formats.append("ass")
        if self.chk_fcpxml.isChecked():
            formats.append("fcpxml")

        if not formats:
            QMessageBox.warning(self, "未选择格式", "请至少勾选一种导出格式。")
            return

        # 选择保存目录
        media_path = self.drop_zone.file_path
        default_dir = str(Path(media_path).parent) if media_path else ""
        default_name = Path(media_path).stem if media_path else "subtitle"

        save_dir = QFileDialog.getExistingDirectory(self, "选择保存目录", default_dir)
        if not save_dir:
            return

        exported = []
        errors = []

        for fmt in formats:
            out_path = os.path.join(save_dir, f"{default_name}.{fmt}")
            try:
                if fmt == "srt":
                    export_srt(segments_to_export, out_path)
                elif fmt == "vtt":
                    export_vtt(segments_to_export, out_path)
                elif fmt == "ass":
                    export_ass(segments_to_export, out_path)
                elif fmt == "fcpxml":
                    export_fcpxml(segments_to_export, out_path)
                exported.append(os.path.basename(out_path))
                self.log_panel.append_log(f"✅ 已导出: {os.path.basename(out_path)}")
            except Exception as e:
                errors.append(f"{fmt.upper()}: {e}")
                self.log_panel.append_log(f"❌ {fmt.upper()} 导出失败: {e}")

        if exported:
            msg = f"已成功导出 {len(exported)} 个文件:\n" + "\n".join(exported)
            if errors:
                msg += f"\n\n以下格式导出失败:\n" + "\n".join(errors)
            QMessageBox.information(self, "导出完成", msg)
        else:
            QMessageBox.critical(self, "导出失败", "所有格式导出均失败:\n" + "\n".join(errors))

    def _parse_srt_text(self, srt_text: str) -> list:
        """
        将 SRT 格式文本解析回 segments。
        用于用户手动编辑 SRT 预览后的导出。
        """
        import re
        segments = []
        blocks = re.split(r'\n\s*\n', srt_text.strip())

        for block in blocks:
            lines = block.strip().splitlines()
            if len(lines) < 2:
                continue

            # 找时间轴行
            time_line = None
            text_lines = []
            for i, line in enumerate(lines):
                if '-->' in line:
                    time_line = line
                    text_lines = lines[i+1:]
                    break

            if not time_line:
                continue

            # 解析时间
            def srt_time_to_sec(s: str) -> float:
                s = s.strip().replace(',', '.')
                parts = s.split(':')
                try:
                    h, m, rest = parts
                    return int(h) * 3600 + int(m) * 60 + float(rest)
                except Exception:
                    return 0.0

            times = time_line.split('-->')
            if len(times) == 2:
                start = srt_time_to_sec(times[0])
                end = srt_time_to_sec(times[1])
                text = "\n".join(text_lines).strip()
                if text:
                    segments.append({"text": text, "start": start, "end": end})

        return segments if segments else None

    # -----------------------------------------------------------------------
    # 设置持久化
    # -----------------------------------------------------------------------

    def _save_settings(self):
        api_key = self.api_key_edit.text().strip()
        if api_key:
            self._groq_settings.setValue("api_key", api_key)
        self._groq_settings.setValue("whisper_model", self.model_combo.currentData())
        self._groq_settings.setValue("whisper_language", self.language_combo.currentData())
        self._groq_settings.setValue("whisper_words_per_seg", self.words_per_seg_spin.value())
        self._groq_settings.setValue("whisper_translate", self.chk_translate.isChecked())
        self._groq_settings.setValue("whisper_trans_lang", self.trans_lang_combo.currentData())

    def _load_settings(self):
        api_key = self._groq_settings.value("api_key", "")
        if api_key:
            self.api_key_edit.setText(api_key)

        model = self._groq_settings.value("whisper_model", SUPPORTED_WHISPER_MODELS[0])
        idx = self.model_combo.findData(model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

        language = self._groq_settings.value("whisper_language", "auto")
        idx = self.language_combo.findData(language)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)

        wps = self._groq_settings.value("whisper_words_per_seg", DEFAULT_WORDS_PER_SEGMENT)
        try:
            self.words_per_seg_spin.setValue(int(wps))
        except Exception:
            pass

        do_translate = self._groq_settings.value("whisper_translate", False)
        if isinstance(do_translate, str):
            do_translate = do_translate.lower() == "true"
        self.chk_translate.setChecked(bool(do_translate))

        trans_lang = self._groq_settings.value("whisper_trans_lang", "zh")
        idx = self.trans_lang_combo.findData(trans_lang)
        if idx >= 0:
            self.trans_lang_combo.setCurrentIndex(idx)
