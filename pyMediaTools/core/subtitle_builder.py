"""
SubtitleSegmentBuilder：字幕分段生成器

职责：
- 统一处理标准模式和 word-level 模式的分段逻辑
- 提供灵活的配置参数（标点、停顿阈值等）
- 返回标准的分段列表格式
"""

import re
import string

from .cjk_tokenizer import CJKTokenizer


class SubtitleSegmentBuilder:
    """
    字幕分段生成器，根据不同策略将字符级时间戳转换为句级/词级分段
    """

    def __init__(self, config=None):
        """
        初始化分段生成器

        Args:
            config (dict): 配置字典，支持以下键：
                - srt_delimiters: 行分隔符集（默认 [" ", "\n", "।", "？", "?", "!", "！", ",", "，"]）
                - srt_sentence_enders: 句末标点集（默认 [".", "\n", "。", "।", "？", "?", "!", "！", "…"]；
                - srt_max_chars: 单行最大字符数（默认 35）
                - srt_pause_threshold: 停顿阈值秒数（默认 0.2）
        """
        self.config = config or {}

        # 配置默认值
        self.delimiters = set(
            self.config.get(
                "srt_delimiters",
                [" ", "\n", "।", "？", "?", "!", "！", ",", "，", '"', """, """],
            )
        )
        self.sentence_enders = set(
            self.config.get(
                "srt_sentence_enders",
                [".", "\n", ",", "،", "।", "？", "?", "!", "！", "…"],
            )
        )
        self.max_chars_per_line = self.config.get("srt_max_chars", 35)
        self.pause_threshold = self.config.get("srt_pause_threshold", 0.2)

    def build_segments(self, chars, char_starts, char_ends, word_level=False, words_per_line=1, ignore_line_length=False):
        """
        构建字幕分段

        Args:
            chars (list): 字符列表
            char_starts (list): 各字符的开始时间（秒）
            char_ends (list): 各字符的结束时间（秒）
            word_level (bool): 是否使用逐词模式
                - False（默认）: 按句末标点/停顿分段（标准模式）
                - True: 按词数分组（word-level 模式）
            words_per_line (int): 在 word_level=True 时，每行目标词数（默认 1）
            ignore_line_length (bool): 在标准模式下，是否忽略行长度限制
                - False（默认）: 考虑 max_chars_per_line（用于显示）
                - True: 只按标点/停顿分割，不考虑行长度（用于翻译）

        Returns:
            list: 分段列表，每个分段为 dict:
                  {
                      "text": "分段文本",
                      "start": 1.5,
                      "end": 3.2
                  }
        """
        if not chars:
            return []

        if word_level:
            segs = self._build_segments_word_level(
                chars, char_starts, char_ends, words_per_line
            )
        else:
            segs = self._build_segments_standard(chars, char_starts, char_ends, ignore_line_length)

        # 一致化后处理，修复常见切分问题
        return self._post_process_segments(segs)

    def _build_segments_standard(self, chars, char_starts, char_ends, ignore_line_length=False):
        """
        标准分段模式：按句末标点和停顿分割

        分段条件（优先级递增）：
        1. 当前字符是句末标点
        2. 当前字符后有明显停顿（时长 >= pause_threshold）
        3. 行长已超过 max_chars_per_line 且当前字符是分隔符（仅当 ignore_line_length=False）
        4. 这是最后一个字符

        改进：
        - 使用字符间隔（character gap）而非单个字符时长来检测停顿
        - 停顿 = char_starts[i+1] - char_ends[i]（下一个字符的开始 - 当前字符的结束）
        - 这样可以避免单个长字符（如标点）导致的误判

        Args:
            ignore_line_length (bool): 是否忽略行长度限制
                - False（默认）: 考虑行长度（用于显示）
                - True: 只按标点/停顿分割（用于翻译）

        Returns:
            list: 分段列表
        """
        sentences = []
        current_line_text = ""
        current_line_start = None

        for i, char in enumerate(chars):
            if current_line_start is None:
                current_line_start = char_starts[i]

            current_line_text += char

            # 优先级判断：
            # 1. 标点结束 2. 停顿 3. 超出长度且在分隔符处 4. 最后一个字符
            is_sentence_end = char in self.sentence_enders

            # 停顿基于字符间隔
            is_pause_after = False
            if i < len(chars) - 1:
                gap_time = char_starts[i + 1] - char_ends[i]
                is_pause_after = gap_time >= self.pause_threshold

            is_long_and_at_delimiter = False
            if not ignore_line_length:
                is_long_and_at_delimiter = (
                    len(current_line_text) > self.max_chars_per_line
                ) and (char in self.delimiters)

            is_last_char = i == len(chars) - 1

            # 根据优先级决定是否分段
            if is_sentence_end:
                reason = "punct"
            elif is_pause_after:
                reason = "pause"
            elif is_long_and_at_delimiter:
                reason = "length"
            elif is_last_char:
                reason = "last"
            else:
                reason = None

            if reason:
                clean_text = current_line_text.strip()
                clean_text = " ".join(clean_text.split())
                if clean_text:
                    sentences.append(
                        {
                            "text": clean_text,
                            "start": current_line_start,
                            "end": char_ends[i],
                            "reason": reason,
                        }
                    )
                current_line_text = ""
                current_line_start = None

        # 仅对长度/停顿/末尾产生的短句进行合并，标点分割始终保留
        # 之前的实现合并了所有原因导致的短句，导致多个句子被折叠在一起。
        merged = []
        for seg in sentences:
            # always merge tiny fragments that follow a length-based split
            prev_reason = merged[-1].get("reason") if merged else None
            should_merge = self._should_merge_short(seg["text"])
            if (
                merged
                and should_merge
                and (
                    seg.get("reason") in ("length", "pause", "last")
                    or prev_reason == "length"
                )
            ):
                prev = merged[-1]
                prev["text"] += " " + seg["text"]
                prev["end"] = seg["end"]
            else:
                merged.append(seg)

        # 删除reason字段，后处理不需要它
        for seg in merged:
            seg.pop("reason", None)

        return merged

    def _build_segments_word_level(self, chars, char_starts, char_ends, words_per_line):
        """
        逐词分段模式：先分词，再按词数分组，最后按语句分割

        流程：
        1. 使用 CJKTokenizer 分词（处理 CJK vs 非 CJK 的边界，标点分离）
        2. 按 words_per_line 对词分组
        3. 遇到句末标点/停顿时立即分段
        4. 使用 smart_join 拼接词文本（CJK 不加空格，正确处理标点）

        改进：
        - 在词级而非字符级进行操作，避免单个字符的时长干扰
        - 检查词间的停顿（word[i+1].start - word[i].end）而非词内部的时长
        - 对标点词进行特殊处理（不独占一行，与前一词合并）

        Returns:
            list: 分段列表
        """
        # 第一步：分词
        words = CJKTokenizer.tokenize_by_cjk(chars, char_starts, char_ends)

        # 预处理：数字+字母、标点词与前一词合并（避免数字/标点单独成行）
        words = self._merge_numeric_with_adjacent(words)
        processed_words = self._merge_punctuation_with_previous(words)

        # 第二步：按词数和句末条件分组
        current_group = []
        segments = []

        for i, word_obj in enumerate(processed_words):
            current_group.append(word_obj)

            # 检查分组条件
            is_limit_reached = len(current_group) >= words_per_line
            is_sentence_end = any(ender in word_obj["text"] for ender in self.sentence_enders)
            
            # 检查词间停顿（而非词内时长）
            is_pause = False
            if i < len(processed_words) - 1:
                gap_time = processed_words[i + 1]["start"] - word_obj["end"]
                is_pause = gap_time >= self.pause_threshold
            
            is_last = i == len(processed_words) - 1

            if is_limit_reached or is_sentence_end or is_pause or is_last:
                text_content = CJKTokenizer.smart_join(current_group)
                if text_content:
                    segments.append(
                        {
                            "text": text_content,
                            "start": current_group[0]["start"],
                            "end": current_group[-1]["end"],
                        }
                    )
                current_group = []

        return segments

    def _merge_punctuation_with_previous(self, words):
        """
        将标点词与前一个词合并，避免标点独占一行
        
        Args:
            words (list): 词对象列表
            
        Returns:
            list: 合并后的词列表
        """
        if not words:
            return words
        
        punctuation_chars = set(
            self.config.get(
                "srt_delimiters",
                [" ", "\n", "।", "？", "?", "!", "！", ",", "，", '"', """, """],
            )
        ) | set(
            self.config.get(
                "srt_sentence_enders",
                [".", "\n", "。", "।", "？", "?", "!", "！", "…"],
            )
        )
        
        result = []
        i = 0
        while i < len(words):
            word = words[i]
            
            # 检查是否是纯标点词
            is_punctuation = all(c in punctuation_chars for c in word["text"] if c.strip())
            
            if is_punctuation and result:
                # 将标点合并到前一个词
                prev_word = result[-1]
                prev_word["text"] += word["text"]
                prev_word["end"] = word["end"]
            else:
                result.append(word)
            
            i += 1
        
        return result

    def _should_merge_short(self, text):
        """
        判断一个句子是否足够短，需要和前一句合并。

        规则：文本中单词数量（忽略标点）小于等于 3。
        中文等无空格语言会被当作单词字符，通过正则抓取 \w+。
        """
        words = re.findall(r"\b\w+\b", text)
        # only merge when there are three or fewer words
        return len(words) <= 3

    def _merge_numeric_with_adjacent(self, words):
        """
        将纯数字词与其后的非标点词合并，避免数字与文字之间因为空格而分成独立分段。

        示例：
            [{'text': '2026', ...}, {'text': 'बहनों', ...}] -> [{'text': '2026 बहनों', ...}]
        """
        if not words:
            return words

        punctuation_chars = set(string.punctuation)
        result = []
        i = 0
        while i < len(words):
            word = words[i]
            if word["text"].isdigit() and i + 1 < len(words):
                nxt = words[i + 1]
                # 后一个不是纯标点时合并
                if not all(c in punctuation_chars for c in nxt["text"] if c.strip()):
                    merged = {
                        "text": word["text"] + " " + nxt["text"],
                        "start": word["start"],
                        "end": nxt["end"],
                    }
                    result.append(merged)
                    i += 2
                    continue
            result.append(word)
            i += 1
        return result

    def _post_process_segments(self, segments):
        """
        后处理分段结果以解决各类边缘情况。

        1. 如果分段发生在未闭合的括号内部，则把后续分段合并到前一个，保证括号内容保持整体。
        2. 如果某一行首字符是标点（除了允许的开引号）或数字，则把该行合并到前一行。
        3. 进一步补强：连续标点、数字等不会单独拆行。

        Args:
            segments (list): 初步生成的分段列表
        Returns:
            list: 修正后的分段列表
        """
        if not segments:
            return []

        # 1. 按括号深度合并
        merged = []
        depth = 0
        for seg in segments:
            text = seg["text"]
            if merged and depth > 0:
                merged[-1]["text"] += " " + text
                merged[-1]["end"] = seg["end"]
            else:
                merged.append(seg.copy())
            depth += text.count("(") - text.count(")")

        # 2. 处理首字符是标点或数字的情况
        final = []
        punctuation_chars = set(string.punctuation) | self.delimiters | self.sentence_enders
        for seg in merged:
            text = seg["text"]
            if final:
                first = text[0]
                if (first in punctuation_chars or first.isdigit()):
                    prev = final[-1]
                    # 如果两边均为标点，则不插入空格，否则保留空格以便单词分隔
                    if prev["text"] and prev["text"][-1] in punctuation_chars and first in punctuation_chars:
                        # 当首字符是开括号时，仍保留空格，提高可读性（例如 ")。("）
                        if first in "([{" or first in "（“『":
                            prev["text"] += " " + text
                        else:
                            prev["text"] += text
                    else:
                        prev["text"] += " " + text
                    prev["end"] = seg["end"]
                    continue
            final.append(seg)

        # 最后对每个分段做简单的标点间距规范化
        for seg in final:
            t = seg["text"]
            # 1. 去掉左括号后的空格
            t = re.sub(r"\(\s+", "(", t)
            # 2. 去掉闭合括号前的空格
            t = re.sub(r"\s+\)", ")", t)
            # 3. 数字与冒号间不留空格
            t = re.sub(r"(\d)\s*:\s*(\d)", r"\1:\2", t)
            seg["text"] = t
        return final

    def reconfigure(self, **kwargs):
        """
        动态更新配置参数

        Args:
            **kwargs: 任何支持的配置参数，将覆盖现有值

        Examples:
            >>> builder = SubtitleSegmentBuilder()
            >>> builder.reconfigure(srt_max_chars=50, srt_pause_threshold=0.5)
        """
        self.config.update(kwargs)
        self.delimiters = set(
            self.config.get(
                "srt_delimiters",
                [" ", "\n", "।", "？", "?", "!", "！", ",", "，", '"', """, """],
            )
        )
        self.sentence_enders = set(
            self.config.get(
                "srt_sentence_enders",
                [".", "\n", ",", "，", "।", "？", "?", "!", "！", "…"],
            )
        )
        self.max_chars_per_line = self.config.get("srt_max_chars", 35)
        self.pause_threshold = self.config.get("srt_pause_threshold", 0.2)
