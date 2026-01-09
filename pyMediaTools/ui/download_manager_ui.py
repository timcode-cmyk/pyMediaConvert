import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QProgressBar, QFileDialog, 
    QGroupBox, QHeaderView, QMessageBox, QCheckBox, QSpinBox, QMenu
)
from PySide6.QtCore import Qt, QTimer, Slot, QPoint
from PySide6.QtGui import QAction

from ..core.downloadmanager import DownloadManager
from ..utils import get_default_download_dir
from .styles import apply_common_style
from pyMediaTools import get_logger

# 日志
logger = get_logger(__name__)

class DownloadManagerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = DownloadManager()
        self.download_path = str(get_default_download_dir())
        self.init_ui()

        # 应用统一样式
        apply_common_style(self)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_ui)
        self.timer.start(1000)

    def init_ui(self):
        self.setWindowTitle("pyMedia 下载管理器")
        self.resize(900, 700)
        main_layout = QVBoxLayout(self)

        # --- 顶部设置面板 ---
        settings_group = QGroupBox("下载设置")
        settings_layout = QHBoxLayout(settings_group)

        # 路径选择
        settings_layout.addWidget(QLabel("保存目录:"))
        self.path_label = QLineEdit(self.download_path)
        self.path_label.setReadOnly(True)
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self.select_directory)
        settings_layout.addWidget(self.path_label)
        settings_layout.addWidget(btn_browse)

        # 并行任务数
        settings_layout.addWidget(QLabel("同时下载数:"))
        self.spin_concurrent = QSpinBox()
        self.spin_concurrent.setRange(1, 8)
        self.spin_concurrent.setValue(4)
        self.spin_concurrent.valueChanged.connect(self.update_concurrent_limit)
        settings_layout.addWidget(self.spin_concurrent)

        # 功能开关
        self.chk_proxy = QCheckBox("接管系统下载")
        self.chk_proxy.setToolTip("开启后，浏览器插件可将任务发送至此")
        self.chk_accel = QCheckBox("启用分块加速")
        self.chk_accel.setChecked(True)
        settings_layout.addWidget(self.chk_proxy)
        settings_layout.addWidget(self.chk_accel)

        main_layout.addWidget(settings_group)

        # --- 总进度条与批量操作 ---
        control_panel = QHBoxLayout()
        
        # 批量操作按钮
        self.btn_pause_all = QPushButton("全部暂停")
        self.btn_pause_all.clicked.connect(lambda: self.manager._call_rpc("pauseAll"))
        self.btn_start_all = QPushButton("全部开始")
        self.btn_start_all.clicked.connect(lambda: self.manager._call_rpc("unpauseAll"))
        self.btn_purge = QPushButton("清空已完成/失败")
        self.btn_purge.clicked.connect(lambda: self.manager._call_rpc("purgeDownloadResult"))
        
        control_panel.addWidget(self.btn_start_all)
        control_panel.addWidget(self.btn_pause_all)
        control_panel.addWidget(self.btn_purge)
        control_panel.addStretch()

        # 进度信息
        control_panel.addWidget(QLabel("总进度:"))
        self.total_progress = QProgressBar()
        self.total_progress.setFixedWidth(200)
        control_panel.addWidget(self.total_progress)
        self.total_speed_label = QLabel("总速度: 0 KB/s")
        control_panel.addWidget(self.total_speed_label)
        
        main_layout.addLayout(control_panel)

        # --- 添加任务区域 ---
        add_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("在此粘贴 URL 链接...")
        btn_add = QPushButton("新建下载")
        btn_add.clicked.connect(self.add_new_task)
        add_layout.addWidget(self.url_input)
        add_layout.addWidget(btn_add)
        main_layout.addLayout(add_layout)

        # --- 下载列表 ---
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["文件名", "进度", "大小", "速度", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        main_layout.addWidget(self.table)

    def select_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择下载保存目录", self.download_path)
        if dir_path:
            self.download_path = dir_path
            self.path_label.setText(dir_path)

    def update_concurrent_limit(self, value):
        self.manager.change_global_option(value)

    def add_new_task(self):
        url = self.url_input.text().strip()
        if not url: return
        gid = self.manager.add_download(url, self.download_path, self.chk_accel.isChecked())
        if gid:
            self.url_input.clear()
        else:
            QMessageBox.critical(self, "错误", "无法连接到下载核心")

    def show_context_menu(self, pos: QPoint):
        row = self.table.currentRow()
        if row < 0: return
        
        gid = self.table.item(row, 0).data(Qt.UserRole)
        status = self.table.item(row, 4).text()

        menu = QMenu(self)
        
        # 正在下载或等待中，显示暂停
        if status in ["active", "waiting"]:
            act_pause = QAction("暂停任务", self)
            act_pause.triggered.connect(lambda: self.manager.pause_task(gid))
            menu.addAction(act_pause)
        # 已暂停，显示继续
        elif status == "paused":
            act_resume = QAction("继续任务", self)
            act_resume.triggered.connect(lambda: self.manager.unpause_task(gid))
            menu.addAction(act_resume)

        menu.addSeparator()
        act_del = QAction("彻底删除任务", self)
        act_del.triggered.connect(lambda: self.manager.remove_task(gid))
        menu.addAction(act_del)
        
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    @Slot()
    def refresh_ui(self):
        tasks = self.manager.get_status_all()
        
        if not tasks:
            self.table.setRowCount(0)
            self.total_progress.setValue(0)
            self.total_speed_label.setText("总速度: 0 KB/s")
            return

        self.table.setRowCount(len(tasks))
        total_bytes = 0
        completed_bytes = 0
        total_speed = 0

        for i, task in enumerate(tasks):
            gid = task['gid']
            status = task['status']
            
            # 文件名获取
            files = task.get('files', [])
            name = "正在解析..."
            if files and files[0].get('path'):
                name = os.path.basename(files[0]['path'])
            elif files and files[0].get('uris'):
                # 如果还未确定文件名，尝试从URL获取
                uri = files[0]['uris'][0]['uri']
                name = uri.split('/')[-1].split('?')[0] or "未知任务"
            
            # 进度数据转换
            try:
                t_len = int(task.get('totalLength', 0))
                c_len = int(task.get('completedLength', 0))
                speed = int(task.get('downloadSpeed', 0))
            except (ValueError, TypeError):
                t_len, c_len, speed = 0, 0, 0
            
            total_bytes += t_len
            completed_bytes += c_len
            total_speed += speed

            # 更新表格
            item_name = QTableWidgetItem(name)
            item_name.setData(Qt.UserRole, gid)
            self.table.setItem(i, 0, item_name)
            
            p_bar = QProgressBar()
            p_bar.setValue(int(c_len / t_len * 100) if t_len > 0 else 0)
            self.table.setCellWidget(i, 1, p_bar)
            
            self.table.setItem(i, 2, QTableWidgetItem(f"{t_len/1024/1024:.2f} MB"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{speed/1024:.1f} KB/s"))
            self.table.setItem(i, 4, QTableWidgetItem(status))

        # 更新总进度
        if total_bytes > 0:
            self.total_progress.setValue(int(completed_bytes / total_bytes * 100))
        else:
            self.total_progress.setValue(0)
            
        # 格式化总速度显示
        if total_speed > 1024 * 1024:
            self.total_speed_label.setText(f"总速度: {total_speed/1024/1024:.2f} MB/s")
        else:
            self.total_speed_label.setText(f"总速度: {total_speed/1024:.1f} KB/s")

    def closeEvent(self, event):
        self.manager.stop_server()
        super().closeEvent(event)