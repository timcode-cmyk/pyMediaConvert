import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QComboBox, QMessageBox, QProgressBar, QFileDialog, 
                               QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QSpinBox,
                               QDialog, QTextEdit, QMenu, QApplication, QFormLayout)
from PySide6.QtCore import Qt, QPoint, Signal, QSettings
from PySide6.QtGui import QAction, QFont

from ..core.videodownloader import YtDlpInfoWorker, YtDlpDownloadWorker
from ..core.ytdlp_updater import YtDlpVersionManager
from ..core.ytdlp_update_worker import YtDlpCheckUpdateWorker, YtDlpUpdateWorker
from .styles import apply_common_style

class VideoDownloadWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.info_worker = None
        self.download_worker = None
        self.check_update_worker = None
        self.update_worker = None
        self.video_list_data = [] 
        self.is_downloading = False
        
        self.settings = QSettings("pyMediaTools", "VideoDownloader")
        
        # yt-dlp 版本管理
        self.version_manager = YtDlpVersionManager()
        self.local_version = self.version_manager.get_local_version()
        self.remote_version = None
        self.update_dialog = None  # 引用更新对话框实例
        
        self.initUI()
        self.apply_styles()
        
        # 应用启动后自动检查更新
        self.check_update_async()

    def apply_styles(self):
        # 使用统一样式表并保持局部可扩展性
        apply_common_style(self)

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        # --- 区域1: 视频链接解析与列表 (合并) ---
        parse_list_group = QGroupBox("任务列表")
        parse_list_layout = QVBoxLayout(parse_list_group)
        parse_list_layout.setSpacing(10)
        parse_list_layout.setContentsMargins(10, 15, 10, 10)

        # URL Input Row
        url_layout = QHBoxLayout()
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴 YouTube/Bilibili 等视频或播放列表链接...")
        self.btn_analyze = QPushButton("🔍 解析链接")
        self.btn_analyze.clicked.connect(self.analyze_url)
        
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.btn_analyze)
        parse_list_layout.addLayout(url_layout)

        # Table Tools
        tool_layout = QHBoxLayout()
        self.chk_select_all = QCheckBox("全选/取消全选")
        self.chk_select_all.setChecked(True)
        self.chk_select_all.toggled.connect(self.toggle_select_all)
        tool_layout.addWidget(self.chk_select_all)
        tool_layout.addStretch()
        parse_list_layout.addLayout(tool_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["", "标题", "时长", "状态/进度"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 40)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        parse_list_layout.addWidget(self.table)
        
        layout.addWidget(parse_list_group, 1) # Stretch factor 1

        # --- 区域2: 下载参数与进度 (合并) ---
        opts_prog_group = QGroupBox("下载设置与控制")
        opts_prog_layout = QVBoxLayout(opts_prog_group)
        opts_prog_layout.setSpacing(10)
        opts_prog_layout.setContentsMargins(10, 15, 10, 10)

        # Options Row
        opts_row = QHBoxLayout()
        
        self.chk_audio_only = QCheckBox("仅下载音频")
        self.chk_audio_only.toggled.connect(self.update_format_options)
        
        opts_row.addWidget(QLabel("格式:"))
        self.combo_format = QComboBox()
        self.combo_format.setMinimumWidth(80) 
        self.combo_format.addItem("mp4", "mp4")
        self.combo_format.addItem("mkv", "mkv")
        self.combo_format.addItem("webm", "webm")
        opts_row.addWidget(self.combo_format)
        
        opts_row.addWidget(QLabel("画质:"))
        self.combo_quality = QComboBox()
        self.combo_quality.setMinimumWidth(100)
        self.combo_quality.addItem("Best", "best")
        self.combo_quality.addItem("4K (2160p)", "2160p")
        self.combo_quality.addItem("2K (1440p)", "1440p")
        self.combo_quality.addItem("1080p", "1080p")
        self.combo_quality.addItem("720p", "720p")
        self.combo_quality.addItem("480p", "480p")
        opts_row.addWidget(self.combo_quality)
        
        opts_row.addWidget(self.chk_audio_only)
        
        opts_row.addWidget(QLabel("字幕:"))
        self.chk_subs = QCheckBox("下载")
        self.combo_sub_lang = QComboBox()
        self.combo_sub_lang.addItems(["en", "zh-Hans", "zh-Hant", "ja", "ko", "auto"])
        self.combo_sub_lang.setEditable(True)
        self.combo_sub_lang.setFixedWidth(80)
        opts_row.addWidget(self.chk_subs)
        opts_row.addWidget(self.combo_sub_lang)

        opts_row.addWidget(QLabel("线程:"))
        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 8)
        self.spin_concurrency.setValue(4)
        self.spin_concurrency.setFixedWidth(60)
        self.spin_concurrency.setToolTip("并发下载线程数 (1-8)")
        opts_row.addWidget(self.spin_concurrency)

        opts_row.addStretch()

        # Check Update Button
        self.btn_check_update = QPushButton("检查更新")
        # self.btn_check_update.setFixedWidth(90)
        self.btn_check_update.clicked.connect(self.open_update_dialog)
        opts_row.addWidget(self.btn_check_update)

        opts_prog_layout.addLayout(opts_row)

        # Path Row
        path_layout = QHBoxLayout()
        self.out_path = QLineEdit()
        self.out_path.setPlaceholderText("保存路径...")

        default_download_path = self.settings.value("default_path", os.path.join(os.getcwd(), "Downloads")) # pyright: ignore[reportArgumentType]
        self.out_path.setText(default_download_path)

        self.btn_default_path = QPushButton("设置默认")
        self.btn_default_path.setToolTip("配置默认保存路径")
        self.btn_default_path.clicked.connect(self.configure_default_path)

        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self.browse_output)
        
        path_layout.addWidget(QLabel("保存至:"))
        path_layout.addWidget(self.out_path)
        path_layout.addWidget(btn_browse)
        path_layout.addWidget(self.btn_default_path)
        opts_prog_layout.addLayout(path_layout)



        # Progress & Control Row
        ctrl_layout = QHBoxLayout()
        
        # Status & Progress Stack
        status_prog_layout = QVBoxLayout()
        status_prog_layout.setSpacing(5)
        
        self.status_label = QLabel("等待开始...")
        self.status_label.setObjectName("StatusLabel")
        
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_bar.setFixedHeight(15)
        
        status_prog_layout.addWidget(self.status_label)
        status_prog_layout.addWidget(self.overall_progress_bar)
        
        self.btn_download = QPushButton("⬇️ 开始下载")
        self.btn_download.clicked.connect(self.toggle_download)
        self.btn_download.setMinimumHeight(45)
        self.btn_download.setMinimumWidth(140)
        self.btn_download.setStyleSheet("font-weight: bold;")
        
        ctrl_layout.addLayout(status_prog_layout, 1)
        ctrl_layout.addWidget(self.btn_download)
        
        opts_prog_layout.addLayout(ctrl_layout)
        
        layout.addWidget(opts_prog_group)

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

    def configure_default_path(self):
        current_path = self.out_path.text()
        d = QFileDialog.getExistingDirectory(self, "选择默认保存目录", current_path)
        if d:
            self.settings.setValue("default_path", d)
            self.out_path.setText(d)
            QMessageBox.information(self, "设置成功", f"默认下载路径已更新")

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

    def show_context_menu(self, pos):
        # pos is relative to self.table
        global_pos = self.table.mapToGlobal(pos)
        # itemAt expects coordinates relative to viewport
        viewport_pos = self.table.viewport().mapFromGlobal(global_pos)
        item = self.table.itemAt(viewport_pos)
        
        if not item:
            return
        
        row = item.row()
        if row < 0 or row >= len(self.video_list_data):
            return
            
        entry = self.video_list_data[row]
        url = entry.get('webpage_url') or entry.get('url')
        
        menu = QMenu(self)
        
        # Action: Download this video
        action_download = QAction("⬇️ 下载此视频", self)
        action_download.triggered.connect(lambda: self.download_single_video(row))
        menu.addAction(action_download)
        
        # Action: Copy Link
        if url:
            action_copy = QAction("🔗 复制链接", self)
            action_copy.triggered.connect(lambda: QApplication.clipboard().setText(url))
            menu.addAction(action_copy)
            
        menu.exec(global_pos)

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
            
        self._execute_download(items_to_download)

    def download_single_video(self, row):
        if self.is_downloading:
            QMessageBox.warning(self, "提示", "当前已有下载任务正在进行，请等待完成后再试。")
            return

        entry = self.video_list_data[row]
        url = entry.get('webpage_url') or entry.get('url')
        title = entry.get('title', 'Unknown')
        
        if url:
            items = [{
                'url': url,
                'ui_index': row,
                'title': title
            }]
            self._execute_download(items)

    def open_update_dialog(self):
        """打开版本管理与更新对话框"""
        # 1. 创建对话框实例
        self.update_dialog = YtDlpUpdateDialog(self, self.local_version, self.remote_version)
        self.update_dialog.update_requested.connect(self.start_update)

        # 2. 立即触发异步检查更新
        self.check_update_async()

        # 3. 显示对话框 (exec() 会阻塞直到关闭)
        self.update_dialog.exec()

        # 4. 对话框关闭后清理引用
        self.update_dialog = None  # 对话框关闭后清理引用

    def _execute_download(self, items_to_download):
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

    # ============ yt-dlp 版本管理相关方法 ============
    
    def check_update_async(self):
        """异步检查yt-dlp更新"""
        if self.check_update_worker is not None and self.check_update_worker.isRunning():
            return
        
        # 如果更新对话框已打开，则向其发送“正在检查”的状态
        if self.update_dialog and self.update_dialog.isVisible():
            self.update_dialog.set_checking_status()

        self.check_update_worker = YtDlpCheckUpdateWorker()
        self.check_update_worker.version_checked.connect(self.on_version_checked)
        self.check_update_worker.error.connect(self.on_check_update_error)
        self.check_update_worker.start()
    
    def on_version_checked(self, info: dict):
        """版本检查完成的回调"""
        try:
            local = info.get('local_version')
            remote = info.get('remote_version')
            has_update = info.get('has_update', False)
            
            # 更新本地版本显示
            if local:
                self.local_version = local
            
            if remote:
                self.remote_version = remote
            
            # 如果对话框打开中，更新对话框显示
            if self.update_dialog and self.update_dialog.isVisible():
                self.update_dialog.update_status(local, remote)
                self.update_dialog.set_update_enabled(has_update)
            
            if has_update and remote and local:
                # 如果对话框没打开，则弹窗提示
                if not (self.update_dialog and self.update_dialog.isVisible()):
                    QMessageBox.information(
                        self, "yt-dlp 更新可用", f"发现新版本: {remote}\n当前版本: {local}\n\n点击'检查更新'按钮可进行更新。"
                    )
            else:
                if local == remote:
                    pass
        except Exception as e:
            self.on_check_update_error(f"处理版本信息失败: {str(e)}")
    
    def on_check_update_error(self, error_msg: str):
        """版本检查错误的回调"""
        if self.update_dialog and self.update_dialog.isVisible():
            self.update_dialog.update_status(self.local_version, "❌ 检查失败")

        # 只显示警告，不影响用户操作
        import logging
        logging.warning(f"yt-dlp 版本检查失败: {error_msg}")
    
    def start_update(self):
        """开始yt-dlp更新"""
        if self.is_downloading:
            QMessageBox.warning(self, "提示", "下载中，无法同时更新yt-dlp")
            return
        
        if not self.remote_version:
            QMessageBox.warning(self, "提示", "无法获取远程版本，请先检查更新")
            return
        
        # 使用现有的对话框或创建新的（如果是直接调用）
        if self.update_dialog:
            dialog = self.update_dialog
        else: # 理论上不会进入此分支，因为 start_update 是由对话框触发的
            return
            
        dialog.set_update_enabled(False) # 更新中禁用按钮
        dialog.add_log("正在启动更新进程...")
        
        # 创建更新Worker
        self.update_worker = YtDlpUpdateWorker(update_method='github')
        self.update_worker.progress.connect(dialog.add_log)
        self.update_worker.finished.connect(lambda info: self.on_update_finished(info, dialog))
        self.update_worker.error.connect(lambda err: self.on_update_error(err, dialog))
        
        # 禁用相关按钮
        self.btn_analyze.setEnabled(False)
        self.btn_download.setEnabled(False)
        
        # 显示对话框并开始更新
        self.update_worker.start()
    
    def on_update_finished(self, info: dict, dialog):
        """更新完成的回调"""
        success = info.get('success', False)
        message = info.get('message', '')
        new_version = info.get('new_version')
        
        if success:
            self.local_version = new_version
            dialog.update_status(new_version, self.remote_version)
            
            dialog.add_log(f"✅ {message}")
            QMessageBox.information(
                self,
                "更新成功",
                f"yt-dlp 已成功更新到版本 {new_version}\n\n"
                "程序将继续使用新版本。"
            )
        else:
            dialog.add_log(f"❌ {message}")
            QMessageBox.warning(
                self,
                "更新失败",
                f"更新过程中出现错误:\n{message}\n\n"
                "已自动回滚到原版本。"
            )
        
        # 重新启用按钮
        self.btn_analyze.setEnabled(True)
        self.btn_download.setEnabled(True)
    
    def on_update_error(self, error_msg: str, dialog):
        """更新错误的回调"""
        dialog.add_log(f"❌ 错误: {error_msg}")
        
        QMessageBox.critical(
            self,
            "更新失败",
            f"yt-dlp 更新失败:\n{error_msg}"
        )
        
        # 重新启用按钮
        self.btn_analyze.setEnabled(True)
        self.btn_download.setEnabled(True)


