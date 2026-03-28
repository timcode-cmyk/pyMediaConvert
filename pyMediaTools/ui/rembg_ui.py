# import os
# from pathlib import Path
# from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
#                                QLineEdit, QPushButton, QComboBox, QProgressBar, QMessageBox, 
#                                QFileDialog, QSizePolicy, QGroupBox, QRadioButton, QButtonGroup, QColorDialog)
# from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
# from PySide6.QtGui import QFont, QColor

# from ..core.rembg import RembgProcessor
# from .styles import apply_common_style
# from .media_tools_ui import DropLineEdit, ProgressMonitor
# from pyMediaTools import get_logger

# logger = get_logger(__name__)

# class RembgWorker(QObject):
#     finished = Signal(bool, str)

#     def __init__(self, input_path, output_dir, options, monitor, parent=None):
#         super().__init__(parent)
#         self.input_path = Path(input_path)
#         self.output_dir = Path(output_dir)
#         self.options = options
#         self.monitor = monitor

#     @Slot()
#     def run(self):
#         is_successful = True
#         error_msg = ""
#         try:
#             processor = RembgProcessor(
#                 model_name=self.options.get('model', 'u2net'),
#                 bgcolor=self.options.get('bgcolor'),
#                 monitor=self.monitor
#             )
            
#             files = []
#             if self.input_path.is_file():
#                 files.append(self.input_path)
#             elif self.input_path.is_dir():
#                 # Supported extensions
#                 extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.mp4', '.mov', '.avi', '.mkv', '.webm'}
#                 for p in self.input_path.iterdir():
#                     if p.is_file() and p.suffix.lower() in extensions:
#                         files.append(p)
            
#             files = sorted(files)
#             total = len(files)
            
#             if total == 0:
#                 raise ValueError("未找到支持的文件 (图片或视频)")
            
#             for idx, f in enumerate(files):
#                 if self.monitor.check_stop_flag():
#                     is_successful = False
#                     break
                
#                 self.monitor.update_overall_progress(idx, total, f"正在处理 ({idx+1}/{total}): {f.name}")
                
#                 # Determine output filename
#                 # If bg is transparent and input is jpg, force png extension
#                 if f.suffix.lower() in ['.jpg', '.jpeg'] and self.options.get('bgcolor') is None:
#                     out_name = f.stem + "_rembg.png"
#                 else:
#                     out_name = f.stem + "_rembg" + f.suffix
                
#                 out_file = self.output_dir / out_name
                
#                 processor.process_file(f, out_file)
            
#             if is_successful:
#                 self.monitor.update_overall_progress(total, total, "处理完成")

#         except Exception as e:
#             import traceback
#             error_msg = traceback.format_exc()
            
#             # User-friendly error for missing rembg or onnxruntime
#             err_str = str(e).lower()
#             if "rembg" in err_str or "onnxruntime" in err_str or "module not found" in err_str:
#                 error_msg = "无法初始化 AI 抠图引擎。\n\n可能原因：\n1. 缺少必要组件 (rembg/onnxruntime)\n2. 硬件加速驱动不兼容 (CUDA/Metal)\n3. 模型下载失败\n\n请尝试重新安装或检查网络连接。"
            
#             logger.exception(f"RembgWorker exception: {e}")
#             is_successful = False
#         finally:
#             self.finished.emit(is_successful, error_msg)


# class RembgWidget(QWidget):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.is_processing = False
#         self.worker_thread = None
#         self.monitor = None
#         self.custom_color = (0, 255, 0, 255) # Default Green
        
#         self.init_ui()
#         self.apply_styles()

#     def apply_styles(self):
#         apply_common_style(self)

#     def init_ui(self):
#         layout = QVBoxLayout(self)
#         layout.setContentsMargins(20, 20, 20, 20)
#         layout.setSpacing(15)

#         # Title
#         title = QLabel("AI 智能抠图 / 绿幕合成")
#         title.setFont(QFont("Segoe UI", 20, QFont.Bold))
#         layout.addWidget(title)

#         # 1. Path Input
#         path_group = QGroupBox("输入与输出")
#         path_layout = QVBoxLayout(path_group)
        
#         # Input
#         in_layout = QHBoxLayout()
#         self.input_edit = DropLineEdit()
#         self.input_edit.setPlaceholderText("📂 拖放图片/视频文件或文件夹到此处")
#         self.input_edit.setMinimumHeight(50)
#         self.input_edit.pathDropped.connect(self.update_output_path)
#         self.input_edit.textChanged.connect(self.update_output_path)
        
#         btn_in = QPushButton("浏览...")
#         btn_in.clicked.connect(self.browse_input)
        
