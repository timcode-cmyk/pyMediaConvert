import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QComboBox, QMessageBox, QProgressBar, QFileDialog, 
                               QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QSpinBox)
from PySide6.QtCore import Qt

from ..core.videodownloader import YtDlpInfoWorker, YtDlpDownloadWorker
from .styles import apply_common_style

class VideoDownloadWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.info_worker = None
        self.download_worker = None
        self.video_list_data = [] 
        self.is_downloading = False 
        
        self.initUI()
        self.apply_styles()

    def apply_styles(self):
        # 使用统一样式表并保持局部可扩展性
        apply_common_style(self)

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. URL Area
        url_group = QGroupBox("STEP 1: 视频链接解析")
        url_layout = QHBoxLayout(url_group)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴 YouTube/Bilibili 等视频或播放列表链接...")
        self.btn_analyze = QPushButton("🔍 解析链接")
        self.btn_analyze.clicked.connect(self.analyze_url)
        
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.btn_analyze)
        layout.addWidget(url_group)

        # 2. List Area
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        
        tool_layout = QHBoxLayout()
        self.chk_select_all = QCheckBox("全选/取消全选")
        self.chk_select_all.setChecked(True)
        self.chk_select_all.toggled.connect(self.toggle_select_all)
        tool_layout.addWidget(self.chk_select_all)
        tool_layout.addStretch()
        list_layout.addLayout(tool_layout)

        # Updated Table: Added "Status/Progress" column (Column 3)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["", "标题", "时长", "状态/进度"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 40)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        list_layout.addWidget(self.table)
        
        layout.addWidget(list_container)

        # 3. Options Area
        opts_group = QGroupBox("STEP 2: 下载参数设置")
        opts_layout = QVBoxLayout(opts_group)
        
        row1 = QHBoxLayout()
        
        self.chk_audio_only = QCheckBox("仅下载音频")
        self.chk_audio_only.toggled.connect(self.update_format_options)
        
        row1.addWidget(QLabel("格式:"))
        self.combo_format = QComboBox()
        self.combo_format.setMinimumWidth(100) 
        self.combo_format.addItem("mp4", "mp4")
        self.combo_format.addItem("mkv", "mkv")
        self.combo_format.addItem("webm", "webm")
        row1.addWidget(self.combo_format)
        
        row1.addWidget(QLabel("画质:"))
        self.combo_quality = QComboBox()
        self.combo_quality.setMinimumWidth(120)
        self.combo_quality.addItem("Best", "best")
        self.combo_quality.addItem("4K (2160p)", "2160p")
        self.combo_quality.addItem("2K (1440p)", "1440p")
        self.combo_quality.addItem("1080p", "1080p")
        self.combo_quality.addItem("720p", "720p")
        self.combo_quality.addItem("480p", "480p")
        row1.addWidget(self.combo_quality)
        
        row1.addWidget(self.chk_audio_only)

        self.chk_subs = QCheckBox("下载字幕")
        self.combo_sub_lang = QComboBox()
        self.combo_sub_lang.addItems(["en", "zh-Hans", "zh-Hant", "ja", "ko", "auto"])
        self.combo_sub_lang.setEditable(True)
        self.combo_sub_lang.setFixedWidth(100)
        row1.addWidget(self.chk_subs)
        row1.addWidget(self.combo_sub_lang)

        # Thread/concurrency option
        row1.addWidget(QLabel("线程数:"))
        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 8)
        self.spin_concurrency.setValue(4)
        self.spin_concurrency.setFixedWidth(80)
        self.spin_concurrency.setToolTip("并发下载线程数 (1-8)")
        row1.addWidget(self.spin_concurrency)

        row1.addStretch()
        opts_layout.addLayout(row1)

        # row2 = QHBoxLayout()
        
        # row2.addWidget(self.chk_subs)
        # row2.addWidget(self.combo_sub_lang)
        # row2.addStretch()
        
        # opts_layout.addLayout(row2)
        
        # Output Path Row
        path_layout = QHBoxLayout()
        self.out_path = QLineEdit()
        self.out_path.setPlaceholderText("保存路径...")
        self.out_path.setText(os.path.join(os.getcwd(), "Downloads"))
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self.browse_output)
        
        path_layout.addWidget(QLabel("保存至:"))
        path_layout.addWidget(self.out_path)
        path_layout.addWidget(btn_browse)
        opts_layout.addLayout(path_layout)
        
        layout.addWidget(opts_group)

        # 4. Progress & Control Area
        progress_group = QGroupBox("STEP 3: 状态与控制")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(8)

        # 4.1 Status Label & Button
        ctrl_layout = QHBoxLayout()
        self.status_label = QLabel("等待开始...")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)
        
        self.btn_download = QPushButton("⬇️ 开始下载")
        self.btn_download.clicked.connect(self.toggle_download)
        self.btn_download.setMinimumHeight(36)
        self.btn_download.setMinimumWidth(120)
        self.btn_download.setStyleSheet("font-weight: bold;")
        
        ctrl_layout.addWidget(self.status_label, 1)
        ctrl_layout.addWidget(self.btn_download)
        progress_layout.addLayout(ctrl_layout)
        
        # 4.2 Single Overall Progress Bar
        progress_layout.addWidget(QLabel("总进度:"))
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        
        progress_layout.addWidget(self.overall_progress_bar)
        
        layout.addWidget(progress_group)

    def toggle_select_all(self, checked):
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def update_format_options(self):
        is_audio = self.chk_audio_only.isChecked()
        self.combo_format.clear()
        if is_audio:
            self.combo_format.addItem("mp3", "mp3")
            self.combo_format.addItem("m4a", "m4a")
            self.combo_format.addItem("wav", "wav")
            self.combo_quality.setEnabled(False)
            self.chk_subs.setEnabled(False)
        else:
            self.combo_format.addItem("mp4", "mp4")
            self.combo_format.addItem("mkv", "mkv")
            self.combo_format.addItem("webm", "webm")
            self.combo_quality.setEnabled(True)
            self.chk_subs.setEnabled(True)

    def browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if d:
            self.out_path.setText(d)

    def analyze_url(self):
        url = self.url_input.text().strip()
        if not url: return
        
        self.btn_analyze.setEnabled(False)
        self.status_label.setText("正在解析链接信息...")
        self.table.setRowCount(0)
        self.video_list_data = []
        self.chk_select_all.setChecked(True)
        
        self.info_worker = YtDlpInfoWorker(url)
        self.info_worker.finished.connect(self.on_info_loaded)
        self.info_worker.error.connect(self.on_info_error)
        self.info_worker.start()

    def on_info_loaded(self, info):
        self.btn_analyze.setEnabled(True)
        self.status_label.setText("解析完成")
        
        entries = list(info['entries']) if 'entries' in info else [info]
        self.video_list_data = entries
        self.table.setRowCount(len(entries))
        
        for i, entry in enumerate(entries):
            # Checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Checked)
            self.table.setItem(i, 0, chk_item)
            
            # Title
            title = entry.get('title', 'Unknown')
            self.table.setItem(i, 1, QTableWidgetItem(title))
            
            # Duration
            dur = entry.get('duration')
            dur_str = f"{int(dur//60)}:{int(dur%60):02d}" if dur else "--:--"
            self.table.setItem(i, 2, QTableWidgetItem(dur_str))
            
            # Status (New Column)
            self.table.setItem(i, 3, QTableWidgetItem("待下载"))

    def on_info_error(self, err):
        self.btn_analyze.setEnabled(True)
        self.status_label.setText("解析失败")
        QMessageBox.warning(self, "错误", f"无法解析链接: {err}")

    def _truncate(self, text: str, max_len: int = 40) -> str:
        if not text: return ''
        return text if len(text) <= max_len else text[: max_len - 1] + '…'

    def toggle_download(self):
        if self.is_downloading:
            if self.download_worker:
                self.status_label.setText("正在停止...")
                self.btn_download.setEnabled(False)
                # Call stop to set the flag in the worker
                self.download_worker.stop()
        else:
            self.start_download()

    def start_download(self):
        # Build list of dicts: {'url': url, 'ui_index': i, 'title': title}
        items_to_download = []
        
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).checkState() == Qt.Checked:
                entry = self.video_list_data[i]
                url = entry.get('webpage_url') or entry.get('url')
                title = entry.get('title', 'Unknown')
                if url:
                    items_to_download.append({
                        'url': url,
                        'ui_index': i,
                        'title': title
                    })
        
        if not items_to_download:
            QMessageBox.warning(self, "提示", "请至少选择一个视频")
            return
            
        out_dir = self.out_path.text().strip()
        if not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
            
        quality_val = self.combo_quality.currentData() or self.combo_quality.currentText().lower()
        ext_val = self.combo_format.currentData() or self.combo_format.currentText()

        options = {
            'audio_only': self.chk_audio_only.isChecked(),
            'ext': ext_val,
            'quality': quality_val,
            'subtitles': self.chk_subs.isChecked(),
            'sub_lang': self.combo_sub_lang.currentText(),
            'concurrency': self.spin_concurrency.value(),
        }
        
        self.is_downloading = True
        self.btn_download.setText("⏹ 停止下载")
        self.btn_download.setStyleSheet("background-color: #8B0000; color: white; font-weight: bold;")
        
        # Reset table status for selected
        for item in items_to_download:
            self.table.item(item['ui_index'], 3).setText("准备中...")

        self.download_worker = YtDlpDownloadWorker(items_to_download, options, out_dir)
        self.download_worker.progress.connect(self.on_progress)
        self.download_worker.finished.connect(self.on_finished)
        self.download_worker.error.connect(self.on_error)
        self.download_worker.start()

    def on_finished(self):
        self.is_downloading = False
        self.btn_download.setEnabled(True)
        self.btn_download.setText("⬇️ 开始下载")
        self.btn_download.setStyleSheet("font-weight: bold;")
        self.status_label.setText("所有任务完成")
        self.overall_progress_bar.setValue(100)

    def on_error(self, err):
        self.is_downloading = False
        self.btn_download.setEnabled(True)
        self.btn_download.setText("⬇️ 开始下载")
        self.btn_download.setStyleSheet("font-weight: bold;")
        QMessageBox.critical(self, "错误", err)

    def on_progress(self, data):
        # 1. Update Overall Progress Bar
        overall = data.get('overall_percent', 0)
        self.overall_progress_bar.setValue(int(overall))
        
        # 2. Update Status Label (Current File Name) with speed
        raw_name = data.get('status', '')
        display_name = self._truncate(raw_name, 50)
        speed = data.get('speed') or '-'
        self.status_label.setText(f"正在下载: {display_name}  [速度: {speed}]")
        
        # 3. Update Table Cell (Individual Progress)
        ui_index = data.get('ui_index')
        current_pct = data.get('current_percent', 0)
        file_complete = data.get('file_complete', False)
        
        if ui_index is not None and 0 <= ui_index < self.table.rowCount():
            if file_complete:
                self.table.item(ui_index, 3).setText("完成")
            else:
                self.table.item(ui_index, 3).setText(f"{current_pct:.1f}%")