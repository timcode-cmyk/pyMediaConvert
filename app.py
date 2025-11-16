import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import threading
from pathlib import Path
import sys
import os 

# 导入自定义模块
try:
    from pyMediaConvert import worker
    from pyMediaConvert import config
    MODES = config.MODES
except ImportError as e:
    # 始终在控制台输出错误，但在 GUI 中使用 messagebox 报告
    messagebox.showerror("导入错误", f"无法找到 worker.py 或 config.py。请确保它们在同一目录下。错误: {e}")
    sys.exit(1)


# --- 进度监视器类 (ProgressMonitor) ---
class ProgressMonitor:
    """负责在非GUI线程中更新GUI进度条和状态信息"""
    def __init__(self, overall_bar, overall_text, file_bar, file_text, status_label):
        self.overall_bar = overall_bar
        self.overall_text = overall_text
        self.file_bar = file_bar
        self.file_text = file_text
        self.status_label = status_label
        self.root = overall_bar.winfo_toplevel() # 获取主窗口引用

    def update_overall_progress(self, current: int, total: int, message: str):
        """更新总进度条和文本"""
        percentage = (current / total) * 100 if total > 0 else 0
        self.root.after(0, lambda: [
            self.overall_bar.config(value=current, maximum=total),
            self.overall_text.set(f"总进度: {current}/{total} 文件 ({percentage:.1f}%)"),
            self.status_label.config(text=message)
        ])

    def update_file_progress(self, current_time: float, total_duration: float, file_name: str):
        """更新当前文件进度条和文本"""
        percentage = (current_time / total_duration) * 100 if total_duration > 0 else 0
        self.root.after(0, lambda: [
            self.file_bar.config(value=current_time, maximum=total_duration),
            self.file_text.set(f"🎬 {file_name}: {current_time:.1f}s / {total_duration:.1f}s ({percentage:.1f}%)")
        ])

    def write_message(self, message: str):
        """写入状态栏消息"""
        self.root.after(0, lambda: self.status_label.config(text=message))


