import re
import string

from .cjk_tokenizer import CJKTokenizer

class SubtitleSegmentBuilder:
    """
    字幕分段生成器：优化版
    解决印尼语长文案不换行、印地语/中文标点过碎的问题。
    """

    def __init__(self, config=None):
        """
        初始化分段生成器
        """
        self.config = config or {}

        # 配置默认值
        self.delimiters = set(
            self.config.get(
                "srt_delimiters",
                [" ", "\n", "।", "？", "?", "!", "！", ",", "，", '"', "“", "”"],
            )
        )
        self.sentence_enders = set(
            self.config.get(
                "srt_sentence_enders",
                [".", "\n", "。", "।", "？", "?", "!", "！", "…"],
            )
        )
        self.max_chars_per_line = self.config.get("srt_max_chars", 35)
        self.pause_threshold = self.config.get("srt_pause_threshold", 0.2)

    def build_segments(self, chars, char_starts, char_ends, word_level=False, words_per_line=1, ignore_line_length=False):
        """
        构建字幕分段入口
        """
        if not chars:
            return []

        if word_level:
            segs = self._build_segments_word_level(
                chars, char_starts, char_ends, words_per_line
            )
        else:
            segs = self._build_segments_standard(chars, char_starts, char_ends, ignore_line_length)

        # 一致化后处理，修复括号、首位标点及超长兜底
        return self._post_process_segments(segs)

    def _build_segments_standard(self, chars, char_starts, char_ends, ignore_line_length=False):
        """
        标准分段模式：改进了长句合并逻辑
        """
        sentences = []
        current_line_text = ""
        current_line_start = None

        for i, char in enumerate(chars):
            if current_line_start is None:
                current_line_start = char_starts[i]

            current_line_text += char

            # 1. 句末标点
            is_sentence_end = char in self.sentence_enders

            # 2. 字符间隔停顿
            is_pause_after = False
            if i < len(chars) - 1:
                gap_time = char_starts[i + 1] - char_ends[i]
                is_pause_after = gap_time >= self.pause_threshold

            # 3. 长度控制
            is_long = False
            if not ignore_line_length:
                # 逻辑：达到阈值且在分隔符处，或长度极其严重超标强制断开
                is_long = (len(current_line_text) >= self.max_chars_per_line and char in self.delimiters) or \
                          (len(current_line_text) >= self.max_chars_per_line * 1.5)

            is_last_char = i == len(chars) - 1

            # 确定分段原因
            reason = None
            if is_sentence_end: reason = "punct"
            elif is_pause_after: reason = "pause"
            elif is_long: reason = "length"
            elif is_last_char: reason = "last"

            if reason:
                clean_text = " ".join(current_line_text.strip().split())
                if clean_text:
                    sentences.append({
                        "text": clean_text,
                        "start": current_line_start,
                        "end": char_ends[i],
                        "reason": reason,
                    })
                current_line_text = ""
                current_line_start = None

        # 合并处理：解决标点过碎
        merged = []
        for seg in sentences:
            if not merged:
                merged.append(seg)
                continue

            prev = merged[-1]
            # 优化合并策略：针对印尼语等拉丁语系，提高字符长度阈值判断
            is_current_very_short = self._should_merge_short(seg["text"])
            
            should_merge = False
            # 如果上一句是以标点结束的硬断句，不合并
            if prev["reason"] != "punct":
                # 如果上一句是因为长度切断的，只有在当前片段极短（如只有标点或1个单词）时才合回
                if prev["reason"] == "length":
                    if len(seg["text"]) < 8: # 针对印尼语单词长度优化的阈值
                        should_merge = True
                else:
                    # 停顿或自然末尾产生的碎块，若符合短句定义则合并
                    if is_current_very_short:
                        should_merge = True

            if should_merge:
                prev["text"] = " ".join((prev["text"] + " " + seg["text"]).split())
                prev["end"] = seg["end"]
                # 合并后更新 reason，如果包含了 punct，则标记为 punct 防止继续被后续合并
                if seg["reason"] == "punct":
                    prev["reason"] = "punct"
            else:
                merged.append(seg)

        for seg in merged:
            seg.pop("reason", None)
        return merged

    def _build_segments_word_level(self, chars, char_starts, char_ends, words_per_line):
        """
        词级分段模式
        """
        words = CJKTokenizer.tokenize_by_cjk(chars, char_starts, char_ends)
        words = self._merge_numeric_with_adjacent(words)
        processed_words = self._merge_punctuation_with_previous(words)

        current_group = []
        segments = []

        for i, word_obj in enumerate(processed_words):
            current_group.append(word_obj)

            is_limit_reached = len(current_group) >= words_per_line
            is_sentence_end = any(ender in word_obj["text"] for ender in self.sentence_enders)
            
            is_pause = False
            if i < len(processed_words) - 1:
                gap_time = processed_words[i + 1]["start"] - word_obj["end"]
                is_pause = gap_time >= self.pause_threshold
            
            is_last = i == len(processed_words) - 1

            if is_limit_reached or is_sentence_end or is_pause or is_last:
                text_content = CJKTokenizer.smart_join(current_group)
                if text_content:
                    segments.append({
                        "text": text_content,
                        "start": current_group[0]["start"],
                        "end": current_group[-1]["end"],
                    })
                current_group = []
        return segments

    def _should_merge_short(self, text):
        """
        判断短句逻辑优化：增加字符长度维度
        """
        words = re.findall(r"\b\w+\b", text)
        # 词数少于等于 2 且 字符数少于 12 时定义为短句
        return len(words) <= 3 or len(text) < 16

    def _merge_punctuation_with_previous(self, words):
        """
        标点不换行处理
        """
        if not words: return words
        punctuation_chars = self.delimiters | self.sentence_enders
        result = []
        for word in words:
            is_punctuation = all(c in punctuation_chars for c in word["text"] if c.strip())
            if is_punctuation and result:
                result[-1]["text"] += word["text"]
                result[-1]["end"] = word["end"]
            else:
                result.append(word)
        return result

    def _merge_numeric_with_adjacent(self, words):
        """
        数字不换行处理
        """
        if not words: return words
        punctuation_chars = set(string.punctuation)
        result = []
        i = 0
        while i < len(words):
            word = words[i]
            if word["text"].isdigit() and i + 1 < len(words):
                nxt = words[i + 1]
                if not all(c in punctuation_chars for c in nxt["text"] if c.strip()):
                    word["text"] += " " + nxt["text"]
                    word["end"] = nxt["end"]
                    result.append(word)
                    i += 2
                    continue
            result.append(word)
            i += 1
        return result

    def _post_process_segments(self, segments):
        """
        后处理：修复括号闭合、首位异常字符、以及超长兜底切分
        """
        if not segments: return []

        # 1. 括号合并
        merged_bracket = []
        depth = 0
        for seg in segments:
            text = seg["text"]
            if merged_bracket and depth > 0:
                merged_bracket[-1]["text"] += " " + text
                merged_bracket[-1]["end"] = seg["end"]
            else:
                merged_bracket.append(seg.copy())
            depth += text.count("(") - text.count(")")

        # 2. 首位字符规范化（首位不出现碎标点）
        final = []
        punctuation_chars = set(string.punctuation) | self.delimiters | self.sentence_enders
        for seg in merged_bracket:
            text = seg["text"]
            if final:
                first = text[0]
                if (first in punctuation_chars or first.isdigit()) and first not in "([{“‘":
                    prev = final[-1]
                    prev["text"] = " ".join((prev["text"] + " " + text).split())
                    prev["end"] = seg["end"]
                    continue
            final.append(seg)

        # 3. 兜底切分：防止合并逻辑导致单行超出 max_chars_per_line 的 1.8 倍
        ultimate_segments = []
        for seg in final:
            if len(seg["text"]) > self.max_chars_per_line * 1.8:
                text = seg["text"]
                mid = len(text) // 2
                space_idx = text.find(" ", mid)
                if space_idx == -1: space_idx = text.rfind(" ", 0, mid)
                
                if space_idx != -1:
                    ratio = space_idx / len(text)
                    split_time = seg["start"] + (seg["end"] - seg["start"]) * ratio
                    ultimate_segments.append({"text": text[:space_idx].strip(), "start": seg["start"], "end": split_time})
                    ultimate_segments.append({"text": text[space_idx:].strip(), "start": split_time, "end": seg["end"]})
                    continue
            ultimate_segments.append(seg)

        # 4. 文本清洗
        for seg in ultimate_segments:
            t = seg["text"]
            t = re.sub(r"\(\s+", "(", t)
            t = re.sub(r"\s+\)", ")", t)
            t = re.sub(r"(\d)\s*:\s*(\d)", r"\1:\2", t)
            seg["text"] = t.strip()
        
        return ultimate_segments

    def reconfigure(self, **kwargs):
        """ 动态配置更新 """
        self.config.update(kwargs)
        self.__init__(self.config)