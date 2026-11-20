"""
视频下载器模块
"""
import os
import logging
import re
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import QThread, Signal
import yt_dlp
from ..utils import get_ffmpeg_exe, is_binary_executable

logger = logging.getLogger(__name__)

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")

# 支持的标题/元数据语言选项 (显示名称, yt-dlp/YouTube 语言代码)
METADATA_LANGUAGE_OPTIONS = [
    ("简体中文 (zh-CN)", "zh-CN"),
    ("繁體中文 (zh-TW)", "zh-TW"),
    ("繁體中文-香港 (zh-HK)", "zh-HK"),
    ("English (en)", "en"),
    ("日本語 (ja)", "ja"),
    ("한국어 (ko)", "ko"),
    ("Español (es)", "es"),
    ("Français (fr)", "fr"),
    ("Deutsch (de)", "de"),
    ("Русский (ru)", "ru"),
    ("默认 (不强制)", ""),
]


def strip_ansi(text: str) -> str:
    """移除终端 ANSI 颜色控制字符。"""
    if not text:
        return ""
    return ANSI_ESCAPE_RE.sub("", str(text))


def is_youtube_radio_mix_url(url: str) -> bool:
    """检测链接是否为 YouTube 自动生成的无限电台/合辑 (Mix, list=RD... 或 start_radio=1)。"""
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        list_id = (qs.get("list") or [""])[0]
        start_radio = (qs.get("start_radio") or [""])[0]
        if start_radio == "1" or list_id.startswith("RD"):
            return True
    except Exception:
        pass
    return False


def build_locale_ydl_opts(meta_lang: str | None) -> dict:
    """构建语言本地化参数（使 YouTube 等平台返回指定语言的标题与元数据）。"""
    lang = (meta_lang or "").strip()
    if not lang:
        return {}

    accept_lang = f"{lang},zh;q=0.9,en;q=0.8" if not lang.startswith("en") else "en-US,en;q=0.9"
    return {
        "extractor_args": {
            "youtube": {
                "lang": [lang],
            }
        },
        "http_headers": {
            "Accept-Language": accept_lang,
        },
    }


class YtDlpLogger:
    def debug(self, msg):
        if msg.startswith("[debug] "):
            return
        self.info(msg)

    def info(self, msg):
        clean = strip_ansi(msg)
        # 过滤解析大播放列表时的逐条刷屏日志，避免大量同步磁盘 I/O 拖慢解析
        if clean.startswith("[download] Downloading item "):
            return
        logger.info(f"[yt-dlp] {clean}")

    def warning(self, msg):
        logger.warning(f"[yt-dlp] {strip_ansi(msg)}")

    def error(self, msg):
        logger.error(f"[yt-dlp] {strip_ansi(msg)}")


class YtDlpInfoWorker(QThread):
    """Worker to parse video/playlist info"""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, url: str, options: dict | None = None):
        super().__init__()
        self.url = url
        self.options = options or {}

    def run(self):
        meta_lang = self.options.get("meta_lang", "zh-CN")
        noplaylist = bool(self.options.get("noplaylist", False))
        playlist_limit = int(self.options.get("playlist_limit", 50) or 0)

        ydl_opts = {
            "quiet": True,
            "extract_flat": "in_playlist",
            "no_warnings": True,
            "color": "no_color",
            "logger": YtDlpLogger(),
            "windowsfilenames": True,
        }

        if noplaylist:
            ydl_opts["noplaylist"] = True
        elif playlist_limit > 0:
            ydl_opts["playlistend"] = playlist_limit

        ydl_opts.update(build_locale_ydl_opts(meta_lang))

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                if isinstance(info, dict) and "entries" in info:
                    entries = [e for e in info["entries"] if e is not None]
                    if playlist_limit > 0:
                        entries = entries[:playlist_limit]
                    info["entries"] = entries
                self.finished.emit(info or {})
        except Exception as e:
            self.error.emit(strip_ansi(str(e)))


