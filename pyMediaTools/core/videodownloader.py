"""
视频下载器模块
"""
import os
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import QThread, Signal
import yt_dlp
from ..utils import get_ffmpeg_exe

logger = logging.getLogger(__name__)

class YtDlpInfoWorker(QThread):
    """Worker to parse video/playlist info"""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'dump_single_json': True,
            'no_warnings': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))

class YtDlpDownloadWorker(QThread):
    """Download Worker"""
    # Signal now includes 'ui_index' to update specific table row
    progress = Signal(dict)
    finished = Signal()
    error = Signal(str)
    
    def __init__(self, download_items, options, output_dir):
        """
        download_items: List of dicts [{'url': url, 'ui_index': int, 'title': str}]
        """
        super().__init__()
        self.items = download_items
        self.options = options
        self.output_dir = output_dir
        self._is_running = True
        self.downloaded_files = []
        
        self.total_files = len(download_items) if download_items else 1
        self.current_item_index = 0
        self.current_ui_index = -1
        # concurrency controls how many downloads run in parallel (default 4)
        try:
            self.concurrency = int(self.options.get('concurrency', 4))
        except Exception:
            self.concurrency = 4
        if self.concurrency < 1:
            self.concurrency = 1


    def _format_speed(self, bps: float) -> str:
        """Format bytes-per-second into a human binary unit without '/s', e.g. '1.35MiB'."""
        try:
            if bps is None:
                return '-'
            b = float(bps)
        except Exception:
            return '-'

        units = ["B", "KiB", "MiB", "GiB", "TiB"]
        idx = 0
        while b >= 1024 and idx + 1 < len(units):
            b /= 1024.0
            idx += 1
        return f"{b:.2f}{units[idx]}"

    def _parse_human_speed(self, s: str) -> float | None:
        """解析“1.35MiB/s”或“512.3KiB/s”等字符串，并以浮点数或 None 的形式返回字节/秒。"""
        if not s:
            return None
        try:
            s = s.strip()
            # 删除尾随的“/s”或“/sec”等。
            # s = re.sub(r'/s(ec(ond)?)?$', '', s, flags=re.IGNORECASE).strip()
            # remove ANSI codes
            s = re.sub(r'\x1b\[[0-9;]*m', '', s)
            m = re.match(r'([0-9,.]+)\s*([A-Za-z]+)', s)
            if not m:
                return None
            num = float(m.group(1).replace(',', ''))
            unit = m.group(2).upper()
            # Normalize some common unit variants
            multipliers = {
                'B': 1,
                'KB': 1000,
                'KIB': 1024,
                'MB': 1000**2,
                'MIB': 1024**2,
                'GB': 1000**3,
                'GIB': 1024**3,
            }
            mul = multipliers.get(unit)
            if mul is None:
                # try last char 'B' removal
                if unit.endswith('B') and len(unit) > 1:
                    unit2 = unit[0:-1]
                    mul = multipliers.get(unit2 + 'B')
            if mul is None:
                return None
            return num * mul
        except Exception:
            return None

    def run(self):
        # 1. FFmpeg Check
        ffmpeg_path_str = get_ffmpeg_exe()
        # Strictly check if the file exists
        has_ffmpeg = ffmpeg_path_str and os.path.exists(ffmpeg_path_str)
        
        ffmpeg_loc = ffmpeg_path_str if has_ffmpeg else None

        # 2. Base Options
        ydl_opts = {
            'ffmpeg_location': ffmpeg_loc,
            'prefer_ffmpeg': True,
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            # progress_hooks are attached per-item when running in parallel via _progress_hook_factory
            'progress_hooks': [],
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            # 'cookiesfrombrowser': ('chrome',) # cookies选择问题
        }

        is_audio_only = self.options.get('audio_only', False)
        target_ext = self.options.get('ext', 'mp4')
        quality = (self.options.get('quality') or 'best')

        # 3. Format Strategy (Fixing No Audio)
        if is_audio_only:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': target_ext,
                'preferredquality': '192',
            }]
        else:
            # If NO FFmpeg, force 'best' (single file with audio/video interleaved).
            # 'bestvideo+bestaudio' WILL FAIL to merge without ffmpeg, resulting in no audio.
            if not has_ffmpeg:
                print("FFmpeg not found. Forcing 'best' format to ensure audio.")
                ydl_opts['format'] = 'best'
            else:
                # Standard high quality logic
                if str(quality).lower() == 'best':
                    ydl_opts['format'] = 'bestvideo+bestaudio/best'
                else:
                    try:
                        h = int(str(quality).lower().replace('p', ''))
                        ydl_opts['format'] = f'bestvideo[height<={h}]+bestaudio/best[height<={h}]'
                    except:
                        ydl_opts['format'] = 'bestvideo+bestaudio/best'
                
                if str(target_ext).lower() in ['mp4', 'mkv', 'webm', 'mov']:
                    ydl_opts['merge_output_format'] = target_ext.lower()

        # 4. Subtitles Strategy
        if self.options.get('subtitles', False):
            ydl_opts['writesubtitles'] = True
            # Default to auto or specified lang. 'all' ensures we get something.
            lang = self.options.get('sub_lang', 'en')
            ydl_opts['subtitleslangs'] = [lang, 'en', 'zh-Hans'] 
            
            # Only try to embed if we have FFmpeg. Otherwise just download the file.
            if has_ffmpeg and not is_audio_only:
                ydl_opts.setdefault('postprocessors', []).append({'key': 'FFmpegEmbedSubtitle'})

        # 5. Execution Loop - run downloads in parallel using ThreadPoolExecutor
        try:
            futures = {}
            executor = ThreadPoolExecutor(max_workers=self.concurrency)

            # submit tasks
            for i, item in enumerate(self.items):
                if not self._is_running:
                    break

                ui_index = item['ui_index']
                url = item['url']
                title = item.get('title', 'Unknown')
                # per-item starting signal
                self.progress.emit({
                    'overall_percent': (i / self.total_files) * 100,
                    'current_percent': 0,
                    'status': f"准备下载: {title}",
                    'ui_index': ui_index,
                    'file_complete': False
                })

                # prepare per-item options and bind a progress hook for this item
                item_opts = dict(ydl_opts)
                item_opts['progress_hooks'] = [self._progress_hook_factory(ui_index, i)]

                future = executor.submit(self._download_one, url, item_opts, i, ui_index, title)
                futures[future] = (i, ui_index, title)

            # wait for completions
            completed_count = 0
            for future in as_completed(futures):
                i, ui_index, title = futures[future]
                try:
                    result = future.result()
                    completed_count += 1
                    self.downloaded_files.append(result or title)

                    self.progress.emit({
                        'overall_percent': (completed_count / self.total_files) * 100,
                        'current_percent': 100,
                        'status': f"完成: {title}",
                        'ui_index': ui_index,
                        'file_complete': True
                    })
                except Exception as e:
                    if "Stopped by user" in str(e):
                        logger.info("Download stopped by user.")
                    else:
                        # emit a per-file failure
                        self.progress.emit({
                            'overall_percent': (completed_count / self.total_files) * 100,
                            'current_percent': 0,
                            'status': f"失败: {title}",
                            'ui_index': ui_index,
                            'file_complete': False
                        })
                        self.error.emit(f"下载失败 ({title}): {str(e)}")

            executor.shutdown(wait=False, cancel_futures=True)

        except Exception as e:
            # Handle user stop gracefully
            if "Stopped by user" in str(e):
                logger.info("Download stopped by user.")
            else:
                self.error.emit(f"下载流程异常: {str(e)}")
                return

        if self._is_running:
            self.finished.emit()

    def _progress_hook_factory(self, ui_index, item_idx):
        """Return a per-item hook that binds ui_index and item_idx for progress reporting."""
        def hook(d):
            # Delegate to the shared handler
            return self._handle_progress(d, ui_index, item_idx)
        return hook

    def _handle_progress(self, d, ui_index, item_idx):
        if not self._is_running:
            raise Exception("Stopped by user")

        status = d.get('status')
        if status == 'downloading':
            percent = 0
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes')
            if total and downloaded:
                try:
                    percent = (float(downloaded) / float(total)) * 100
                except Exception:
                    percent = 0
            else:
                p_str = d.get('_percent_str', '').replace('%', '')
                p_str = re.sub(r'\x1b\[[0-9;]*m', '', p_str)
                try:
                    percent = float(p_str)
                except Exception:
                    percent = 0

            # Calculate overall progress
            overall = ((item_idx + (percent / 100.0)) / self.total_files) * 100
            filename = os.path.basename(d.get('filename', 'Unknown'))

            # Normalize speed into a short value like '1.35MiB' (no '/s')
            speed_val = None
            sp_numeric = d.get('speed')
            if sp_numeric:
                try:
                    speed_val = self._format_speed(float(sp_numeric))
                except Exception:
                    speed_val = None
            if speed_val is None:
                speed_str = d.get('_speed_str', '').strip()
                parsed = self._parse_human_speed(speed_str)
                if parsed is not None:
                    speed_val = self._format_speed(parsed)
            if speed_val is None or speed_val == '-':
                speed_val = '-'

            self.progress.emit({
                'overall_percent': overall,
                'current_percent': percent,
                'status': filename,
                'speed': speed_val,
                'eta': d.get('_eta_str', '').strip(),
                'ui_index': ui_index,
                'file_complete': False
            })
        elif status == 'finished':
            fname = d.get('filename')
            if fname:
                self.downloaded_files.append(fname)

    def stop(self):
        """Set flag to stop download"""
        self._is_running = False

    def _download_one(self, url, opts, item_idx, ui_index, title):
        """Run a single yt-dlp download using provided options. Returns title/filename on success."""
        if not self._is_running:
            raise Exception("Stopped by user")
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            return title
        except Exception as e:
            # propagate exception to caller so main loop can emit errors
            raise e