"""
whisper_transcription.py
~~~~~~~~~~~~~~~~~~~~~~~~
Groq Whisper 词级语音识别 + 文案对齐 + 字幕导出

主要功能:
  - extract_audio_with_ffmpeg()  — 从视频/音频文件中提取适合上传的 16kHz 单声道 WAV
  - transcribe_with_groq()       — 调用 Groq Whisper API，获取词级时间戳
  - align_transcript_with_script() — 将用户参考文案与 Whisper 识别词序列比对纠错
  - build_segments_from_words()  — 词序列重新分组为字幕 segments
  - export_srt / export_vtt / export_ass / export_fcpxml — 多格式导出

依赖:
  - ffmpeg (系统 PATH 或 bin/ 目录)
  - requests
  - difflib (标准库)
"""

import os
import re
import math
import time
import subprocess
import tempfile
import requests
from difflib import SequenceMatcher
from pathlib import Path
from ..logging_config import get_logger
from ..utils import get_ffmpeg_exe, get_ffprobe_exe

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

SUPPORTED_WHISPER_MODELS = [
    "whisper-large-v3-turbo",
    "whisper-large-v3",
    "distil-whisper-large-v3-en",
]

# Groq 单次上传文件上限 (25 MB)
GROQ_MAX_BYTES = 25 * 1024 * 1024

# 默认字幕分段策略：每段最多 N 个词
DEFAULT_WORDS_PER_SEGMENT = 10

# 句子边界标点（中英日韩）
SENTENCE_BOUNDARIES = re.compile(r'[。！？!?.…]+$')

# 语言代码 → 显示名称（用于 UI 下拉）
LANGUAGE_OPTIONS = {
    "auto":  "自动检测",
    "zh":    "中文 (Chinese)",
    "en":    "英文 (English)",
    "ja":    "日文 (Japanese)",
    "ko":    "韩文 (Korean)",
    "es":    "西班牙文 (Spanish)",
    "fr":    "法文 (French)",
    "de":    "德文 (German)",
    "pt":    "葡萄牙文 (Portuguese)",
    "ru":    "俄文 (Russian)",
    "ar":    "阿拉伯文 (Arabic)",
    "it":    "意大利文 (Italian)",
    "th":    "泰文 (Thai)",
    "vi":    "越南文 (Vietnamese)",
    "id":    "印尼文 (Indonesian)",
    "hi":    "印地文 (Hindi)",
}

# 翻译目标语言（用于 UI 下拉）
TRANSLATE_TARGET_LANGUAGES = {
    "zh":   "简体中文",
    "en":   "英文",
    "ja":   "日文",
    "ko":   "韩文",
    "es":   "西班牙文",
    "fr":   "法文",
    "de":   "德文",
    "pt":   "葡萄牙文",
    "ru":   "俄文",
}


# ---------------------------------------------------------------------------
# ffmpeg 音频提取
# ---------------------------------------------------------------------------

# def _find_ffmpeg() -> str:
#     """查找 ffmpeg 可执行文件路径（优先 bin/ 目录，其次系统 PATH）。"""
#     from ..utils import get_resource_path  # 复用项目已有的路径工具
#     candidates = [
#         str(get_resource_path("bin/ffmpeg")),
#         str(get_resource_path("bin/ffmpeg.exe")),
#         "ffmpeg",
#     ]
#     for c in candidates:
#         try:
#             result = subprocess.run([c, "-version"], capture_output=True, timeout=5)
#             if result.returncode == 0:
#                 return c
#         except (FileNotFoundError, subprocess.TimeoutExpired):
#             continue
#     raise FileNotFoundError("未找到 ffmpeg，请确认 bin/ffmpeg 存在或系统 PATH 中包含 ffmpeg。")

def _check_ffmpeg_path():
    """检查捆绑的 ffmpeg 和 ffprobe 文件是否存在"""
    # 注意：这里使用 get_ffmpeg_exe() 返回的路径，在运行时是绝对路径
    ffmpeg_path = Path(get_ffmpeg_exe())
    ffprobe_path = Path(get_ffprobe_exe())
    
    if not ffmpeg_path.exists():
        logger.critical(f"绑定的 ffmpeg 可执行文件未找到: {ffmpeg_path}")
        raise FileNotFoundError(f"ffmpeg not found: {ffmpeg_path}")
    if not ffprobe_path.exists():
        logger.critical(f"绑定的 ffprobe 可执行文件未找到: {ffprobe_path}")
        raise FileNotFoundError(f"ffprobe not found: {ffprobe_path}")