class YtDlpDownloadWorker(QThread):
    """Download Worker"""
    progress = Signal(dict)
    finished = Signal()
    error = Signal(str)
    
    def __init__(self, download_items, options, output_dir):
        """
        download_items: List of dicts [{'url': url, 'ui_index': int, 'title': str}]
        """
        super().__init__()
        self.items = download_items
        self.options = options or {}
        self.output_dir = output_dir
        self._is_running = True
        self.downloaded_files = []
        
        self.total_files = len(download_items) if download_items else 1
        self.current_item_index = 0
        self.current_ui_index = -1
        try:
            self.concurrency = int(self.options.get("concurrency", 4))
        except Exception:
            self.concurrency = 4
        if self.concurrency < 1:
            self.concurrency = 1

    def _format_speed(self, bps: float) -> str:
        """Format bytes-per-second into a human binary unit without '/s', e.g. '1.35MiB'."""
        try:
            if bps is None:
                return "-"
            b = float(bps)
        except Exception:
            return "-"

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
            s = strip_ansi(s.strip())
            m = re.match(r"([0-9,.]+)\s*([A-Za-z]+)", s)
            if not m:
                return None
            num = float(m.group(1).replace(",", ""))
            unit = m.group(2).upper()
            multipliers = {
                "B": 1,
                "KB": 1000,
                "KIB": 1024,
                "MB": 1000**2,
                "MIB": 1024**2,
                "GB": 1000**3,
                "GIB": 1024**3,
            }
            mul = multipliers.get(unit)
            if mul is None:
                if unit.endswith("B") and len(unit) > 1:
                    unit2 = unit[0:-1]
                    mul = multipliers.get(unit2 + "B")
            if mul is None:
                return None
            return num * mul
        except Exception:
            return None

    def run(self):
        # 1. 严格检测 FFmpeg 是否真实存在且可在当前 CPU 架构上执行
        ffmpeg_path_str = get_ffmpeg_exe()
        has_ffmpeg = is_binary_executable(ffmpeg_path_str)
        ffmpeg_loc = ffmpeg_path_str if has_ffmpeg else None

        if not has_ffmpeg:
            logger.warning(
                f"FFmpeg 不可用或架构不兼容 ({ffmpeg_path_str})，将回退至免合并单文件流模式下载。"
            )

        # 2. Base Options
        ydl_opts = {
            "prefer_ffmpeg": True,
            "outtmpl": os.path.join(self.output_dir, "%(title)s [%(id)s].%(ext)s"),
            "progress_hooks": [],
            "quiet": False,
            "no_warnings": False,
            "ignoreerrors": False,
            "color": "no_color",
            "noplaylist": True,
            "logger": YtDlpLogger(),
            "windowsfilenames": True,
            "trim_file_name": 100,
        }
        if ffmpeg_loc:
            ydl_opts["ffmpeg_location"] = ffmpeg_loc

        meta_lang = self.options.get("meta_lang", "zh-CN")
        ydl_opts.update(build_locale_ydl_opts(meta_lang))

        is_audio_only = self.options.get("audio_only", False)
        target_ext = self.options.get("ext", "mp4")
        quality = self.options.get("quality") or "best"

        # 3. Format Strategy
        if is_audio_only:
            ydl_opts["format"] = "bestaudio/best"
            if has_ffmpeg:
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": target_ext,
                    "preferredquality": "192",
                }]
        else:
            if not has_ffmpeg:
                # 无可用 FFmpeg 时，禁止请求需要合并的双流 (bestvideo+bestaudio)，只选择预合并的单文件流
                if str(quality).lower() == "best":
                    ydl_opts["format"] = f"best[ext={target_ext}]/best/b"
                else:
                    try:
                        h = int(str(quality).lower().replace("p", ""))
                        ydl_opts["format"] = (
                            f"best[height<={h}][ext={target_ext}]/best[height<={h}]/best/b"
                        )
                    except ValueError:
                        ydl_opts["format"] = f"best[ext={target_ext}]/best/b"
            else:
                if str(quality).lower() == "best":
                    ydl_opts["format"] = "bestvideo+bestaudio/best"
                else:
                    try:
                        h = int(str(quality).lower().replace("p", ""))
                        ydl_opts["format"] = (
                            f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
                        )
                    except ValueError:
                        ydl_opts["format"] = "bestvideo+bestaudio/best"
                
                if str(target_ext).lower() in ["mp4", "mkv", "webm", "mov"]:
                    ydl_opts["merge_output_format"] = target_ext.lower()

        # 4. Subtitles Strategy
        if self.options.get("subtitles", False):
            ydl_opts["writesubtitles"] = True
            lang = self.options.get("sub_lang", "en")
            ydl_opts["subtitleslangs"] = [lang, "en", "zh-Hans"]
            
            if has_ffmpeg and not is_audio_only:
                ydl_opts.setdefault("postprocessors", []).append({"key": "FFmpegEmbedSubtitle"})

        # 5. Execution Loop
        try:
            futures = {}
            executor = ThreadPoolExecutor(max_workers=self.concurrency)

            for i, item in enumerate(self.items):
                if not self._is_running:
                    break

                ui_index = item["ui_index"]
                url = item["url"]
                title = item.get("title", "Unknown")
                self.progress.emit({
                    "overall_percent": (i / self.total_files) * 100,
                    "current_percent": 0,
                    "status": f"准备下载: {title}",
                    "ui_index": ui_index,
                    "file_complete": False,
                })

                item_opts = dict(ydl_opts)
                item_opts["progress_hooks"] = [self._progress_hook_factory(ui_index, i)]

                future = executor.submit(self._download_one, url, item_opts, i, ui_index, title)
                futures[future] = (i, ui_index, title)

            processed_count = 0
            for future in as_completed(futures):
                i, ui_index, title = futures[future]
                processed_count += 1
                try:
                    result = future.result()
                    self.downloaded_files.append(result or title)

                    self.progress.emit({
                        "overall_percent": (processed_count / self.total_files) * 100,
                        "current_percent": 100,
                        "status": f"完成: {title}",
                        "ui_index": ui_index,
                        "file_complete": True,
                    })
                except Exception as e:
                    if "Stopped by user" in str(e):
                        logger.info(f"Download for {title} stopped by user.")
                    else:
                        self.progress.emit({
                            "overall_percent": (processed_count / self.total_files) * 100,
                            "current_percent": 0,
                            "status": f"失败: {title}",
                            "ui_index": ui_index,
                            "file_complete": False,
                        })
                        error_msg = strip_ansi(str(e))
                        if len(error_msg) > 500:
                            error_msg = error_msg[:500] + "..."
                        self.error.emit(f"下载失败 ({title}): {error_msg}")

            executor.shutdown(wait=False, cancel_futures=True)

        except Exception as e:
            if "Stopped by user" in str(e):
                logger.info("Download stopped by user.")
            else:
                self.error.emit(f"下载流程异常: {strip_ansi(str(e))}")
                return

        if self._is_running:
            self.finished.emit()

    def _progress_hook_factory(self, ui_index, item_idx):
        def hook(d):
            return self._handle_progress(d, ui_index, item_idx)
        return hook

    def _handle_progress(self, d, ui_index, item_idx):
        if not self._is_running:
            raise Exception("Stopped by user")

        status = d.get("status")
        if status == "downloading":
            percent = 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes")
            if total and downloaded:
                try:
                    percent = (float(downloaded) / float(total)) * 100
                except Exception:
                    percent = 0
            else:
                p_str = strip_ansi(d.get("_percent_str", "").replace("%", ""))
                try:
                    percent = float(p_str)
                except Exception:
                    percent = 0

            overall = ((item_idx + (percent / 100.0)) / self.total_files) * 100
            filename = os.path.basename(d.get("filename", "Unknown"))

            speed_val = None
            sp_numeric = d.get("speed")
            if sp_numeric:
                try:
                    speed_val = self._format_speed(float(sp_numeric))
                except Exception:
                    speed_val = None
            if speed_val is None:
                speed_str = d.get("_speed_str", "").strip()
                parsed = self._parse_human_speed(speed_str)
                if parsed is not None:
                    speed_val = self._format_speed(parsed)
            if speed_val is None or speed_val == "-":
                speed_val = "-"

            self.progress.emit({
                "overall_percent": overall,
                "current_percent": percent,
                "status": filename,
                "speed": speed_val,
                "eta": strip_ansi(d.get("_eta_str", "").strip()),
                "ui_index": ui_index,
                "file_complete": False,
            })
        elif status == "finished":
            fname = d.get("filename")
            if fname:
                self.downloaded_files.append(fname)

    def stop(self):
        """Set flag to stop download"""
        self._is_running = False

    def _download_one(self, url, opts, item_idx, ui_index, title):
        """Run a single yt-dlp download using provided options. Returns title/filename on success."""
        if not self._is_running:
            raise Exception("Stopped by user")
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        return title
