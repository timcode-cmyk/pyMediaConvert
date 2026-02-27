"""
CJKTokenizer：CJK（汉字、日文、韩文）文本分词工具

职责：
- 识别 CJK 字符与非 CJK 字符的边界
- 将字符序列分组为单词（考虑 CJK 的逐字特性）
- 智能拼接单词（CJK 不加空格，非 CJK 加空格）
- 支持按词数分组和过滤标点
"""

import string
import re


class CJKTokenizer:
    """
    CJK 文本分词器，支持将字符级时间戳转换为词级时间戳
    """

    @staticmethod
    def is_cjk(char):
        """
        判断字符是否为 CJK（汉字、日文、韩文）

        Args:
            char (str): 单个字符

        Returns:
            bool: 如果是 CJK 返回 True

        Examples:
            >>> CJKTokenizer.is_cjk('中')
            True
            >>> CJKTokenizer.is_cjk('a')
            False
        """
        if not char:
            return False
        return "\u4e00" <= char <= "\u9fff"

    @staticmethod
    def tokenize_by_cjk(chars, char_starts, char_ends):
        """
        将字符序列分词，处理 CJK 和非 CJK 字符的混合
        
        改进：标点符号被独立分离（不混入词中），保留时间戳便于后续处理

        Args:
            chars (list): 字符列表
            char_starts (list): 各字符的开始时间（秒）
            char_ends (list): 各字符的结束时间（秒）

        Returns:
            list: 词对象列表，每个词为 dict:
                  {
                      "text": "词",
                      "start": 1.0,
                      "end": 2.0
                  }

        Examples:
            >>> chars = ['中', '文', ' ', 'h', 'i']
            >>> starts = [0, 0.5, 1.0, 1.5, 2.0]
            >>> ends = [0.5, 1.0, 1.0, 2.0, 2.5]
            >>> tokens = CJKTokenizer.tokenize_by_cjk(chars, starts, ends)
            >>> len(tokens)
            2
            >>> tokens[0]['text']
            '中文'
        """
        if not chars:
            return []

        # 标点符号集合（用于分离，而非累积到词中）
        punctuation_chars = (
            set(string.punctuation)
            | set(["。", "，", "！", "？", "、", "；", "：", "“", "”", "‘", "’", "（", "）", "…", "—", "～", "·", "《", "》", "〈", "〉"])
        )

        words = []
        current_word = ""
        word_start = None

        for i, char in enumerate(chars):
            # 标点处理：独立分离（可选保留，便于句末标点检测）
            if char in punctuation_chars:
                # 先保存积累的词
                if current_word:
                    words.append({"text": current_word, "start": word_start, "end": char_starts[i]})
                    current_word = ""
                    word_start = None
                # 将标点作为独立词保存（带时间戳）
                words.append({"text": char, "start": char_starts[i], "end": char_ends[i]})
                continue

            if word_start is None:
                word_start = char_starts[i]

            # CJK 字符：逐字分割
            if CJKTokenizer.is_cjk(char):
                # 先保存之前累积的非 CJK 词
                if current_word:
                    words.append({"text": current_word, "start": word_start, "end": char_starts[i]})
                # 添加当前 CJK 字
                words.append({"text": char, "start": char_starts[i], "end": char_ends[i]})
                current_word = ""
                word_start = None
                continue

            # 非 CJK 字符处理
            if char.strip() == "":
                # 空格：作为单词分隔符
                if current_word:
                    words.append(
                        {
                            "text": current_word,
                            "start": word_start,
                            "end": char_starts[i],
                        }
                    )
                current_word = ""
                word_start = None
            else:
                # 累积非空白字符
                current_word += char
                # 最后一个字符
                if i == len(chars) - 1:
                    words.append({"text": current_word, "start": word_start, "end": char_ends[i]})

        return words

    @staticmethod
    def smart_join(word_objects, words_per_line=1):
        """
        智能拼接词对象列表，返回拼接后的文本

        与旧版本不同，此实现**保留**独立的标点符号（包括括号、冒号等），
        仅在必要时插入空格。之前的逻辑会删除所有标点，导致词级模式下
        引号、括号和数字间隔丢失。

        规则：
        - 保留每个词对象中的标点符号；标点作为独立词时直接附加
        - 清理前后空格与多余内部空格
        - CJK 字符之间不加空格
        - 非 CJK 字符之间加单个空格

        Args:
            word_objects (list): 词对象列表，每个为 {"text": "词", "start": ..., "end": ...}
            words_per_line (int): 每行保留多少个词（用于日志，不影响拼接）

        Returns:
            str: 拼接后的文本
        """
        if not word_objects:
            return ""

        # 标点符号集（中英文）用于识别独立标点词
        punctuation_chars = (
            set(string.punctuation)
            | set(["。", "，", "！", "？", "、", "；", "：", "“", "”", "‘", "’", "（", "）", "…", "—", "～", "·", "《", "》", "〈", "〉"])
        )

        # 先清理每个词的空格
        parts = []
        for word_obj in word_objects:
            txt = word_obj["text"]
            # collapse internal whitespace
            txt = " ".join(txt.split())
            if txt:
                parts.append(txt)

        if not parts:
            return ""

        result = parts[0]
        for txt in parts[1:]:
            prev_char = result[-1] if result else ""
            curr_char = txt[0]
            # 如果当前词是纯标点，则直接附加，无需空格
            if all(c in punctuation_chars for c in txt):
                result += txt
            else:
                is_prev_cjk = CJKTokenizer.is_cjk(prev_char)
                is_curr_cjk = CJKTokenizer.is_cjk(curr_char)
                if not is_prev_cjk and not is_curr_cjk and not (curr_char in punctuation_chars):
                    result += " " + txt
                else:
                    result += txt

        # 后处理：调整常见标点周围的空格
        # 1. 在单词后且未有空格的情况下，在左括号前插入一个空格
        result = re.sub(r"(?<=[^\s\(])\(", r" (", result)
        # 2. 删除左括号后的空格
        result = re.sub(r"\( ", "(", result)
        # 3. 删除数字与冒号之间的空格（保持 "6:14" 形式）
        result = re.sub(r"(\d)\s*:\s*(\d)", r"\1:\2", result)
        # 4. 删除闭合括号前多余空格
        result = re.sub(r"\s+\)", ")", result)
        return result

    @staticmethod
    def group_words(word_objects, words_per_line, sentence_enders, pause_threshold=0.2):
        """
        按词数和句末标点对单词进行分组

        Args:
            word_objects (list): 词对象列表
            words_per_line (int): 每行目标词数
            sentence_enders (set): 句末标点字符集
            pause_threshold (float): 停顿阈值（秒）

        Returns:
            list: 分组后的词组列表，每个为 list of word_objects

        Examples:
            >>> words = [{"text": "hello", "start": 0, "end": 1}, ...]
            >>> groups = CJKTokenizer.group_words(words, 2, {'.', '。'})
            >>> len(groups[0])  # 第一组的词数
        """
        if not word_objects:
            return []

        groups = []
        current_group = []

        for i, word_obj in enumerate(word_objects):
            current_group.append(word_obj)

            # 检查是否需要结束当前组
            is_limit_reached = len(current_group) >= words_per_line
            is_sentence_end = any(ender in word_obj["text"] for ender in sentence_enders)
            is_pause = (i < len(word_objects) - 1) and (word_obj["end"] - word_obj["start"] >= pause_threshold)
            is_last = i == len(word_objects) - 1

            if is_limit_reached or is_sentence_end or is_pause or is_last:
                if current_group:
                    groups.append(current_group)
                current_group = []

        return groups