def extract_audio_with_ffmpeg(
    media_path: str,
    output_wav: str,
    sample_rate: int = 16000,
    progress_callback=None,
) -> str:
    """
    使用 ffmpeg 从视频/音频文件中提取单声道 WAV。

    Args:
        media_path:        输入文件路径（视频或音频）
        output_wav:        输出 WAV 文件路径
        sample_rate:       采样率，默认 16000Hz（Whisper 要求）
        progress_callback: 可选回调 fn(message: str)

    Returns:
        output_wav 路径
    """
    ffmpeg_bin = str(get_ffmpeg_exe())

    cmd = [
        ffmpeg_bin,
        "-y",                    # 覆盖输出
        "-i", str(media_path),   # 确保路径是字符串
        "-vn",                   # 不含视频流
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", str(sample_rate), # 采样率
        "-ac", "1",              # 单声道
        output_wav,
    ]

    if progress_callback:
        progress_callback(f"正在提取音频: {os.path.basename(media_path)}")

    logger.info(f"ffmpeg 命令: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 音频提取失败:\n{result.stderr[-2000:]}")

    if not os.path.exists(output_wav):
        raise RuntimeError("ffmpeg 运行完毕但未找到输出 WAV 文件。")

    file_size = os.path.getsize(output_wav)
    logger.info(f"音频提取完成: {output_wav} ({file_size/1024/1024:.1f} MB)")

    if progress_callback:
        progress_callback(f"音频提取完成 ({file_size/1024/1024:.1f} MB)")

    return output_wav


def get_audio_duration(media_path: str) -> float:
    """使用 ffprobe 获取媒体文件时长（秒）。"""
    ffprobe_bin = str(get_ffprobe_exe())

    cmd = [
        ffprobe_bin, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        media_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def split_wav_into_chunks(
    wav_path: str,
    max_bytes: int = GROQ_MAX_BYTES,
    tmp_dir: str = None,
) -> list:
    """
    将 WAV 文件按大小分块（每块 < max_bytes），用于超长文件处理。

    Returns:
        list of (chunk_path, start_sec, end_sec)
    """
    file_size = os.path.getsize(wav_path)
    if file_size <= max_bytes:
        return [(wav_path, 0.0, None)]

    duration = get_audio_duration(wav_path)
    chunk_duration = duration * max_bytes / file_size * 0.92  # 留 8% 安全余量

    chunks = []
    t = 0.0
    ffmpeg_bin = str(get_ffmpeg_exe())
    tmp_dir = tmp_dir or tempfile.gettempdir()

    chunk_idx = 0
    while t < duration:
        end_t = min(t + chunk_duration, duration)
        chunk_path = os.path.join(tmp_dir, f"_whisper_chunk_{chunk_idx}.wav")
        cmd = [
            ffmpeg_bin, "-y",
            "-i", wav_path,
            "-ss", str(t),
            "-to", str(end_t),
            "-c", "copy",
            chunk_path,
        ]
        subprocess.run(cmd, capture_output=True, timeout=120)
        chunks.append((chunk_path, t, end_t))
        t = end_t
        chunk_idx += 1

    logger.info(f"已将音频分为 {len(chunks)} 个分块")
    return chunks


# ---------------------------------------------------------------------------
# Groq Whisper API 调用
# ---------------------------------------------------------------------------

def transcribe_with_groq(
    wav_path: str,
    api_key: str,
    language: str = "auto",
    model: str = "whisper-large-v3-turbo",
    user_prompt: str = "",
    progress_callback=None,
    time_offset: float = 0.0,
) -> dict:
    """
    调用 Groq Whisper API 获取词级时间戳。

    Args:
        wav_path:          WAV 文件路径
        api_key:           Groq API Key
        language:          语言代码，"auto" 表示自动检测
        model:             Whisper 模型名称
        user_prompt:       参考文案前缀，提升识别准确率（最多 224 tokens）
        progress_callback: 可选回调 fn(message: str)
        time_offset:       当处理分块时，时间戳偏移量（秒）

    Returns:
        {"words": [{"word": str, "start": float, "end": float}, ...],
         "text": str,
         "language": str}
    """
    if not api_key:
        raise ValueError("未提供 Groq API Key")

    headers = {"Authorization": f"Bearer {api_key}"}

    form_data = {
        "model": model,
        "response_format": "verbose_json",
        "timestamp_granularities[]": "word",
    }

    if language and language != "auto":
        form_data["language"] = language

    if user_prompt:
        # Groq Whisper prompt 最多 224 tokens，截断保险
        form_data["prompt"] = user_prompt[:500]

    if progress_callback:
        progress_callback(f"正在上传至 Groq Whisper ({model})...")

    logger.info(f"调用 Groq Whisper API: model={model}, language={language or 'auto'}")

    retry_count = 0
    max_retries = 3
    backoff = 5

    while retry_count <= max_retries:
        try:
            with open(wav_path, "rb") as f:
                files = {"file": (os.path.basename(wav_path), f, "audio/wav")}
                response = requests.post(
                    GROQ_WHISPER_URL,
                    headers=headers,
                    data=form_data,
                    files=files,
                    timeout=120,
                )

            if response.status_code == 200:
                data = response.json()
                words = data.get("words", [])

                # 应用时间偏移（分块处理时）
                if time_offset > 0:
                    for w in words:
                        w["start"] = w.get("start", 0) + time_offset
                        w["end"] = w.get("end", 0) + time_offset

                logger.info(f"Whisper 识别完成: {len(words)} 个词，语言={data.get('language', '未知')}")

                if progress_callback:
                    progress_callback(f"识别完成，共 {len(words)} 个词")

                return {
                    "words": words,
                    "text": data.get("text", ""),
                    "language": data.get("language", ""),
                }

            elif response.status_code == 429:
                retry_count += 1
                wait = backoff * (2 ** (retry_count - 1))
                logger.warning(f"Groq 速率限制 (429)，{wait}s 后重试...")
                if progress_callback:
                    progress_callback(f"API 速率限制，{wait}s 后重试...")
                time.sleep(wait)

            else:
                raise RuntimeError(f"Groq Whisper API 错误 ({response.status_code}): {response.text[:500]}")

        except (requests.Timeout, requests.ConnectionError) as e:
            retry_count += 1
            if retry_count > max_retries:
                raise RuntimeError(f"网络请求失败（已重试 {max_retries} 次）: {e}")
            time.sleep(3)

    raise RuntimeError("Groq Whisper API 重试次数超限")


def transcribe_file(
    media_path: str,
    api_key: str,
    language: str = "auto",
    model: str = "whisper-large-v3-turbo",
    user_prompt: str = "",
    progress_callback=None,
) -> dict:
    """
    完整的识别流程：提取音频 → 分块（如需要）→ 调用 Groq API → 合并结果。

    Returns:
        {"words": [...], "text": str, "language": str}
    """
    tmp_dir = tempfile.mkdtemp(prefix="whisper_")
    tmp_wav = os.path.join(tmp_dir, "audio_extracted.wav")

    try:
        # Step 1: 提取音频
        extract_audio_with_ffmpeg(media_path, tmp_wav, progress_callback=progress_callback)

        # Step 2: 分块检查
        chunks = split_wav_into_chunks(tmp_wav, tmp_dir=tmp_dir)

        all_words = []
        full_text_parts = []
        detected_language = ""

        for idx, (chunk_path, start_sec, _end_sec) in enumerate(chunks):
            if len(chunks) > 1 and progress_callback:
                progress_callback(f"处理分块 {idx+1}/{len(chunks)}...")

            result = transcribe_with_groq(
                wav_path=chunk_path,
                api_key=api_key,
                language=language,
                model=model,
                user_prompt="",
                progress_callback=progress_callback if len(chunks) == 1 else None,
                time_offset=start_sec,
            )

            all_words.extend(result["words"])
            full_text_parts.append(result["text"])
            if not detected_language:
                detected_language = result["language"]

        return {
            "words": all_words,
            "text": " ".join(full_text_parts),
            "language": detected_language,
        }

    finally:
        # 清理临时文件
        import shutil
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 文案对齐引擎
# ---------------------------------------------------------------------------

def _tokenize(text: str, is_cjk_heavy: bool = False) -> list:
    """
    将文本分词。
    - 中日韩文本：按字符分割
    - 西文文本：按空格分割，去除标点保留词干
    """
    if is_cjk_heavy:
        # 字符级 tokenize（去掉标点，保留汉字/假名/字母数字）
        return [c for c in text if c.strip() and not re.match(r'[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7ff]', c)]
    else:
        tokens = re.findall(r"[a-zA-Z0-9'\-]+", text.lower())
        return tokens


def _detect_cjk(text: str) -> bool:
    """判断文本是否以中日韩字符为主。"""
    cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7ff]', text))
    total_chars = len([c for c in text if c.strip()])
    return total_chars > 0 and cjk_chars / total_chars > 0.3


def align_transcript_with_script(
    whisper_words: list,
    user_script: str,
) -> list:
    """
    将用户提供的参考文案与 Whisper 词级识别结果对齐，输出带时间戳的词列表。

    算法：
    1. 将参考文案分词 → script_tokens
    2. 将 Whisper words 提取词文本 → asr_tokens
    3. 使用 SequenceMatcher 进行最长公共子序列比对
    4. 对匹配上的词：使用 Whisper 时间戳 + 用户文案的原始词（保留大小写/标点）
    5. 对参考文案中多出的词（漏识别）：线性插值补充时间戳
    6. 对 Whisper 多出的词（噪声）：丢弃

    Args:
        whisper_words: Groq 返回的 [{"word": str, "start": float, "end": float}]
        user_script:   用户输入的参考文案（字符串）

    Returns:
        list of {"word": str, "start": float, "end": float, "aligned": bool}
        aligned=True 表示有 Whisper 时间戳，False 表示是插值的
    """
    if not user_script or not user_script.strip():
        # 无参考文案：直接使用 Whisper 原始结果
        return [
            {"word": w.get("word", ""), "start": w.get("start", 0.0), "end": w.get("end", 0.0), "aligned": True}
            for w in whisper_words
        ]

    if not whisper_words:
        return []

    is_cjk = _detect_cjk(user_script)

    # 提取 Whisper 词（清理空格）
    asr_raw = [w.get("word", "").strip() for w in whisper_words]
    asr_tokens = [re.sub(r'[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7ff]', '', t).lower() for t in asr_raw]

    # 解析参考文案为 (原始词, 清理后词) 对
    if is_cjk:
        # 逐字，保留原始字符（含标点），仅对齐时用清理后的字
        script_chars_raw = list(user_script)
        script_pairs = []
        for ch in script_chars_raw:
            clean = re.sub(r'[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7ff]', '', ch).lower()
            script_pairs.append((ch, clean))
        # 过滤掉纯空格/纯标点的 pair（对齐时忽略，但保留在输出中）
        align_pairs = [(raw, clean) for raw, clean in script_pairs if clean]
        # 为了对齐，标点也可以参与但不强求匹配
        script_tokens_clean = [clean for _, clean in align_pairs]
        script_tokens_raw = [raw for raw, _ in align_pairs]
    else:
        # 英文：按单词，保留原词
        script_words_raw = re.findall(r"[\w']+|[^\w\s]", user_script)
        script_pairs = [(w, re.sub(r'[^\w]', '', w).lower()) for w in script_words_raw]
        align_pairs_all = [(raw, clean) for raw, clean in script_pairs if clean]
        script_tokens_clean = [clean for _, clean in align_pairs_all]
        script_tokens_raw = [raw for raw, _ in align_pairs_all]

    # SequenceMatcher 对比
    matcher = SequenceMatcher(None, asr_tokens, script_tokens_clean, autojunk=False)
    opcodes = matcher.get_opcodes()

    # 构建 asr_idx → script_idx 映射
    asr_to_script = {}   # asr word index → script token index
    script_to_asr = {}   # script token index → asr word index (or (asr_before, asr_after) for interpolation)

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            # 完全匹配
            for offset in range(i2 - i1):
                asr_to_script[i1 + offset] = j1 + offset
                script_to_asr[j1 + offset] = i1 + offset
        elif tag == "replace":
            # 部分匹配：尽量一对一对应（取长度较小者）
            pairs = min(i2 - i1, j2 - j1)
            for offset in range(pairs):
                asr_to_script[i1 + offset] = j1 + offset
                script_to_asr[j1 + offset] = i1 + offset
        # insert: script tokens 中多出的（Whisper 漏识别）→ 后面做插值
        # delete: asr tokens 中多出的（噪声）→ 忽略

    # 构建输出词列表
    aligned_words = []
    n_script = len(script_tokens_clean)

    # 先确定每个 script token 的时间戳（已匹配或需要插值）
    for j in range(n_script):
        raw_word = script_tokens_raw[j]

        if j in script_to_asr:
            # 直接匹配到 Whisper 词
            asr_idx = script_to_asr[j]
            w = whisper_words[asr_idx]
            aligned_words.append({
                "word": raw_word,
                "start": float(w.get("start", 0)),
                "end": float(w.get("end", 0)),
                "aligned": True,
            })
        else:
            # 需要插值：找最近的已知时间戳进行线性插值
            prev_time = None
            next_time = None

            # 找前一个已匹配词的结束时间
            for pj in range(j - 1, -1, -1):
                if pj in script_to_asr:
                    prev_time = float(whisper_words[script_to_asr[pj]].get("end", 0))
                    break

            # 找后一个已匹配词的开始时间
            for nj in range(j + 1, n_script):
                if nj in script_to_asr:
                    next_time = float(whisper_words[script_to_asr[nj]].get("start", 0))
                    break

            # 插值
            if prev_time is not None and next_time is not None:
                # 线性插值：在 prev_time 和 next_time 之间平均分配
                gap_words = sum(1 for k in range(j, n_script) if k not in script_to_asr and (
                    (k < min((kk for kk in script_to_asr if kk > j), default=n_script))
                ))
                gap_words = max(gap_words, 1)
                gap = (next_time - prev_time) / (gap_words + 1)
                # 计算当前词在 gap 中的位置
                pos = sum(1 for k in range(j) if k not in script_to_asr and (
                    (k > max((kk for kk in script_to_asr if kk < j), default=-1))
                )) + 1
                start_t = prev_time + gap * pos
                end_t = start_t + gap
                aligned_words.append({
                    "word": raw_word,
                    "start": round(start_t, 3),
                    "end": round(end_t, 3),
                    "aligned": False,
                })
            elif prev_time is not None:
                # 只有前面的锚点
                start_t = prev_time + 0.1
                aligned_words.append({
                    "word": raw_word,
                    "start": round(start_t, 3),
                    "end": round(start_t + 0.3, 3),
                    "aligned": False,
                })
            elif next_time is not None:
                # 只有后面的锚点
                start_t = max(0.0, next_time - 0.3)
                aligned_words.append({
                    "word": raw_word,
                    "start": round(start_t, 3),
                    "end": round(next_time, 3),
                    "aligned": False,
                })
            else:
                # 完全没有锚点（整段都未匹配）
                aligned_words.append({
                    "word": raw_word,
                    "start": 0.0,
                    "end": 0.3,
                    "aligned": False,
                })

    logger.info(
        f"对齐完成: 文案词={n_script}, Whisper词={len(whisper_words)}, "
        f"已对齐={sum(1 for w in aligned_words if w['aligned'])}"
    )

    return aligned_words


# ---------------------------------------------------------------------------
# 词序列 → Segments 分组
# ---------------------------------------------------------------------------

def build_segments_from_words(
    aligned_words: list,
    words_per_segment: int = DEFAULT_WORDS_PER_SEGMENT,
    use_script_punctuation: bool = True,
    pause_threshold: float = 0.4,
) -> list:
    """
    将词级列表重新分组为字幕 segments。

    分组策略（按优先级）：
    1. 遇到句子边界标点（。！？.!?）→ 切断
    2. 累计词数达到 words_per_segment → 切断

    Args:
        aligned_words:         align_transcript_with_script() 的输出
        words_per_segment:     每段最多词数
        use_script_punctuation: 是否按标点切断

    Returns:
        list of {"text": str, "start": float, "end": float}
    """
    if not aligned_words:
        return []

    segments = []
    current_words = []
    current_start = aligned_words[0]["start"]
    is_cjk = _detect_cjk("".join(w["word"] for w in aligned_words[:20]))

    def flush_segment():
        if not current_words:
            return
        if is_cjk:
            text = "".join(w["word"] for w in current_words)
        else:
            text = " ".join(w["word"] for w in current_words)
        segments.append({
            "text": text,
            "start": current_words[0]["start"],
            "end": current_words[-1]["end"],
        })

    for word_info in aligned_words:
        word = word_info["word"]

        # 如果当前词与上一词之间存在明显停顿，则切断当前段
        if current_words:
            prev_end = current_words[-1]["end"]
            if word_info["start"] - prev_end > pause_threshold:
                flush_segment()
                current_words = []

        current_words.append(word_info)

        # 检查是否应该切断
        should_break = False

        if use_script_punctuation and SENTENCE_BOUNDARIES.search(word):
            should_break = True
        elif len(current_words) >= words_per_segment:
            should_break = True

        if should_break:
            flush_segment()
            current_words = []

    flush_segment()

    return segments


# ---------------------------------------------------------------------------
# 字幕格式导出
# ---------------------------------------------------------------------------

def _format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间格式 HH:MM:SS,mmm"""
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_vtt_time(seconds: float) -> str:
    """将秒数转换为 WebVTT 时间格式 HH:MM:SS.mmm"""
    srt = _format_srt_time(seconds)
    return srt.replace(",", ".")


def export_srt(segments: list, output_path: str) -> str:
    """
    导出 SRT 字幕文件。

    Args:
        segments:    [{"text": str, "start": float, "end": float}]
        output_path: 输出文件路径

    Returns:
        output_path
    """
    lines = []
    for idx, seg in enumerate(segments, 1):
        start = _format_srt_time(seg["start"])
        end = _format_srt_time(seg["end"])
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"])
        lines.append("")

    content = "\n".join(lines)
    Path(output_path).write_text(content, encoding="utf-8")
    logger.info(f"SRT 导出完成: {output_path} ({len(segments)} 条)")
    return output_path


def export_vtt(segments: list, output_path: str) -> str:
    """导出 WebVTT 字幕文件。"""
    lines = ["WEBVTT", ""]
    for idx, seg in enumerate(segments, 1):
        start = _format_vtt_time(seg["start"])
        end = _format_vtt_time(seg["end"])
        lines.append(f"{idx}")
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"])
        lines.append("")

    content = "\n".join(lines)
    Path(output_path).write_text(content, encoding="utf-8")
    logger.info(f"VTT 导出完成: {output_path}")
    return output_path


def export_ass(segments: list, output_path: str) -> str:
    """导出 ASS 字幕文件（基础格式）。"""
    def sec_to_ass(s: float) -> str:
        s = max(0.0, s)
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = s % 60
        return f"{h}:{m:02d}:{sec:05.2f}"

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,70,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,1,2,10,10,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for seg in segments:
        start = sec_to_ass(seg["start"])
        end = sec_to_ass(seg["end"])
        text = seg["text"].replace("\n", "\\N")
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    content = header + "\n".join(events) + "\n"
    Path(output_path).write_text(content, encoding="utf-8")
    logger.info(f"ASS 导出完成: {output_path}")
    return output_path


def export_fcpxml(segments: list, output_path: str, fps: float = 25.0) -> str:
    """
    导出 Final Cut Pro XML (FCPXML v1.11) 字幕文件。
    复用已有的时间码格式逻辑。
    """
    import fractions

    def sec_to_fcptime(secs: float, fps_f: float) -> str:
        """秒 → FCP 时间格式 (frame_count/timebase s)"""
        frames = round(secs * fps_f)
        if fps_f == int(fps_f):
            return f"{frames * int(1000/fps_f if fps_f < 100 else 1)}/{int(1000 if fps_f < 100 else fps_f)}s"
        # 用分数简化
        fr = fractions.Fraction(frames, 1) / fractions.Fraction(fps_f).limit_denominator(1001)
        return f"{fr.numerator}/{fr.denominator}s"

    # 简化版 FCPXML：使用 1001/24000 时间基（24fps）或 1/fps
    timebase = "1001/24000s" if abs(fps - 23.976) < 0.1 else f"1/{int(fps)}s"
    frames_per_sec = fps

    def to_fcp(secs: float) -> str:
        frames = round(secs * frames_per_sec)
        return f"{frames}/{int(frames_per_sec)}s"

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE fcpxml>',
        '<fcpxml version="1.11">',
        '    <resources>',
        f'        <format id="r1" name="FFVideoFormat1080p{int(fps)}" frameDuration="1/{int(fps)}s" width="1920" height="1080" colorSpace="1-1-1 (Rec. 709)"/>',
        '    </resources>',
        '    <library>',
        '        <event name="Whisper Subtitles">',
        '            <project name="Whisper Subtitles">',
        '                <sequence format="r1" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48000">',
        '                    <spine>',
        '                        <gap name="Gap" offset="0s" duration="' + to_fcp(segments[-1]["end"] if segments else 10) + '" start="0s">',
    ]

    for idx, seg in enumerate(segments):
        start = to_fcp(seg["start"])
        dur = to_fcp(max(0.05, seg["end"] - seg["start"]))
        text = seg["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        xml_lines += [
            f'                            <title name="Subtitle {idx+1}" lane="1" offset="{start}" ref="r1" duration="{dur}" role="titles">',
            f'                                <text>',
            f'                                    <text-style ref="ts{idx+1}">{text}</text-style>',
            f'                                </text>',
            f'                                <text-style-def id="ts{idx+1}">',
            f'                                    <text-style font="Helvetica Neue" fontSize="80" fontFace="Bold" fontColor="1 1 1 1" alignment="center"/>',
            f'                                </text-style-def>',
            f'                            </title>',
        ]

    xml_lines += [
        '                        </gap>',
        '                    </spine>',
        '                </sequence>',
        '            </project>',
        '        </event>',
        '    </library>',
        '</fcpxml>',
    ]

    content = "\n".join(xml_lines)
    Path(output_path).write_text(content, encoding="utf-8")
    logger.info(f"FCPXML 导出完成: {output_path}")
    return output_path


def segments_to_srt_text(segments: list) -> str:
    """将 segments 转换为 SRT 格式字符串（用于 UI 预览）。"""
    lines = []
    for idx, seg in enumerate(segments, 1):
        start = _format_srt_time(seg["start"])
        end = _format_srt_time(seg["end"])
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Qt Worker（在线程中运行完整流程）
# ---------------------------------------------------------------------------

try:
    from PySide6.QtCore import QObject, Signal

    class WhisperWorker(QObject):
        """
        在 QThread 中运行完整的识别 + 对齐 + 导出流程。

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
            model: str = "whisper-large-v3-turbo",
            user_script: str = "",
            words_per_segment: int = DEFAULT_WORDS_PER_SEGMENT,
            parent=None,
        ):
            super().__init__(parent)
            self.media_path = media_path
            self.api_key = api_key
            self.language = language
            self.model = model
            self.user_script = user_script
            self.words_per_segment = words_per_segment
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
                    language=self.language if self.language != "auto" else "",
                    model=self.model,
                    user_prompt="",
                    progress_callback=self.progress.emit,
                )

                if self._cancelled:
                    return

                whisper_words = result["words"]
                self.progress.emit(f"✅ 识别完成，共 {len(whisper_words)} 个词。正在进行文案对齐...")

                # Step 2: 文案对齐
                aligned_words = align_transcript_with_script(
                    whisper_words=whisper_words,
                    user_script=self.user_script,
                )

                if self._cancelled:
                    return

                # Step 3: 分组为 segments
                self.progress.emit("📝 正在生成字幕分段...")
                segments = build_segments_from_words(
                    aligned_words=aligned_words,
                    words_per_segment=self.words_per_segment,
                )

                self.progress.emit(f"✨ 完成！共生成 {len(segments)} 条字幕。")
                self.finished.emit(segments)

            except Exception as e:
                logger.exception(f"WhisperWorker 异常: {e}")
                self.error.emit(str(e))

except ImportError:
    # 仅在有 PySide6 时才定义 Worker（允许在非 Qt 环境下导入本模块）
    pass
