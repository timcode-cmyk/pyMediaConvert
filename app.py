"""
视频批处理 GUI
使用 Tkinter 构建的图形用户界面。
从 config.py 动态加载模式。
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import threading
import sys

# 确保 worker 和 config 可以在 (src) 目录之外被导入
# 如果 app.py 在项目根目录，src 和 worker 也在根目录
try:
    import config
    import worker
except ImportError:
    # 如果是从 src 目录运行，可能需要调整路径
    # 为简单起见，假设 app.py, cli.py, worker.py, config.py 都在根目录
    print("错误：无法导入 'config' 或 'worker'。")
    print("请确保 app.py, worker.py 和 config.py 在同一目录，或在 Python 路径中。")
    sys.exit(1)


class BatchProcessorApp:
    def __init__(self, master):
        self.master = master
        master.title("视频批处理工具")
        master.geometry("500x350")

        # --- 样式 ---
        self.style = ttk.Style()
        self.style.configure('TButton', padding=5, font=('Helvetica', 10))
        self.style.configure('TLabel', padding=2, font=('Helvetica', 10))
        self.style.configure('TFrame', padding=10)

        self.main_frame = ttk.Frame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 模式选择 ---
        self.mode_label = ttk.Label(self.main_frame, text="1. 选择处理模式:")
        self.mode_label.pack(anchor='w')

        self.mode_var = tk.StringVar(master)
        # 从 config.py 动态获取模式
        self.mode_options = {cfg['description']: mode_name for mode_name, cfg in config.MODES.items()}
        self.mode_menu = ttk.OptionMenu(self.main_frame, self.mode_var,
                                        list(self.mode_options.keys())[0], # 默认值
                                        *self.mode_options.keys()) # 显示描述
        self.mode_var.set(list(self.mode_options.keys())[0]) # 设置默认值
        self.mode_menu.pack(fill='x', pady=5)

        # --- 路径选择 ---
        self.input_dir = tk.StringVar(value=str(Path.cwd()))
        self.output_dir = tk.StringVar(value=str(Path.cwd() / "output"))

        self.input_label = ttk.Label(self.main_frame, text="2. 选择输入目录:")
        self.input_label.pack(anchor='w', pady=(10, 0))
        self.input_frame = ttk.Frame(self.main_frame)
        self.input_entry = ttk.Entry(self.input_frame, textvariable=self.input_dir, width=50)
        self.input_btn = ttk.Button(self.input_frame, text="浏览...", command=self.select_input_dir)
        self.input_entry.pack(side=tk.LEFT, fill='x', expand=True)
        self.input_btn.pack(side=tk.RIGHT, padx=(5, 0))
        self.input_frame.pack(fill='x')

        self.output_label = ttk.Label(self.main_frame, text="3. 选择输出目录:")
        self.output_label.pack(anchor='w', pady=(10, 0))
        self.output_frame = ttk.Frame(self.main_frame)
        self.output_entry = ttk.Entry(self.output_frame, textvariable=self.output_dir, width=50)
        self.output_btn = ttk.Button(self.output_frame, text="浏览...", command=self.select_output_dir)
        self.output_entry.pack(side=tk.LEFT, fill='x', expand=True)
        self.output_btn.pack(side=tk.RIGHT, padx=(5, 0))
        self.output_frame.pack(fill='x')

        # --- 运行按钮和状态 ---
        self.run_button = ttk.Button(self.main_frame, text="开始处理", command=self.start_processing)
        self.run_button.pack(pady=20)

        self.status_var = tk.StringVar(value="准备就绪")
        self.status_label = ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor='w')
        self.status_label.pack(fill='x', side=tk.BOTTOM, ipady=5)

        # --- 线程 ---
        self.processing_thread = None
        self.stop_event = threading.Event() # 用于未来可能的停止功能

    def select_input_dir(self):
        dir_path = filedialog.askdirectory(title="选择输入目录", initialdir=self.input_dir.get())
        if dir_path:
            self.input_dir.set(dir_path)

    def select_output_dir(self):
        dir_path = filedialog.askdirectory(title="选择输出目录", initialdir=self.output_dir.get())
        if dir_path:
            self.output_dir.set(dir_path)

    def start_processing(self):
        if self.processing_thread and self.processing_thread.is_alive():
            messagebox.showwarning("正在处理", "已经在处理中，请稍候。")
            return

        # 1. 获取参数
        selected_description = self.mode_var.get()
        mode_name = self.mode_options[selected_description]
        mode_config = config.MODES[mode_name]

        in_dir = Path(self.input_dir.get())
        out_dir = Path(self.output_dir.get())

        if not in_dir.is_dir():
            messagebox.showerror("错误", f"输入目录未找到: {in_dir}")
            return

        # 2. 准备 GUI 状态
        self.run_button.config(state=tk.DISABLED, text="处理中...")
        self.status_var.set(f"开始处理模式: {mode_name}...")
        self.master.update_idletasks() # 强制更新界面

        # 3. 启动后台线程
        self.processing_thread = threading.Thread(
            target=self.run_processing_task,
            args=(mode_config, in_dir, out_dir)
        )
        self.processing_thread.start()

    def run_processing_task(self, mode_config, in_dir, out_dir):
        """在后台线程中运行的实际处理任务"""
        try:
            # 实例化转换器
            ConverterClass = mode_config['class']
            params = mode_config.get('params', {})
            support_exts = mode_config.get('support_exts')
            output_suffix = mode_config.get('output_suffix')

            converter = ConverterClass(
                params=params,
                support_exts=support_exts,
                output_suffix=output_suffix
            )

            # 运行 (tqdm 的输出会打印到启动 app.py 的控制台)
            converter.run(in_dir, out_dir)

            # 成功
            # (重要) 必须在主线程中更新 GUI
            self.master.after(0, self.on_processing_finished, None)

        except Exception as e:
            # 失败
            self.master.after(0, self.on_processing_finished, e)

    def on_processing_finished(self, error=None):
        """处理完成后在主线程中调用的回调"""
        self.run_button.config(state=tk.NORMAL, text="开始处理")

        if error:
            self.status_var.set("处理失败！")
            messagebox.showerror("处理失败", f"发生错误: \n{error}")
        else:
            self.status_var.set("处理完成！")
            messagebox.showinfo("完成", "所有文件处理完毕。")

if __name__ == "__main__":
    # (重要)
    # PyInstaller 在 Windows/macOS 上使用 'spawn' 启动多进程时
    # 需要这个 __name__ == "__main__" 保护
    root = tk.Tk()
    app = BatchProcessorApp(root)
    root.mainloop()