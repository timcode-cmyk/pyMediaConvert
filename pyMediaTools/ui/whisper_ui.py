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
from PySide6.QtCore import Qt, QThread, QSettings, QMimeData, QUrl, QSize, QObject, Signal
from PySide6.QtGui import QFont, QFontDatabase, QDragEnterEvent, QDropEvent, QColor, QPalette

from ..core.gladia_transcription import (
    LANGUAGE_OPTIONS,
    TRANSLATE_TARGET_LANGUAGES,
)
from ..core.subtitle_writer import (
    export_srt,
    export_vtt,
    export_ass,
    export_fcpxml,
    segments_to_srt_text,
)
from ..core.whisper_worker import WhisperWorker
from ..core.translation_worker import TranslationWorker
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
        self._hovering = False
        self._setup_ui()
        self._apply_style(hovering=False)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 10, 15, 15)

        self.icon_label = QLabel("🎬")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 42px; background: transparent;")

        self.title_label = QLabel("拖拽视频或音频文件至此")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; background: transparent;")

        self.sub_label = QLabel("支持: .mp4 .mov .mkv .mp3 .m4a .wav .flac 等")
        self.sub_label.setAlignment(Qt.AlignCenter)
        self.sub_label.setStyleSheet("font-size: 11px; color: palette(mid); background: transparent;")

        self.file_label = QLabel("")
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("font-size: 11px; color: palette(highlight); font-weight: bold; background: transparent;")

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
        self._hovering = hovering
        palette = self.palette()
        is_dark = palette.color(QPalette.Window).lightness() < 128
        accent = palette.color(QPalette.Highlight)
        default_border = "rgba(255, 255, 255, 0.22)" if is_dark else "rgba(0, 0, 0, 0.22)"

        if self.file_path:
            border_color = "#22c55e"
            bg = "rgba(34, 197, 94, 0.08)"
        elif hovering:
            border_color = accent.name()
            bg = f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.10)"
        else:
            border_color = default_border
            bg = "rgba(255, 255, 255, 0.02)" if is_dark else "rgba(0, 0, 0, 0.02)"

        self.setStyleSheet(f"""
            QFrame#DropZone {{
                border: 2px dashed {border_color};
                border-radius: 10px;
                background-color: {bg};
            }}
        """)

    def apply_theme(self):
        self._apply_style(hovering=self._hovering)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and Path(urls[0].toLocalFile()).suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS:
                event.acceptProposedAction()
                self._apply_style(hovering=True)
                return
        event.ignore()

    def dragMoveEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and Path(urls[0].toLocalFile()).suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS:
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._apply_style(hovering=False)

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._set_file(path)
            event.acceptProposedAction()
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
        fixed_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        fixed_font.setPointSize(11)
        self.setFont(fixed_font)
        self.setPlaceholderText("识别进度日志将显示在此处...")

    def append_log(self, message: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.append(f"[{ts}] {message}")
        # 自动滚动到底部
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


# ---------------------------------------------------------------------------

class ConfigCard(QGroupBox):
    """样式统一的配置卡片。"""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setObjectName("ConfigCard")
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(8)
        self._layout.setContentsMargins(12, 14, 12, 12)

    def inner_layout(self):
        return self._layout


# ---------------------------------------------------------------------------
# 主 Widget
# ---------------------------------------------------------------------------

class WhisperWidget(QWidget):
    """
    Gladia Whisper 语音识别主界面。

    布局：
      左侧 (310px) — 配置面板
      右侧 (弹性) — 进度 + 结果
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WhisperWidget")

        self._worker: WhisperWorker | None = None
        self._worker_thread: QThread | None = None
        self._translate_worker = None
        self._translate_thread: QThread | None = None
        self._current_segments = []
        self._translated_segments = []

        # Gladia + Groq API Keys 从全局 QSettings 读取
        self._gladia_settings = QSettings("pyMediaTools", "Gladia")
        self._groq_settings = QSettings("pyMediaTools", "Groq")
        # 字幕分段参数
        self._global_settings = QSettings("pyMediaTools", "GlobalSettings")

        self._setup_ui()
        self._load_settings()
        self.apply_styles()

    def apply_styles(self):
        """基于当前 QPalette 动态应用并刷新深/浅色主题样式。"""
        apply_common_style(self)

        palette = self.palette()
        is_dark = palette.color(QPalette.Window).lightness() < 128
        accent = palette.color(QPalette.Highlight).name()
        border = "rgba(255, 255, 255, 0.14)" if is_dark else "rgba(0, 0, 0, 0.12)"
        panel_bg = "rgba(255, 255, 255, 0.03)" if is_dark else "rgba(0, 0, 0, 0.02)"

        if hasattr(self, "left_panel"):
            self.left_panel.setStyleSheet(f"QWidget#LeftPanel {{ border-right: 1px solid {border}; }}")
        if hasattr(self, "title_label_main"):
            self.title_label_main.setStyleSheet(f"color: {accent};")
        if hasattr(self, "api_notice"):
            self.api_notice.setText(
                f'🔑 Gladia API Key 请在 <a href="settings" style="color:{accent}; text-decoration:none;">⚙️ 全局设置</a> 中配置'
            )
        if hasattr(self, "drop_zone"):
            self.drop_zone.apply_theme()

        for editor in (
            getattr(self, "log_panel", None),
            getattr(self, "srt_preview", None),
            getattr(self, "json_preview", None),
            getattr(self, "trans_preview", None),
        ):
            if editor is not None:
                editor.setStyleSheet(
                    f"background-color: {panel_bg}; border: 1px solid {border}; border-radius: 8px; padding: 8px;"
                )

        if hasattr(self, "run_btn"):
            self.run_btn.setStyleSheet(f"""
                QPushButton#RunButton {{
                    background-color: {accent};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton#RunButton:hover {{
                    background-color: palette(link-visited);
                }}
                QPushButton#RunButton:disabled {{
                    background-color: {border};
                    color: palette(mid);
                }}
                QPushButton#RunButton[running="true"] {{
                    background-color: #ef4444;
                }}
                QPushButton#RunButton[running="true"]:hover {{
                    background-color: #dc2626;
                }}
            """)

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
        splitter.setSizes([310, 790])
        splitter.setHandleWidth(1)

        root.addWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("LeftPanel")
        panel.setFixedWidth(310)
        self.left_panel = panel

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ------- 标题 -------
        self.title_label_main = QLabel("🎤  语音识别")
        title_font = self.title_label_main.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_label_main.setFont(title_font)

        subtitle = QLabel("Gladia 词级精度识别 · 文案对齐纠错 · 字幕导出")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: palette(mid); font-size: 11px;")
        layout.addWidget(self.title_label_main)
        layout.addWidget(subtitle)

        # ------- 文件区 -------
        self.drop_zone = DropZoneWidget()
        layout.addWidget(self.drop_zone)

        # ------- API Key 提示（支持点击打开全局设置）-------
        self.api_notice = QLabel()
        self.api_notice.setStyleSheet("font-size: 11px; color: palette(mid); padding: 4px 0;")
        self.api_notice.linkActivated.connect(self._open_global_settings)
        layout.addWidget(self.api_notice)

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
            "留空则直接使用 Gladia 原始识别结果。"
        )
        script_hint.setWordWrap(True)
        script_hint.setStyleSheet("font-size: 11px; color: palette(mid);")
        script_layout.addWidget(script_hint)

        self.script_edit = QTextEdit()
        self.script_edit.setPlaceholderText("在此粘贴参考文案或台词脚本...\n该内容仅用于识别后对齐纠错，不作为 Whisper prompt 输入。")
        self.script_edit.setMinimumHeight(80)
        self.script_edit.setMaximumHeight(180)
        script_layout.addWidget(self.script_edit)

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
        self.run_btn.setMinimumHeight(46)
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self._toggle_run)
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
        result_font = result_title.font()
        result_font.setPointSize(15)
        result_font.setBold(True)
        result_title.setFont(result_font)
        header_row.addWidget(result_title)
        header_row.addStretch()

        self.copy_btn = QPushButton("📋 复制")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setFixedHeight(32)
        self.copy_btn.clicked.connect(self._copy_result)
        self.copy_btn.setEnabled(False)

        self.save_btn = QPushButton("💾 导出文件")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setFixedHeight(32)
        self.save_btn.clicked.connect(self._export_all)
        self.save_btn.setEnabled(False)

        header_row.addWidget(self.copy_btn)
        header_row.addWidget(self.save_btn)
        layout.addLayout(header_row)

        # ------- 进度区 -------
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)

        # ------- 日志 -------
        self.log_panel = LogPanel()
        layout.addWidget(self.log_panel)

        # ------- 结果 Tab -------
        self.result_tabs = QTabWidget()
        self.result_tabs.setObjectName("ResultTabs")

        fixed_font_11 = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        fixed_font_11.setPointSize(11)
        fixed_font_10 = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        fixed_font_10.setPointSize(10)

        # Tab 1: SRT 预览
        self.srt_preview = QTextEdit()
        self.srt_preview.setObjectName("SrtPreview")
        self.srt_preview.setPlaceholderText(
            "识别完成后，SRT 格式预览将显示在此处。\n"
            "您可以直接在此编辑字幕内容。"
        )
        self.srt_preview.setFont(fixed_font_11)
        self.result_tabs.addTab(self.srt_preview, "SRT 预览")

        # Tab 2: JSON 词级数据
        self.json_preview = QTextEdit()
        self.json_preview.setReadOnly(True)
        self.json_preview.setFont(fixed_font_10)
        self.json_preview.setPlaceholderText("识别完成后，词级 JSON 数据将显示在此处...")
        self.result_tabs.addTab(self.json_preview, "词级数据 (JSON)")

        # Tab 3: 翻译预览
        self.trans_preview = QTextEdit()
        self.trans_preview.setReadOnly(True)
        self.trans_preview.setFont(fixed_font_11)
        self.trans_preview.setPlaceholderText("若启用自动翻译，翻译结果会显示在此处。")
        self.result_tabs.addTab(self.trans_preview, "翻译预览")

        layout.addWidget(self.result_tabs, 1)

        # ------- 统计信息 -------
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        layout.addWidget(self.stats_label)

        return panel

    def _open_global_settings(self):
        from .settings_dialog import GlobalSettingsDialog
        dialog = GlobalSettingsDialog(self)
        dialog.exec()

    def cleanup(self):
        """窗口关闭时安全中止正在运行的语音识别或翻译线程。"""
        if self._worker:
            self._worker.cancel()
        for t in (self._worker_thread, self._translate_thread):
            if t is not None and t.isRunning():
                t.quit()
                if not t.wait(500):
                    t.terminate()
                    t.wait(200)

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

        # 从环境变量或全局 QSettings 读取 API Key（环境变量优先级更高）
        from ..utils import get_env_override
        api_key = get_env_override(("PYMEDIA_GLADIA_API_KEY", "GLADIA_API_KEY")) or self._gladia_settings.value("api_key", "").strip()
        if not api_key:
            QMessageBox.warning(
                self, "缺少 API Key",
                "请在全局设置 (⚙️) 中配置 Gladia API Key。\n"
                "可前往 https://app.gladia.io/ 免费申请。"
            )
            return

        language = self.language_combo.currentData()
        user_script = self.script_edit.toPlainText().strip()

        # 字幕分段参数从全局设置读取
        subtitle_config = {
            "srt_max_chars": int(self._global_settings.value("srt_max_chars", 35)),
            "srt_pause_threshold": float(self._global_settings.value("srt_pause_threshold", 0.3)),
        }

        # 保存 UI 偏好设置
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
        self._translated_segments = []

        self.log_panel.append_log(f"文件: {os.path.basename(media_path)}")
        self.log_panel.append_log(f"语言: {language or '自动检测'} | 分段: {subtitle_config['srt_max_chars']}字/行")
        if user_script:
            self.log_panel.append_log(f"参考文案: {len(user_script)} 字符（用于对齐纠错）")

        # 创建 Worker
        self._worker = WhisperWorker(
            media_path=media_path,
            api_key=api_key,
            language=language if language != "auto" else "auto",
            user_script=user_script,
            subtitle_config=subtitle_config,
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
        self._translated_segments = []

        # 可选翻译
        if self.chk_translate.isChecked() and segments:
            self._run_translation(segments)
        else:
            self._display_segments(segments)

    def _run_translation(self, segments: list):
        """调用 TranslationManager 翻译 segments（使用 Groq API Key）。"""
        self.log_panel.append_log("🌍 正在调用翻译 API...")
        self.progress_bar.setVisible(True)
        from ..utils import get_env_override
        api_key = get_env_override(("PYMEDIA_GROQ_API_KEY", "GROQ_API_KEY")) or self._groq_settings.value("api_key", "").strip()
        target_lang = self.trans_lang_combo.currentData()

        self._translate_worker = TranslationWorker(
            segments=segments,
            api_key=api_key,
            target_lang=target_lang,
        )
        self._translate_thread = QThread()
        self._translate_worker.moveToThread(self._translate_thread)
        self._translate_thread.started.connect(self._translate_worker.run)
        self._translate_worker.progress.connect(self._on_progress)
        self._translate_worker.finished.connect(self._on_translation_finished)
        self._translate_worker.error.connect(self._on_translation_error)
        self._translate_worker.finished.connect(self._translate_thread.quit)
        self._translate_worker.error.connect(self._translate_thread.quit)
        self._translate_thread.start()

    def _on_translation_finished(self, translated: list):
        self._translated_segments = translated
        self._display_segments(self._current_segments, translated)
        self.log_panel.append_log("✅ 翻译完成")
        self.progress_bar.setVisible(False)

    def _on_translation_error(self, message: str):
        self._translated_segments = []
        self.log_panel.append_log(f"⚠️ 翻译失败: {message}，使用原始识别结果")
        self._display_segments(self._current_segments)
        self.progress_bar.setVisible(False)

    def _display_segments(self, segments: list, translated_segments: list | None = None):
        """将 segments 显示到预览面板。"""
        self._current_segments = segments

        # SRT 预览
        srt_text = segments_to_srt_text(segments)
        self.srt_preview.setPlainText(srt_text)

        # 翻译预览
        if translated_segments:
            trans_text = segments_to_srt_text(translated_segments)
            self.trans_preview.setPlainText(trans_text)
        else:
            self.trans_preview.clear()
            self.trans_preview.setPlaceholderText("若启用自动翻译，翻译结果会显示在此处。")

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

        # 选择保存文件名（默认跟随输入文件所在目录）
        media_path = self.drop_zone.file_path
        default_dir = str(Path(media_path).parent) if media_path else ""
        default_name = Path(media_path).stem if media_path else "subtitle"
        default_path = os.path.join(default_dir, f"{default_name}.srt")

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择导出文件",
            default_path,
            "字幕文件 (*.srt *.vtt *.ass *.fcpxml);;所有文件 (*)"
        )
        if not save_path:
            return

        save_dir = str(Path(save_path).parent)
        base_name = Path(save_path).stem

        exported = []
        errors = []

        for fmt in formats:
            out_path = os.path.join(save_dir, f"{base_name}.{fmt}")
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

                # 导出翻译文件
                if self.chk_translate.isChecked() and self._translated_segments:
                    trans_label = self.trans_lang_combo.currentData() or "trans"
                    trans_suffix = "cn" if trans_label == "zh" else trans_label
                    trans_path = os.path.join(save_dir, f"{base_name}_{trans_suffix}.{fmt}")
                    if fmt == "srt":
                        export_srt(self._translated_segments, trans_path)
                    elif fmt == "vtt":
                        export_vtt(self._translated_segments, trans_path)
                    elif fmt == "ass":
                        export_ass(self._translated_segments, trans_path)
                    elif fmt == "fcpxml":
                        export_fcpxml(self._translated_segments, trans_path)
                    exported.append(os.path.basename(trans_path))
                    self.log_panel.append_log(f"✅ 已导出翻译文件: {os.path.basename(trans_path)}")
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
        # 保存语言和翻译偏好到 Gladia QSettings
        self._gladia_settings.setValue("whisper_language", self.language_combo.currentData())
        self._gladia_settings.setValue("whisper_translate", self.chk_translate.isChecked())
        self._gladia_settings.setValue("whisper_trans_lang", self.trans_lang_combo.currentData())

    def _load_settings(self):
        language = self._gladia_settings.value("whisper_language", "auto")
        idx = self.language_combo.findData(language)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)

        do_translate = self._gladia_settings.value("whisper_translate", False)
        if isinstance(do_translate, str):
            do_translate = do_translate.lower() == "true"
        self.chk_translate.setChecked(bool(do_translate))

        trans_lang = self._gladia_settings.value("whisper_trans_lang", "zh")
        idx = self.trans_lang_combo.findData(trans_lang)
        if idx >= 0:
            self.trans_lang_combo.setCurrentIndex(idx)
