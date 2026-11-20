"""
whisper_worker.py
~~~~~~~~~~~~~~~~~
Gladia 语音识别异步 Worker（Qt 线程包装层）。
将 Qt 信号/线程调度与 gladia_transcription 核心识别逻辑分离。
"""

from PySide6.QtCore import QObject, Signal

from ..logging_config import get_logger
from .gladia_transcription import (
    align_transcript_with_script,
    build_segments_with_builder,
    transcribe_file,
)

logger = get_logger(__name__)


class WhisperWorker(QObject):
    """
    在 QThread 中运行完整的识别 + 对齐 + 导出流程（使用 Gladia API）。

    信号:
        progress(str)  — 进度消息
        finished(list) — 完成后的 segments 列表
        error(str)     — 错误消息
    """

    progress = Signal(str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        media_path: str,
        api_key: str,
        language: str = "auto",
        user_script: str = "",
        subtitle_config: dict = None,
        parent=None,
    ):
        super().__init__(parent)
        self.media_path = media_path
        self.api_key = api_key
        self.language = language
        self.user_script = user_script
        self.subtitle_config = subtitle_config or {}
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self.progress.emit("🎬 开始处理媒体文件...")

            if self._cancelled:
                return

            # Step 1: 提取音频 + 识别
            result = transcribe_file(
                media_path=self.media_path,
                api_key=self.api_key,
                language=self.language if self.language != "auto" else "auto",
                progress_callback=self.progress.emit,
            )

            if self._cancelled:
                return

            whisper_words = result["words"]
            self.progress.emit(f"✅ 识别完成，共 {len(whisper_words)} 个词。正在进行文案对齐...")

            # Step 2: 文案对齐（模糊纠错）
            aligned_words = align_transcript_with_script(
                whisper_words=whisper_words,
                user_script=self.user_script,
            )

            if self._cancelled:
                return

            # Step 3: 使用 SubtitleSegmentBuilder 分段
            self.progress.emit("📝 正在生成字幕分段...")
            segments = build_segments_with_builder(
                aligned_words=aligned_words,
                config=self.subtitle_config,
            )

            self.progress.emit(f"✨ 完成！共生成 {len(segments)} 条字幕。")
            self.finished.emit(segments)

        except Exception as e:
            logger.exception(f"WhisperWorker 异常: {e}")
            self.error.emit(str(e))