# --- 主应用类 (App) ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("pyMediaConvert 批量转换工具")
        self.resizable(True, True) 

        # 状态变量
        self.input_path_var = tk.StringVar(value="")
        self.output_path_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value=list(MODES.keys())[0] if MODES else "")
        self.status_var = tk.StringVar(value="等待用户输入...")
        
        # 进度条变量
        self.overall_progress_text = tk.StringVar(value="总进度: 0/0 文件 (0.0%)")
        self.file_progress_text = tk.StringVar(value="当前文件: 0.0s / 0.0s (0.0%)")

        self.setup_style()
        self.create_widgets()

    def setup_style(self):
        """配置现代化的 Tkinter 样式，并尽量使用原生主题"""
        self.style = ttk.Style(self)
        
        # 尝试使用更现代、更接近系统原生的主题
        native_theme = 'clam'
        if sys.platform.startswith('win'):
            # Windows 上的 'vista' 和 'xpnative' 通常能更好地适应系统颜色
            native_theme = 'vista' if 'vista' in self.style.theme_names() else 'xpnative'
        elif sys.platform == 'darwin':
            # macOS 上的 'aqua' 几乎总是能适配系统亮色/深色模式
            native_theme = 'aqua' if 'aqua' in self.style.theme_names() else 'clam'
            
        self.style.theme_use(native_theme)
        
        # 基础样式配置 - 扁平化和字体
        self.font_name = 'Helvetica'
        self.style.configure(".", font=(self.font_name, 10))
        self.style.configure("TFrame", padding=10)
        
        # 针对启动按钮，定义一个使用系统强调色的风格 (在原生主题下，这通常会是蓝色/绿色)
        self.style.configure("Accent.TButton", font=(self.font_name, 10, 'bold'), borderwidth=1)
        # 尝试使用原生主题的映射，例如：Windows/macOS 下的按钮激活状态
        # 注意: 在不同的 ttk 主题下，foreground/background 的映射会自动遵循系统颜色
        
        # 确保窗口背景遵循主题
        self.config(bg=self.style.lookup('TFrame', 'background'))
        self.style.configure("TFrame", background=self.style.lookup('TFrame', 'background'))
        self.style.configure("TLabel", background=self.style.lookup('TFrame', 'background'))

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="15 15 15 15")
        main_frame.pack(fill='both', expand=True)

        # 配置 Grid 布局
        main_frame.columnconfigure(1, weight=1)

        # --- 顶部控制栏：模式选择 ---
        top_control_frame = ttk.Frame(main_frame)
        top_control_frame.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        top_control_frame.columnconfigure(1, weight=1)

        ttk.Label(top_control_frame, text="转换模式:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.mode_combobox = ttk.Combobox(top_control_frame, textvariable=self.mode_var, values=list(MODES.keys()), state="readonly")
        self.mode_combobox.grid(row=0, column=1, sticky="ew") # 占满剩余空间
        self.mode_combobox.bind('<<ComboboxSelected>>', self.show_mode_description)
        
        # 删除了主题切换按钮

        # --- 模式描述 (Mode Description) ---
        self.desc_label = ttk.Label(main_frame, text="", wraplength=700, font=(self.font_name, 10, 'italic'))
        self.desc_label.grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 10))
        self.show_mode_description()

        # --- 输入目录 (Input Directory) ---
        ttk.Label(main_frame, text="输入目录:").grid(row=2, column=0, sticky="w", pady=5)
        self.input_entry = ttk.Entry(main_frame, textvariable=self.input_path_var)
        self.input_entry.grid(row=2, column=1, sticky="ew", padx=10)
        self.input_entry.bind("<FocusOut>", self.update_output_path) 
        self.input_entry.bind("<Return>", self.update_output_path) 
        
        self.path_tip_label = ttk.Label(main_frame, text="(粘贴/输入路径 或 选择目录)")
        self.path_tip_label.grid(row=2, column=2, sticky="w", padx=5)

        ttk.Button(main_frame, text="选择目录", command=self.select_input_dir).grid(row=2, column=3, sticky="e")

        # --- 输出目录 (Output Directory) ---
        ttk.Label(main_frame, text="输出目录:").grid(row=3, column=0, sticky="w", pady=5)
        self.output_entry = ttk.Entry(main_frame, textvariable=self.output_path_var)
        self.output_entry.grid(row=3, column=1, sticky="ew", padx=10)
        self.output_entry.bind("<FocusOut>", lambda e: self.update_output_path(e, force=True))
        ttk.Button(main_frame, text="选择目录", command=self.select_output_dir).grid(row=3, column=3, sticky="e")

        # --- 启动按钮 (Start Button) ---
        # 使用 Accent.TButton 样式，让它尽可能接近系统的强调色
        self.start_button = ttk.Button(main_frame, text="🚀 开始转换", command=self.start_conversion, style="Accent.TButton")
        self.start_button.grid(row=4, column=0, columnspan=4, pady=20, sticky="ew")

        # --- 状态显示 (Status Label) ---
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, anchor="w", font=(self.font_name, 10, 'italic'), wraplength=750)
        self.status_label.grid(row=5, column=0, columnspan=4, sticky="ew", pady=5)

        # --- 进度条区域 ---
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=6, column=0, columnspan=4, sticky="ew", pady=10)
        progress_frame.columnconfigure(0, weight=1)

        # 1. 总进度条
        ttk.Label(progress_frame, textvariable=self.overall_progress_text).grid(row=0, column=0, sticky="w")
        self.overall_bar = ttk.Progressbar(progress_frame, orient='horizontal', mode='determinate')
        self.overall_bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # 2. 当前文件进度条
        ttk.Label(progress_frame, textvariable=self.file_progress_text).grid(row=2, column=0, sticky="w")
        self.file_bar = ttk.Progressbar(progress_frame, orient='horizontal', mode='determinate')
        self.file_bar.grid(row=3, column=0, sticky="ew")

        # 初始化 ProgressMonitor 并设置到 worker 模块
        self.monitor = ProgressMonitor(
            overall_bar=self.overall_bar, 
            overall_text=self.overall_progress_text,
            file_bar=self.file_bar, 
            file_text=self.file_progress_text,
            status_label=self.status_label
        )
        worker.GlobalProgressMonitor = self.monitor

    def show_mode_description(self, event=None):
        """显示当前选中模式的描述"""
        mode_key = self.mode_var.get()
        desc = MODES.get(mode_key, {}).get('description', '未找到描述。')
        self.desc_label.config(text=f"说明: {desc}")

    def select_input_dir(self):
        """打开文件对话框选择输入目录"""
        folder = filedialog.askdirectory(title="选择包含待处理文件的输入目录")
        if folder:
            self.input_path_var.set(folder)
            self.update_output_path()

    def select_output_dir(self):
        """打开文件对话框选择输出目录"""
        folder = filedialog.askdirectory(title="选择输出目录")
        if folder:
            self.output_path_var.set(folder)

    def update_output_path(self, event=None, force=False):
        """
        根据输入目录自动设置默认输出目录。
        默认输出目录：[输入目录]/output
        """
        input_dir_str = self.input_path_var.get().strip()
        current_output_dir = self.output_path_var.get().strip()

        if input_dir_str:
            # 清理路径：处理路径被拖入时可能带有的引号
            if input_dir_str.startswith('"') and input_dir_str.endswith('"'):
                input_dir_str = input_dir_str[1:-1]

            input_path = Path(input_dir_str)
            
            # 检查输入路径是否是有效目录
            if not input_path.is_dir():
                # 尝试修复，如果用户输入的是文件路径，我们取其父目录
                if input_path.is_file():
                    input_path = input_path.parent
                else:
                    self.status_var.set("警告: 输入路径无效，请确保它是目录路径。")
                    return

            # 如果输出目录为空, 或者我们被强制更新 (force=True), 或者输出目录是旧的自动生成目录，则更新
            default_output = input_path / "output"
            
            should_update = not current_output_dir or force or \
                            Path(current_output_dir) == Path(self.input_path_var.get().strip()) / "output"
                            
            if should_update:
                self.output_path_var.set(str(default_output))
                self.status_var.set(f"输出目录已自动设置为: {default_output}")
                
        elif not input_dir_str:
            self.output_path_var.set("")


    def start_conversion(self):
        """开始转换过程"""
        input_dir = self.input_path_var.get().strip()
        output_dir = self.output_path_var.get().strip()
        mode_key = self.mode_var.get()

        # 1. 验证输入
        if not all([input_dir, output_dir, mode_key]):
            messagebox.showerror("错误", "请确保已选择输入目录、输出目录和转换模式。")
            return
        
        # 再次确认输入目录存在
        if not Path(input_dir).is_dir():
            messagebox.showerror("错误", "输入目录无效或不存在。")
            return

        # 2. 禁用UI并更新状态
        self.start_button.config(state=tk.DISABLED, text="处理中...")
        self.status_var.set("正在初始化转换...")

        # 3. 在新线程中运行转换逻辑
        conversion_thread = threading.Thread(
            target=self._run_conversion_thread,
            args=(input_dir, output_dir, mode_key)
        )
        conversion_thread.start()

    def _run_conversion_thread(self, input_dir_str: str, output_dir_str: str, mode_key: str):
        """在单独的线程中执行转换器逻辑"""
        try:
            input_dir = Path(input_dir_str)
            output_dir = Path(output_dir_str)
            mode_config = MODES[mode_key]

            # 实例化转换器
            ConverterClass = mode_config['class']
            
            converter = ConverterClass(
                params=mode_config['params'],
                support_exts=mode_config.get('support_exts'),
                output_ext=mode_config.get('output_ext')
            )
            
            # 开始运行
            self.monitor.write_message(f"转换开始: 模式 '{mode_config['description']}'")
            converter.run(input_dir, output_dir)

            # 成功完成
            self.monitor.write_message(f"✅ 转换完成! 结果保存在: {output_dir}")

        except Exception as e:
            # 捕获所有线程内的异常并报告给主线程
            error_message = f"❌ 严重错误: {e}"
            self.monitor.write_message(error_message)
            self.after(0, lambda: messagebox.showerror("转换错误", error_message))
        
        finally:
            # 转换结束，恢复UI
            self.after(0, lambda: self.start_button.config(state=tk.NORMAL, text="🚀 开始转换", style="Accent.TButton"))


if __name__ == "__main__":
    app = App()
    # 初始化进度条为 0
    app.overall_bar.config(value=0, maximum=1)
    app.file_bar.config(value=0, maximum=1)
    app.mainloop()