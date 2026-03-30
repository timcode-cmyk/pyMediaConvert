"""
TranslationWorker：后台翻译任务，属于核心模块，不属于 UI 逻辑。

职责：
- 将字幕段落聚合为更自然的句子
- 调用 TranslationManager 批量翻译
- 返回翻译后的段落数据

注意：此模块仅负责翻译逻辑，不处理 UI 展示。
"""

from typing import List

from PySide6.QtCore import QObject, Signal

from .translation_manager import TranslationManager
from .whisper_transcription import _detect_cjk, SENTENCE_BOUNDARIES, TRANSLATE_TARGET_LANGUAGES


class TranslationWorker(QObject):
    progress = Signal(str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, segments: list, api_key: str, target_lang: str, parent=None):
        super().__init__(parent)
        self.segments = segments
        self.api_key = api_key
        self.target_lang = target_lang

    def run(self):
        try:
            self.progress.emit("🌍 开始翻译...")
            tm = TranslationManager(api_key=self.api_key)

            grouped = self._group_segments_into_sentences(self.segments)
            if self.target_lang == "zh":
                translated = tm.translate_segments(grouped)
            else:
                translated = self._translate_to_other_language(grouped)

            self.finished.emit(translated)
        except Exception as e:
            self.error.emit(str(e))

    def _group_segments_into_sentences(self, segments: list) -> list:
        sentence_groups = []
        current_group = []
        is_cjk = _detect_cjk("".join(s.get("text", "") for s in segments[:20]))

        def flush_group():
            if not current_group:
                return
            if is_cjk:
                text = "".join(s.get("text", "") for s in current_group)
            else:
                text = " ".join(s.get("text", "") for s in current_group)
            sentence_groups.append({
                "text": text,
                "start": current_group[0].get("start", 0.0),
                "end": current_group[-1].get("end", 0.0),
            })

        for seg in segments:
            current_group.append(seg)
            text = seg.get("text", "").strip()
            total_text = "".join(s.get("text", "") for s in current_group) if is_cjk else " ".join(s.get("text", "") for s in current_group)
            if SENTENCE_BOUNDARIES.search(text[-1:] if text else "") or len(current_group) >= 6 or len(total_text) > 120:
                flush_group()
                current_group = []

        flush_group()
        return sentence_groups

    def _translate_to_other_language(self, groups: list) -> list:
        tm = TranslationManager(api_key=self.api_key)
        translated_groups = []
        batch_size = 20
        lang_name = TRANSLATE_TARGET_LANGUAGES.get(self.target_lang, self.target_lang)

        for i in range(0, len(groups), batch_size):
            batch = groups[i : i + batch_size]
            texts = [f"{idx+1}. {s.get('text','')}" for idx, s in enumerate(batch)]
            sep = "###SEG_SEP###"
            combined = f"\n{sep}\n".join(texts)
            system_prompt = (
                f"You are a professional subtitle translator. "
                f"Translate each numbered segment into {lang_name}, preserving the numbering. "
                f"Segments are separated by '{sep}'. Output only the translated segments separated by '{sep}'."
            )
            result = tm._request_with_retry(system_prompt, combined)
            parts = [p.strip() for p in result.split(sep)] if result else []
            if len(parts) > len(batch) and not parts[-1]:
                parts.pop()

            for j, original in enumerate(batch):
                txt = parts[j] if j < len(parts) else original.get("text", "")
                updated = original.copy()
                updated["text"] = txt
                translated_groups.append(updated)

        return translated_groups