#         in_layout.addWidget(self.input_edit)
#         in_layout.addWidget(btn_in)
#         path_layout.addWidget(QLabel("输入源:"))
#         path_layout.addLayout(in_layout)
        
#         # Output
#         out_layout = QHBoxLayout()
#         self.output_edit = QLineEdit()
#         self.output_edit.setPlaceholderText("输出目录")
#         btn_out = QPushButton("浏览...")
#         btn_out.clicked.connect(self.browse_output)
        
#         out_layout.addWidget(self.output_edit)
#         out_layout.addWidget(btn_out)
#         path_layout.addWidget(QLabel("输出目录:"))
#         path_layout.addLayout(out_layout)
        
#         layout.addWidget(path_group)

#         # 2. Settings
#         settings_group = QGroupBox("参数设置")
#         settings_layout = QVBoxLayout(settings_group)
        
#         # Model Selection
#         model_layout = QHBoxLayout()
#         model_layout.addWidget(QLabel("模型选择:"))
#         self.combo_model = QComboBox()
#         self.combo_model.addItems(["u2net (标准)", "u2netp (快速)", "u2net_human_seg (人像)", "isnet-general-use (通用)"])
#         # Map display text to internal model name
#         self.model_map = {
#             "u2net (标准)": "u2net",
#             "u2netp (快速)": "u2netp",
#             "u2net_human_seg (人像)": "u2net_human_seg",
#             "isnet-general-use (通用)": "isnet-general-use"
#         }
#         model_layout.addWidget(self.combo_model, 1)
#         settings_layout.addLayout(model_layout)
        
#         # Background Selection
#         bg_layout = QHBoxLayout()
#         bg_layout.addWidget(QLabel("背景处理:"))
        
#         self.bg_group = QButtonGroup(self)
#         self.rb_transparent = QRadioButton("透明 (仅图片)")
#         self.rb_green = QRadioButton("绿幕")
#         self.rb_blue = QRadioButton("蓝幕")
#         self.rb_custom = QRadioButton("自定义颜色")
        
#         self.rb_green.setChecked(True) # Default
        
#         self.bg_group.addButton(self.rb_transparent)
#         self.bg_group.addButton(self.rb_green)
#         self.bg_group.addButton(self.rb_blue)
#         self.bg_group.addButton(self.rb_custom)
        
#         bg_layout.addWidget(self.rb_transparent)
#         bg_layout.addWidget(self.rb_green)
#         bg_layout.addWidget(self.rb_blue)
#         bg_layout.addWidget(self.rb_custom)
        
#         self.btn_color_pick = QPushButton()
#         self.btn_color_pick.setFixedWidth(50)
#         self.btn_color_pick.setStyleSheet(f"background-color: #00FF00;")
#         self.btn_color_pick.clicked.connect(self.pick_color)
#         self.btn_color_pick.setEnabled(False) # Enable only when custom is checked
        
#         self.rb_custom.toggled.connect(self.btn_color_pick.setEnabled)
#         # Update color button when preset selected (visual feedback)
#         self.rb_green.toggled.connect(lambda c: c and self.update_color_preview((0, 255, 0, 255)))
#         self.rb_blue.toggled.connect(lambda c: c and self.update_color_preview((0, 0, 255, 255)))
#         self.rb_transparent.toggled.connect(lambda c: c and self.update_color_preview(None))
#         self.rb_custom.toggled.connect(lambda c: c and self.update_color_preview(self.custom_color))

#         bg_layout.addWidget(self.btn_color_pick)
#         bg_layout.addStretch()
        
#         settings_layout.addLayout(bg_layout)
        
#         layout.addWidget(settings_group)

#         # 3. Progress & Control
#         prog_group = QGroupBox("状态与控制")
#         prog_layout = QVBoxLayout(prog_group)
        
#         self.status_label = QLabel("等待开始...")
#         self.status_label.setObjectName("StatusLabel")
        
#         self.overall_pbar = QProgressBar()
#         self.file_pbar = QProgressBar()
        
#         prog_layout.addWidget(QLabel("总进度:"))
#         prog_layout.addWidget(self.overall_pbar)
#         prog_layout.addWidget(QLabel("当前文件进度:"))
#         prog_layout.addWidget(self.file_pbar)
#         prog_layout.addWidget(self.status_label)
        
#         layout.addWidget(prog_group)

#         # Button
#         self.btn_start = QPushButton("🚀 开始处理")
#         self.btn_start.setObjectName("StartStopButton")
#         self.btn_start.setProperty('converting', 'false')
#         self.btn_start.setMinimumHeight(45)
#         self.btn_start.clicked.connect(self.toggle_process)
#         layout.addWidget(self.btn_start)