class YtDlpUpdateDialog(QDialog):
    """yt-dlp 版本管理与更新对话框"""
    
    update_requested = Signal()
    
    def __init__(self, parent, local_version, remote_version):
        super().__init__(parent)
        apply_common_style(self)

        self.setWindowTitle("yt-dlp 版本管理")
        self.resize(550, 400)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 版本信息区域
        info_group = QGroupBox("版本信息")
        form_layout = QFormLayout(info_group)
        
        self.lbl_local = QLabel(str(local_version or "未知"))
        self.lbl_remote = QLabel(str(remote_version or "正在检查..."))
        
        form_layout.addRow("当前本地版本:", self.lbl_local)
        form_layout.addRow("最新远程版本:", self.lbl_remote)
        layout.addWidget(info_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        self.btn_update = QPushButton("立即更新")
        self.btn_update.setEnabled(False) # 初始禁用，等待检查结果
        self.btn_update.clicked.connect(self.update_requested.emit)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_update)
        layout.addLayout(btn_layout)
        
        # 进度日志
        layout.addWidget(QLabel("更新日志:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        # 使用等宽字体，颜色由样式表控制
        log_font = QFont()
        log_font.setFamily("Courier New, Courier, monospace")
        log_font.setPointSize(10)
        self.log_text.setFont(log_font)

        layout.addWidget(self.log_text, 1)
        
        # 关闭按钮
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.accept)
        layout.addWidget(self.btn_close, 0, Qt.AlignRight)

        # 关键修复：在构造函数末尾，当所有子控件都已创建且窗口尺寸有效时，再进行居中移动
        if parent:
            self.move(parent.geometry().center() - self.rect().center())


    def update_status(self, local, remote):
        self.lbl_local.setText(str(local or "未知"))
        if remote:
            self.lbl_remote.setText(str(remote))
        else:
            self.lbl_remote.setText("获取失败")

    def set_update_enabled(self, enabled):
        self.btn_update.setEnabled(enabled)
    
    def set_checking_status(self):
        """设置UI为正在检查状态"""
        self.lbl_remote.setText("正在检查...")
        self.btn_update.setEnabled(False)

    def add_log(self, message: str):
        """添加日志消息"""
        self.log_text.append(message)
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )