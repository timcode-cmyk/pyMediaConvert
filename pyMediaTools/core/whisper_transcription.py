"""
whisper_transcription.py
~~~~~~~~~~~~~~~~~~~~~~~~
Gladia 词级语音识别 + 文案对齐 + 字幕导出

主要功能:
  - extract_audio_with_ffmpeg()      — 从视频/音频文件中提取适合上传的 16kHz 单声道 WAV
  - transcribe_with_gladia()         — 调用 Gladia v2 API，获取词级时间戳
  - align_transcript_with_script()   — 将用户参考文案与识别词序列比对纠错（模糊匹配）
  - build_segments_with_builder()    — 使用 SubtitleSegmentBuilder 智能断行分段
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

GLADIA_UPLOAD_URL = "https://api.gladia.io/v2/upload"
GLADIA_TRANSCRIPTION_URL = "https://api.gladia.io/v2/pre-recorded"

# Gladia 单次上传文件上限 (500 MB，实际限制更宽)
GLADIA_MAX_BYTES = 200 * 1024 * 1024

# 默认字幕分段策略（传递给 SubtitleSegmentBuilder）
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

def _check_ffmpeg_path():
    """检查捆绑的 ffmpeg 和 ffprobe 文件是否存在"""
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
        sample_rate:       采样率，默认 16000Hz（Whisper/Gladia 要求）
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
    max_bytes: int = GLADIA_MAX_BYTES,
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
        chunk_path = os.path.join(tmp_dir, f"_gladia_chunk_{chunk_idx}.wav")
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
# Gladia v2 API 调用
# ---------------------------------------------------------------------------

def _gladia_upload_audio(wav_path: str, api_key: str) -> str:
    """
    上传音频文件到 Gladia，返回 audio_url。
    """
    headers = {
        "x-gladia-key": api_key,
    }
    with open(wav_path, "rb") as f:
        files = {"audio": (os.path.basename(wav_path), f, "audio/wav")}
        response = requests.post(GLADIA_UPLOAD_URL, headers=headers, files=files, timeout=120)

    if response.status_code not in (200, 201):
        raise RuntimeError(f"Gladia 上传失败 ({response.status_code}): {response.text[:500]}")

    data = response.json()
    audio_url = data.get("audio_url") or data.get("url")
    if not audio_url:
        raise RuntimeError(f"Gladia 上传响应中未找到 audio_url: {data}")

    logger.info(f"Gladia 音频上传成功: {audio_url}")
    return audio_url


def _gladia_submit_transcription(audio_url: str, api_key: str, language: str = "") -> str:
    """
    提交转录任务，返回 result_url (轮询地址)。

    Gladia v2 /v2/pre-recorded 请求体（扁平结构，无嵌套）:
      - audio_url: 必须
      - language_config: 可选，语言配置
      - diarization: 可选
      词级时间戳在响应的 utterances[].words[] 中默认返回，无需额外参数
    """
    headers = {
        "x-gladia-key": api_key,
        "Content-Type": "application/json",
    }

    body = {
        "audio_url": audio_url,
        "diarization": False,
    }

    # 语言配置：直接放根层级，不嵌套
    if language and language not in ("auto", ""):
        body["language_config"] = {
            "languages": [language],
            "code_switching": False,
        }

    response = requests.post(GLADIA_TRANSCRIPTION_URL, headers=headers, json=body, timeout=60)

    if response.status_code not in (200, 201):
        raise RuntimeError(f"Gladia 提交转录失败 ({response.status_code}): {response.text[:500]}")

    data = response.json()
    result_url = data.get("result_url")
    if not result_url:
        raise RuntimeError(f"Gladia 转录响应中未找到 result_url: {data}")

    logger.info(f"Gladia 转录任务已提交，轮询地址: {result_url}")
    return result_url


def _gladia_poll_result(result_url: str, api_key: str, progress_callback=None, timeout: int = 600) -> dict:
    """
    轮询 Gladia 转录结果，直到状态为 done。

    Returns:
        Gladia 响应完整 JSON
    """
    headers = {"x-gladia-key": api_key}
    deadline = time.time() + timeout
    poll_interval = 3

    while time.time() < deadline:
        response = requests.get(result_url, headers=headers, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Gladia 轮询失败 ({response.status_code}): {response.text[:300]}")

        data = response.json()
        status = data.get("status", "")

        if status == "done":
            logger.info("Gladia 转录完成")
            return data
        elif status == "error":
            error_msg = data.get("error", {}).get("message", "未知错误")
            raise RuntimeError(f"Gladia 转录失败: {error_msg}")
        else:
            if progress_callback:
                progress_callback(f"Gladia 转录中... ({status})")
            logger.debug(f"Gladia 状态: {status}，等待 {poll_interval}s")
            time.sleep(poll_interval)
            poll_interval = min(poll_interval + 1, 10)  # 逐渐延长轮询间隔

    raise RuntimeError(f"Gladia 转录超时（>{timeout}s）")


def _extract_words_from_gladia(result_data: dict, time_offset: float = 0.0) -> list:
    """
    从 Gladia 响应中提取统一格式的词级时间戳列表。

    优先级:
    1. utterances[].words[]  — 词级（最精准）
    2. transcription.words[] — 顶层词数组
    3. utterances[] 内文本均分 — 句子级时间戳内按词均分（保留时间准确性）
    4. full_transcript 全局均分 — 最终保底

    Returns:
        [{"word": str, "start": float, "end": float}, ...]
    """
    result = result_data.get("result", {})
    transcription = result.get("transcription", {})
    utterances = transcription.get("utterances", [])

    # 1. utterances[].words[] — 词级（最精准）
    word_level = []
    for utt in utterances:
        for w in utt.get("words", []):
            word_text = w.get("word", "").strip()
            if word_text:
                word_level.append({
                    "word": word_text,
                    "start": float(w.get("start", 0)) + time_offset,
                    "end": float(w.get("end", 0)) + time_offset,
                })
    if word_level:
        logger.info(f"Gladia: 词级时间戳，共 {len(word_level)} 个词")
        return word_level

    # 2. transcription.words[] — 顶层词数组
    raw_words = transcription.get("words", [])
    if raw_words:
        result_words = []
        for w in raw_words:
            word_text = w.get("word", "").strip()
            if word_text:
                result_words.append({
                    "word": word_text,
                    "start": float(w.get("start", 0)) + time_offset,
                    "end": float(w.get("end", 0)) + time_offset,
                })
        if result_words:
            logger.info(f"Gladia: 顶层词数组，共 {len(result_words)} 个词")
            return result_words

    # 3. utterances 内按词均分（时间戳锚定在句子级别，词内线性插值）
    if utterances:
        logger.warning("Gladia 未返回词级时间戳，使用句子内均分插值（时间基于 utterance 锚点）")
        result_words = []
        for utt in utterances:
            text = utt.get("text", "").strip()
            utt_start = float(utt.get("start", 0)) + time_offset
            utt_end = float(utt.get("end", 0)) + time_offset
            tokens = text.split() if text else []
            if not tokens:
                continue
            dur = (utt_end - utt_start) / len(tokens)
            for i, tok in enumerate(tokens):
                result_words.append({
                    "word": tok,
                    "start": round(utt_start + i * dur, 3),
                    "end": round(utt_start + (i + 1) * dur, 3),
                })
        if result_words:
            return result_words

    # 4. full_transcript 全局均分（最终保底）
    logger.warning("Gladia: utterances 为空，使用 full_transcript 全局均分")
    full_text = transcription.get("full_transcript", "")
    duration = result_data.get("metadata", {}).get("audio_duration", 60.0)
    tokens = full_text.split()
    if tokens:
        dur_per_tok = duration / len(tokens)
        return [
            {
                "word": tok,
                "start": round(i * dur_per_tok + time_offset, 3),
                "end": round((i + 1) * dur_per_tok + time_offset, 3),
            }
            for i, tok in enumerate(tokens)
        ]

    return []


def transcribe_with_gladia(
    wav_path: str,
    api_key: str,
    language: str = "auto",
    progress_callback=None,
    time_offset: float = 0.0,
) -> dict:
    """
    完整调用 Gladia v2 API：上传 → 提交任务 → 轮询结果 → 提取词级时间戳。

    Args:
        wav_path:          WAV 文件路径
        api_key:           Gladia API Key
        language:          语言代码，"auto" 表示自动检测
        progress_callback: 可选回调 fn(message: str)
        time_offset:       分块处理时的时间戳偏移（秒）

    Returns:
        {"words": [...], "text": str, "language": str}
    """
    if not api_key:
        raise ValueError("未提供 Gladia API Key")

    if progress_callback:
        progress_callback("正在上传音频到 Gladia...")

    # 1. 上传
    audio_url = _gladia_upload_audio(wav_path, api_key)

    if progress_callback:
        progress_callback("音频已上传，正在提交转录任务...")

    # 2. 提交
    result_url = _gladia_submit_transcription(audio_url, api_key, language)

    if progress_callback:
        progress_callback("转录任务已提交，等待结果...")

    # 3. 轮询
    result_data = _gladia_poll_result(result_url, api_key, progress_callback)

    # 4. 提取词
    words = _extract_words_from_gladia(result_data, time_offset)

    # 全文
    full_text = result_data.get("result", {}).get("transcription", {}).get("full_transcript", "")
    detected_lang = result_data.get("result", {}).get("transcription", {}).get("languages", [language])[0] \
        if result_data.get("result", {}).get("transcription", {}).get("languages") else language

    logger.info(f"Gladia 识别完成: {len(words)} 个词，语言={detected_lang}")

    if progress_callback:
        progress_callback(f"识别完成，共 {len(words)} 个词")

    return {
        "words": words,
        "text": full_text,
        "language": detected_lang,
    }


def transcribe_file(
    media_path: str,
    api_key: str,
    language: str = "auto",
    progress_callback=None,
) -> dict:
    """
    完整的识别流程：提取音频 → 分块（如需要）→ 调用 Gladia API → 合并结果。

    Returns:
        {"words": [...], "text": str, "language": str}
    """
    tmp_dir = tempfile.mkdtemp(prefix="gladia_")
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

            result = transcribe_with_gladia(
                wav_path=chunk_path,
                api_key=api_key,
                language=language,
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
        import shutil
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 文案对齐引擎（保留原有逻辑，兼容 Gladia 输出格式）
# ---------------------------------------------------------------------------

def _tokenize(text: str, is_cjk_heavy: bool = False) -> list:
    """将文本分词。"""
    if is_cjk_heavy:
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
    将用户提供的参考文案与识别词级结果对齐，输出带时间戳的词列表。
    支持模糊匹配纠正识别错误的词。

    算法：
    1. 将参考文案分词 → script_tokens
    2. 将识别 words 提取词文本 → asr_tokens
    3. 使用 SequenceMatcher 进行最长公共子序列比对
    4. 对匹配上的词：使用识别时间戳 + 用户文案的原始词（保留大小写/标点）
    5. 对参考文案中多出的词（漏识别）：线性插值补充时间戳
    6. 对识别多出的词（噪声）：丢弃

    Args:
        whisper_words: Gladia/Groq 返回的 [{"word": str, "start": float, "end": float}]
        user_script:   用户输入的参考文案（字符串）

    Returns:
        list of {"word": str, "start": float, "end": float, "aligned": bool}
    """
    if not user_script or not user_script.strip():
        return [
            {"word": w.get("word", ""), "start": w.get("start", 0.0), "end": w.get("end", 0.0), "aligned": True}
            for w in whisper_words
        ]

    if not whisper_words:
        return []

    is_cjk = _detect_cjk(user_script)

    asr_raw = [w.get("word", "").strip() for w in whisper_words]
    asr_tokens = [re.sub(r'[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7ff]', '', t).lower() for t in asr_raw]

    if is_cjk:
        script_chars_raw = list(user_script)
        script_pairs = []
        for ch in script_chars_raw:
            clean = re.sub(r'[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7ff]', '', ch).lower()
            script_pairs.append((ch, clean))
        align_pairs = [(raw, clean) for raw, clean in script_pairs if clean]
        script_tokens_clean = [clean for _, clean in align_pairs]
        script_tokens_raw = [raw for raw, _ in align_pairs]
    else:
        script_words_raw = re.findall(r"[\w']+|[^\w\s]", user_script)
        script_pairs = [(w, re.sub(r'[^\w]', '', w).lower()) for w in script_words_raw]
        align_pairs_all = [(raw, clean) for raw, clean in script_pairs if clean]
        script_tokens_clean = [clean for _, clean in align_pairs_all]
        script_tokens_raw = [raw for raw, _ in align_pairs_all]

    matcher = SequenceMatcher(None, asr_tokens, script_tokens_clean, autojunk=False)
    opcodes = matcher.get_opcodes()

    asr_to_script = {}
    script_to_asr = {}

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for offset in range(i2 - i1):
                asr_to_script[i1 + offset] = j1 + offset
                script_to_asr[j1 + offset] = i1 + offset
        elif tag == "replace":
            pairs = min(i2 - i1, j2 - j1)
            for offset in range(pairs):
                asr_to_script[i1 + offset] = j1 + offset
                script_to_asr[j1 + offset] = i1 + offset

    aligned_words = []
    n_script = len(script_tokens_clean)

    for j in range(n_script):
        raw_word = script_tokens_raw[j]

        if j in script_to_asr:
            asr_idx = script_to_asr[j]
            w = whisper_words[asr_idx]
            aligned_words.append({
                "word": raw_word,
                "start": float(w.get("start", 0)),
                "end": float(w.get("end", 0)),
                "aligned": True,
            })
        else:
            prev_time = None
            next_time = None

            for pj in range(j - 1, -1, -1):
                if pj in script_to_asr:
                    prev_time = float(whisper_words[script_to_asr[pj]].get("end", 0))
                    break

            for nj in range(j + 1, n_script):
                if nj in script_to_asr:
                    next_time = float(whisper_words[script_to_asr[nj]].get("start", 0))
                    break

            if prev_time is not None and next_time is not None:
                gap_words = sum(1 for k in range(j, n_script) if k not in script_to_asr and (
                    (k < min((kk for kk in script_to_asr if kk > j), default=n_script))
                ))
                gap_words = max(gap_words, 1)
                gap = (next_time - prev_time) / (gap_words + 1)
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
                start_t = prev_time + 0.1
                aligned_words.append({
                    "word": raw_word,
                    "start": round(start_t, 3),
                    "end": round(start_t + 0.3, 3),
                    "aligned": False,
                })
            elif next_time is not None:
                start_t = max(0.0, next_time - 0.3)
                aligned_words.append({
                    "word": raw_word,
                    "start": round(start_t, 3),
                    "end": round(next_time, 3),
                    "aligned": False,
                })
            else:
                aligned_words.append({
                    "word": raw_word,
                    "start": 0.0,
                    "end": 0.3,
                    "aligned": False,
                })

    logger.info(
        f"对齐完成: 文案词={n_script}, 识别词={len(whisper_words)}, "
        f"已对齐={sum(1 for w in aligned_words if w['aligned'])}"
    )

    return aligned_words


# ---------------------------------------------------------------------------
# 分段构建 — 使用 SubtitleSegmentBuilder
# ---------------------------------------------------------------------------

def build_segments_with_builder(
    aligned_words: list,
    config: dict = None,
) -> list:
    """
    将词级列表通过 SubtitleSegmentBuilder 分组为字幕 segments。

    分组策略（SubtitleSegmentBuilder 内部实现）：
    1. 遇到句子边界标点（。！？.!?）→ 切断
    2. 词间停顿超过 pause_threshold → 切断
    3. 累计字符数达到 srt_max_chars → 切断

    Args:
        aligned_words: align_transcript_with_script() 的输出
        config:        {'srt_max_chars': 35, 'srt_pause_threshold': 0.3, ...}

    Returns:
        list of {"text": str, "start": float, "end": float}
    """
    if not aligned_words:
        return []

    # 导入 SubtitleSegmentBuilder
    try:
        from .subtitle_builder import SubtitleSegmentBuilder
    except ImportError:
        logger.warning("SubtitleSegmentBuilder 不可用，回退到简单分段")
        return _build_segments_simple(aligned_words, config or {})

    builder = SubtitleSegmentBuilder(config or {})

    # 将 word 列表转为 chars/char_starts/char_ends 格式
    # SubtitleSegmentBuilder 在 standard 模式下支持"词"或"字符"
    chars = []
    char_starts = []
    char_ends = []
    is_cjk = _detect_cjk("".join(w["word"] for w in aligned_words[:20]))

    for word_info in aligned_words:
        word = word_info["word"]
        start = word_info["start"]
        end = word_info["end"]

        # 统一进行字符级分解，以便 Builder 正确识别停顿和分隔符（如空格）
        n = max(len(word), 1)
        dur = (end - start) / n
        
        for i, ch in enumerate(word):
            chars.append(ch)
            char_starts.append(start + i * dur)
            char_ends.append(start + (i + 1) * dur)
        
        # 对于非 CJK，单词间追加空格，以便 Builder 识别词界
        if not is_cjk:
            chars.append(" ")
            char_starts.append(end)
            char_ends.append(end + 0.001)

    return builder.build_segments(chars, char_starts, char_ends)


def _build_segments_simple(aligned_words: list, config: dict) -> list:
    """回退简单分段（当 SubtitleSegmentBuilder 不可用时）。"""
    max_chars = config.get("srt_max_chars", 35)
    pause_threshold = config.get("srt_pause_threshold", 0.3)
    is_cjk = _detect_cjk("".join(w["word"] for w in aligned_words[:20]))

    segments = []
    current_words = []

    def flush():
        if not current_words:
            return
        text = ("" if is_cjk else " ").join(w["word"] for w in current_words)
        segments.append({
            "text": text.strip(),
            "start": current_words[0]["start"],
            "end": current_words[-1]["end"],
        })

    for i, word_info in enumerate(aligned_words):
        word = word_info["word"]

        if current_words:
            prev_end = current_words[-1]["end"]
            if word_info["start"] - prev_end > pause_threshold:
                flush()
                current_words = []

        current_words.append(word_info)
        cur_text = ("" if is_cjk else " ").join(w["word"] for w in current_words)

        if SENTENCE_BOUNDARIES.search(word) or len(cur_text) >= max_chars:
            flush()
            current_words = []

    flush()
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
    """导出 SRT 字幕文件。"""
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
    """导出 Final Cut Pro XML (FCPXML v1.11) 字幕文件。"""
    def to_fcp(secs: float) -> str:
        frames = round(secs * fps)
        return f"{frames}/{int(fps)}s"

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE fcpxml>',
        '<fcpxml version="1.11">',
        '    <resources>',
        f'        <format id="r1" name="FFVideoFormat1080p{int(fps)}" frameDuration="1/{int(fps)}s" width="1920" height="1080" colorSpace="1-1-1 (Rec. 709)"/>',
        '    </resources>',
        '    <library>',
        '        <event name="Gladia Subtitles">',
        '            <project name="Gladia Subtitles">',
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

except ImportError:
    pass