#     def browse_input(self):
#         path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "Media Files (*.png *.jpg *.jpeg *.mp4 *.mov *.avi *.mkv);;All Files (*)")
#         if not path:
#             path = QFileDialog.getExistingDirectory(self, "选择文件夹")
#         if path:
#             self.input_edit.setText(path)

#     def browse_output(self):
#         path = QFileDialog.getExistingDirectory(self, "选择输出目录")
#         if path:
#             self.output_edit.setText(path)

#     def update_output_path(self, text):
#         if text and os.path.exists(text):
#             p = Path(text)
#             if p.is_file():
#                 default_out = p.parent / "REMBG_OUTPUT"
#             else:
#                 default_out = p / "REMBG_OUTPUT"
#             self.output_edit.setText(str(default_out))

#     def pick_color(self):
#         c = QColorDialog.getColor(initial=QColor(*self.custom_color), parent=self, title="选择背景色")
#         if c.isValid():
#             self.custom_color = (c.red(), c.green(), c.blue(), 255)
#             self.update_color_preview(self.custom_color)

#     def update_color_preview(self, color_tuple):
#         if color_tuple is None:
#             # Transparent representation: white
#             self.btn_color_pick.setStyleSheet("background-color: white; border: 1px dashed gray;") 
#             return
        
#         r, g, b, a = color_tuple
#         self.btn_color_pick.setStyleSheet(f"background-color: rgb({r},{g},{b}); border: 1px solid gray;")

#     def get_bg_color(self):
#         if self.rb_transparent.isChecked():
#             return None
#         if self.rb_green.isChecked():
#             return (0, 255, 0, 255)
#         if self.rb_blue.isChecked():
#             return (0, 0, 255, 255)
#         if self.rb_custom.isChecked():
#             return self.custom_color
#         return (0, 255, 0, 255)

#     def toggle_process(self):
#         if self.is_processing:
#             self.stop_process()
#         else:
#             self.start_process()

#     def start_process(self):
#         input_path = self.input_edit.text().strip()
#         output_dir = self.output_edit.text().strip()
        
#         if not input_path or not os.path.exists(input_path):
#             QMessageBox.warning(self, "错误", "请输入有效的输入路径")
#             return
        
#         if not output_dir:
#             QMessageBox.warning(self, "错误", "请设置输出目录")
#             return
            
#         os.makedirs(output_dir, exist_ok=True)
        
#         options = {
#             'model': self.model_map.get(self.combo_model.currentText(), 'u2net'),
#             'bgcolor': self.get_bg_color()
#         }
        
#         self.is_processing = True
#         self.btn_start.setText("🛑 停止处理")
#         self.btn_start.setProperty('converting', 'true')
#         self.btn_start.style().polish(self.btn_start)
        
#         self.monitor = ProgressMonitor()
#         self.monitor.overall_progress.connect(self.update_overall)
#         self.monitor.file_progress.connect(self.update_file)
        
#         self.worker = RembgWorker(input_path, output_dir, options, self.monitor)
#         self.worker_thread = QThread()
#         self.worker.moveToThread(self.worker_thread)
#         self.worker_thread.started.connect(self.worker.run)
#         self.worker.finished.connect(self.on_finished)
#         self.worker.finished.connect(self.worker_thread.quit)
#         self.worker.finished.connect(self.worker.deleteLater)
#         self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        
#         self.worker_thread.start()

#     def stop_process(self):
#         if self.monitor:
#             self.monitor.request_stop()
#             self.status_label.setText("正在请求停止...")
#             self.btn_start.setEnabled(False)

#     @Slot(int, int, str)
#     def update_overall(self, cur, total, msg):
#         self.overall_pbar.setRange(0, total)
#         self.overall_pbar.setValue(cur)
#         self.status_label.setText(msg)

#     @Slot(float, float, str)
#     def update_file(self, cur, total, msg):
#         self.file_pbar.setRange(0, int(total))
#         self.file_pbar.setValue(int(cur))

#     @Slot(bool, str)
#     def on_finished(self, success, err):
#         self.is_processing = False
#         self.btn_start.setEnabled(True)
#         self.btn_start.setText("🚀 开始处理")
#         self.btn_start.setProperty('converting', 'false')
#         self.btn_start.style().polish(self.btn_start)
        
#         if success:
#             self.status_label.setText("处理完成")
#             self.overall_pbar.setValue(self.overall_pbar.maximum())
#             QMessageBox.information(self, "完成", "处理任务已完成")
#         elif self.monitor and self.monitor.check_stop_flag():
#             self.status_label.setText("已停止")
#         elif err:
#             self.status_label.setText("发生错误")
#             QMessageBox.critical(self, "错误", f"处理过程中出错: {err}")