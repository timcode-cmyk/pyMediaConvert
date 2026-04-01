import os
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QProgressBar, QMessageBox,
                               QFileDialog, QSizePolicy, QGroupBox, QSlider, QCheckBox, QSpinBox, QColorDialog, QFontComboBox, QDialog, QFormLayout, QDialogButtonBox, QTextEdit, QGridLayout, QComboBox)
from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtGui import QFont, QColor

from .styles import apply_common_style
from .media_tools_ui import DropLineEdit, ProgressMonitor
from ..core.vidoecut import SceneCutter, get_available_fonts, get_available_ass_files
from ..utils import get_resource_path
from pyMediaTools import get_logger

logger = get_logger(__name__)


class SceneCutWorker(QObject):
    finished = Signal(bool, str)

    def __init__(self, input_path, output_path, options, monitor, parent=None):
        super().__init__(parent)
        self.input_path = input_path
        self.output_path = output_path
        self.options = options
        self.monitor = monitor

    @Slot()
    def run(self):
        is_successful = False
        error_msg = ""
        try:
            # 从watermark_params中提取font_name用于初始化SceneCutter
            font_name = None
            if self.options.get('watermark_params'):
                font_name = self.options['watermark_params'].get('font_name')
            
            cutter = SceneCutter(monitor=self.monitor, font_name=font_name)
            cutter.run(Path(self.input_path), Path(self.output_path), **self.options)
            is_successful = not self.monitor.check_stop_flag()
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            logger.exception(f"SceneCutWorker 发生异常: {e}")
        finally:
            self.finished.emit(is_successful, error_msg)

class WatermarkSettingsDialog(QDialog):
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("水印详细设置")
        self.setModal(True)
        self.setMinimumWidth(450)

        self.settings = current_settings or {}
        
        # 加载可用字体
        self.available_fonts = get_available_fonts()

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # Font - 使用下拉框选择
        self.font_combo = QComboBox()
        if self.available_fonts:
            self.font_combo.addItems(self.available_fonts.keys())
            # 设置当前选择
            current_font = self.settings.get('font_name', list(self.available_fonts.keys())[0])
            idx = self.font_combo.findText(current_font)
            if idx >= 0:
                self.font_combo.setCurrentIndex(idx)
        else:
            self.font_combo.addItem("未找到字体文件")
            self.font_combo.setEnabled(False)
        
        self.font_combo.setToolTip("从 assets 目录选择字体文件")
        form_layout.addRow("字体文件:", self.font_combo)

        # Size
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 200)
        self.size_spin.setValue(int(self.settings.get('font_size', 24)))
        form_layout.addRow("字体大小:", self.size_spin)

        # Color
        self.color_btn = QPushButton(self.settings.get('font_color', 'white'))
        self.color_btn.setToolTip("点击选择颜色")
        self.set_button_color(self.color_btn, self.settings.get('font_color', 'white'))
        self.color_btn.clicked.connect(self.pick_color)
        form_layout.addRow("字体颜色:", self.color_btn)

        # Position
        self.x_edit = QLineEdit(str(self.settings.get('x', "W-tw-10")))
        self.y_edit = QLineEdit(str(self.settings.get('y', "40")))
        self.x_edit.setToolTip("例如: 10, w-text_w-10, (w-text_w)/2")
        self.y_edit.setToolTip("例如: 10, h-text_h-10, (h-text_h)/2")
        form_layout.addRow("X 坐标:", self.x_edit)
        form_layout.addRow("Y 坐标:", self.y_edit)

        main_layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def set_button_color(self, button, color_name):
        color = QColor(color_name)
        if color.isValid():
            button.setStyleSheet(f"background-color: {color.name()}; color: {'black' if color.lightness() > 128 else 'white'}; border: 1px solid #888;")

    def pick_color(self):
        current_color = QColor(self.color_btn.text())
        color = QColorDialog.getColor(current_color, self, "选择颜色")
        if color.isValid():
            self.color_btn.setText(color.name())
            self.set_button_color(self.color_btn, color.name())

    def get_settings(self):
        return {
            'font_name': self.font_combo.currentText(),
            'font_size': str(self.size_spin.value()),
            'font_color': self.color_btn.text(),
            'x': self.x_edit.text(),
            'y': self.y_edit.text(),
        }

class VideoCutWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker_thread = None
        self.monitor = None
        self.is_processing = False
        
        # 加载可用资源，初始化水印设置 (必须在 init_ui 之前)
        available_fonts = get_available_fonts()
        default_font = list(available_fonts.keys())[0] if available_fonts else "Roboto-Bold"
        self.available_ass_files = get_available_ass_files()
        
        self.watermark_settings = {
            'font_name': default_font,
            'font_size': "24",
            'font_color': "white",
            'x': "W-tw-10",
            'y': "40",
            'text': list(self.available_ass_files.keys())[0] if self.available_ass_files else ""
        }
        
        self.init_ui()
        self.apply_styles()

    def apply_styles(self):
        apply_common_style(self)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 15)
        main_layout.setSpacing(10)

        # 1. 路径设置
        path_group = QGroupBox("文件路径")
        path_layout = QVBoxLayout(path_group)
        self.input_path_edit = DropLineEdit()
        self.input_path_edit.setPlaceholderText("📂 拖放视频文件或文件夹到此处")
        self.input_path_edit.setMinimumHeight(40)
        self.input_path_edit.pathDropped.connect(self.update_output_path)
        self.input_path_edit.textChanged.connect(self.update_output_path)
        
        input_btn = QPushButton("浏览...")
        input_btn.clicked.connect(self.select_input_path)
        input_box = QHBoxLayout()
        input_box.addWidget(self.input_path_edit)
        input_box.addWidget(input_btn)
        path_layout.addLayout(input_box)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("输出目录将自动生成")
        self.output_path_edit.setReadOnly(True)
        path_layout.addWidget(self.output_path_edit)
        main_layout.addWidget(path_group)

        # 2. 参数设置
        options_group = QGroupBox("参数设置")
        options_layout = QGridLayout(options_group)
        options_layout.setSpacing(10)

        # 阈值
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.setValue(20)
        self.threshold_label = QLabel("20%")
        self.threshold_slider.valueChanged.connect(lambda v: self.threshold_label.setText(f"{v}%"))
        # 导出视频
        self.chk_export_video = QCheckBox("导出视频")
        self.chk_export_video.setChecked(True)
        
        # 导出静帧
        self.chk_export_frame = QCheckBox("导出静帧")
        self.chk_export_frame.setChecked(True)

        self.spin_frame_offset = QSpinBox()
        self.spin_frame_offset.setRange(0, 1000)
        self.spin_frame_offset.setValue(10)
        
        # 建立相互依赖逻辑
        self.chk_export_video.toggled.connect(self._on_export_video_toggled)
        self.chk_export_frame.toggled.connect(self._on_export_frame_toggled)

        options_layout.addWidget(QLabel("场景检测阈值:"), 0, 0)
        options_layout.addWidget(self.threshold_slider, 0, 1)
        options_layout.addWidget(self.threshold_label, 0, 2)
        options_layout.addWidget(self.chk_export_video, 0, 3)
        options_layout.addWidget(self.chk_export_frame, 0, 4)
        options_layout.addWidget(QLabel("偏移量:"), 0, 5)
        options_layout.addWidget(self.spin_frame_offset, 0, 6)

        # 水印
        self.chk_add_watermark = QCheckBox("添加水印:")
        self.chk_add_watermark.setChecked(False)
        
        # 修改为下拉菜单，读取 assets 中的 .ass 字幕作为列表
        self.combo_watermark_ass = QComboBox()
        if self.available_ass_files:
            self.combo_watermark_ass.addItems(self.available_ass_files.keys())
        else:
            self.combo_watermark_ass.addItem("无 .ass 文件")
            self.combo_watermark_ass.setEnabled(False)

        self.btn_watermark_settings = QPushButton("水印设置")
        self.btn_watermark_settings.clicked.connect(self.open_watermark_settings)
        # 暂时封存按钮
        self.btn_watermark_settings.setVisible(False)
        
        self.chk_add_watermark.toggled.connect(self.combo_watermark_ass.setEnabled)
        # self.chk_add_watermark.toggled.connect(self.btn_watermark_settings.setEnabled)
        self.combo_watermark_ass.setEnabled(False)

        options_layout.addWidget(self.chk_add_watermark, 1, 0)
        options_layout.addWidget(self.combo_watermark_ass, 1, 1, 1, 2)
        options_layout.addWidget(self.btn_watermark_settings, 1, 3)

        options_layout.setColumnStretch(1, 1)
        main_layout.addWidget(options_group)

        # 3. 重命名设置
        rename_group = QGroupBox("片段重命名 (可选)")
        rename_layout = QVBoxLayout(rename_group)
        
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("人员ID:"))
        self.person_id_edit = QLineEdit()
        self.person_id_edit.setPlaceholderText("例如: Tim")
        id_layout.addWidget(self.person_id_edit)
        rename_layout.addLayout(id_layout)

        rename_layout.addWidget(QLabel("自定义片段名称 (每行对应一个片段):"))
        self.rename_edit = QTextEdit()
        self.rename_edit.setPlaceholderText("第一段视频的名称\n第二段视频的名称\n...")
        self.rename_edit.setMinimumHeight(60)
        rename_layout.addWidget(self.rename_edit)

        naming_info = QLabel("命名规则: 日期_人员ID_自定义名称_序号.mp4")
        naming_info.setStyleSheet("color: palette(mid); font-size: 11px;")
        rename_layout.addWidget(naming_info)

        main_layout.addWidget(rename_group)

        # 3. 进度与控制
        progress_group = QGroupBox("状态与控制")
        progress_layout = QVBoxLayout(progress_group)
        self.status_label = QLabel("等待开始...")
        self.status_label.setObjectName("StatusLabel")
        self.overall_progress_bar = QProgressBar()
        self.file_progress_bar = QProgressBar()
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(QLabel("总进度:"))
        progress_layout.addWidget(self.overall_progress_bar)
        progress_layout.addWidget(QLabel("当前文件进度:"))
        progress_layout.addWidget(self.file_progress_bar)
        main_layout.addWidget(progress_group)

        self.start_stop_button = QPushButton("🚀 开始处理")
        self.start_stop_button.setObjectName('StartStopButton')
        self.start_stop_button.setProperty('converting', 'false')
        self.start_stop_button.setMinimumHeight(40)
        self.start_stop_button.clicked.connect(self.toggle_processing)
        main_layout.addWidget(self.start_stop_button)

    def select_input_path(self):
        # 支持选单个文件或整个目录
        path, _ = QFileDialog.getOpenFileName(self, "选择视频文件或目录", "", "视频文件 (*.mp4 *.mkv *.mov *.avi *.m4v *.webm);;所有文件 (*)")
        if not path:
            path = QFileDialog.getExistingDirectory(self, "选择包含视频的目录")
        if path:
            self.input_path_edit.setText(path)

    @Slot(str)
    def update_output_path(self, input_path_str):
        if input_path_str and os.path.exists(input_path_str):
            p = Path(input_path_str)
            parent_dir = p.parent if p.is_file() else p
            self.output_path_edit.setText(str(parent_dir / "SCENE_CUT_OUTPUT"))
        else:
            self.output_path_edit.setText("")

    def open_watermark_settings(self):
        dialog = WatermarkSettingsDialog(self, self.watermark_settings)
        if dialog.exec() == QDialog.Accepted:
            self.watermark_settings.update(dialog.get_settings())
            # Update text from main UI
            self.watermark_settings['text'] = self.combo_watermark_ass.currentText()
            logger.info(f"水印参数已更新: {self.watermark_settings}")

    def _on_export_video_toggled(self, checked):
        # 取消导出视频时，导出静帧无法取消 (必须勾选并禁用)
        if not checked:
            self.chk_export_frame.setChecked(True)
            self.chk_export_frame.setEnabled(False)
        else:
            self.chk_export_frame.setEnabled(True)

    def _on_export_frame_toggled(self, checked):
        # 取消导出静帧时，导出视频无法取消 (必须勾选并禁用)
        self.spin_frame_offset.setEnabled(checked)
        if not checked:
            self.chk_export_video.setChecked(True)
            self.chk_export_video.setEnabled(False)
        else:
            self.chk_export_video.setEnabled(True)

    def toggle_processing(self):
        if self.is_processing:
            self.stop_processing()
        else:
            self.start_processing()

    def start_processing(self):
        input_path = self.input_path_edit.text().strip()
        output_path = self.output_path_edit.text().strip()

        if not input_path or not os.path.exists(input_path):
            QMessageBox.warning(self, "错误", "请输入有效的输入路径。")
            return

        Path(output_path).mkdir(parents=True, exist_ok=True)

        person_id = self.person_id_edit.text().strip()
        rename_lines = self.rename_edit.toPlainText().splitlines()

        options = {
            'threshold': self.threshold_slider.value() / 100.0,
            'export_video': self.chk_export_video.isChecked(),
            'export_frame': self.chk_export_frame.isChecked(),
            'frame_offset': self.spin_frame_offset.value(),
            'watermark_params': None,
            'person_id': person_id,
            'rename_lines': rename_lines
        }

        if self.chk_add_watermark.isChecked():
            try:
                # Update text from the main UI (selected .ass file)
                self.watermark_settings['text'] = self.combo_watermark_ass.currentText()
                
                # 验证选择的字体是否存在
                available_fonts = get_available_fonts()
                if self.watermark_settings['font_name'] not in available_fonts:
                    raise ValueError(f"字体 '{self.watermark_settings['font_name']}' 未找到。可用字体: {', '.join(available_fonts.keys())}")
                
                options['watermark_params'] = self.watermark_settings.copy()
            except Exception as e:
                QMessageBox.critical(self, "水印参数错误", str(e))
                return

        self.is_processing = True
        self.start_stop_button.setText("🛑 停止处理")
        self.start_stop_button.setProperty('converting', 'true')
        self.start_stop_button.style().polish(self.start_stop_button)

        self.monitor = ProgressMonitor()
        self.worker = SceneCutWorker(input_path, output_path, options, self.monitor)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_processing_finished)
        self.monitor.overall_progress.connect(self.update_overall_progress)
        self.monitor.file_progress.connect(self.update_file_progress)

        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    def stop_processing(self):
        if self.monitor:
            self.monitor.request_stop()
            self.status_label.setText("正在请求停止...")
            self.start_stop_button.setEnabled(False)

    @Slot(bool, str)
    def on_processing_finished(self, success, error_msg):
        self.is_processing = False
        self.start_stop_button.setEnabled(True)
        self.start_stop_button.setText("🚀 开始处理")
        self.start_stop_button.setProperty('converting', 'false')
        self.start_stop_button.style().polish(self.start_stop_button)

        if success:
            # make sure bars reach full
            self.overall_progress_bar.setValue(self.overall_progress_bar.maximum())
            self.file_progress_bar.setValue(self.file_progress_bar.maximum())
            self.status_label.setText("处理完成！")
            QMessageBox.information(self, "完成", "所有任务已成功完成。")
        elif self.monitor and self.monitor.check_stop_flag():
            self.status_label.setText("用户已停止。")
        else:
            self.status_label.setText("处理失败。")
            QMessageBox.critical(self, "错误", f"处理过程中发生错误:\n{error_msg}")

    @Slot(int, int, str)
    def update_overall_progress(self, current, total, status):
        # always update range first, then value
        self.overall_progress_bar.setRange(0, total)
        # clamp current to [0,total]
        if total > 0 and current >= total:
            self.overall_progress_bar.setValue(total)
        else:
            self.overall_progress_bar.setValue(current)
        self.status_label.setText(status)

    @Slot(float, float, str)
    def update_file_progress(self, current, total, name):
        self.file_progress_bar.setRange(0, int(total))
        self.file_progress_bar.setValue(int(current))