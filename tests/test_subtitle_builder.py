import unittest
import os
import sys

# make sure project root in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pyMediaTools.core.subtitle_builder import SubtitleSegmentBuilder


class TestSubtitleSegmentBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = SubtitleSegmentBuilder()

    def test_length_based_short_merge(self):
        # 在行长控制下，未超过 1.8x 兜底限制的短尾部片段应自动向前回并，避免产生碎片
        self.builder.reconfigure(srt_max_chars=15)
        txt = "hello world this is"
        chars = list(txt)
        starts = [i * 0.1 for i in range(len(chars))]
        ends = [(i + 1) * 0.1 for i in range(len(chars))]
        segments = self.builder.build_segments(chars, starts, ends, word_level=False)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["text"], "hello world this is")

        # 若整体确实超过 max_chars * 1.8，兜底切分应生效以避免单行过长
        self.builder.reconfigure(srt_max_chars=5)
        segments_fallback = self.builder.build_segments(chars, starts, ends, word_level=False)
        self.assertEqual(len(segments_fallback), 2)

    def test_punctuation_splits_are_respected(self):
        # sentence-ending punctuation (period, exclamation, question, etc.)
        # causes a break; we do not merge across a boundary marked by
        # sentence_enders.
        txt = "Hello world. Hi!"
        chars = list(txt)
        starts = [i * 0.1 for i in range(len(chars))]
        ends = [(i + 1) * 0.1 for i in range(len(chars))]
        segments = self.builder.build_segments(chars, starts, ends, word_level=False)
        self.assertEqual(len(segments), 2)
        self.assertTrue(segments[1]["text"].startswith("Hi"))

    def test_should_merge_short(self):
        # threshold is <=3 words (or short CJK string)
        self.assertTrue(self.builder._should_merge_short("a b"))
        self.assertTrue(self.builder._should_merge_short("word!"))
        self.assertTrue(self.builder._should_merge_short("This is three"))
        self.assertFalse(self.builder._should_merge_short("This is four words"))
        self.assertTrue(self.builder._should_merge_short("。"))  # punctuation only

    def test_consecutive_punctuation_dont_split(self):
        # two punctuation marks in a row (question + quote) should not produce two segments
        chars = list("Hello?\"World")
        starts = [i * 0.1 for i in range(len(chars))]
        ends = [(i + 1) * 0.1 for i in range(len(chars))]
        segs = self.builder.build_segments(chars, starts, ends)
        # only one segment, the quote never ends up as a separate segment
        self.assertEqual(len(segs), 1)
        self.assertTrue(segs[0]['text'].endswith('"World'))

    def test_comma_splits_sentence(self):
        # 逗号是 delimiter（软分隔符），而非 sentence_ender（硬句末标点）：
        # 短句内部不会因为逗号碎裂，只有在超出 max_chars 时才会在逗号处优先断行。
        chars = list("Hello , world.")
        starts = [i * 0.1 for i in range(len(chars))]
        ends = [(i + 1) * 0.1 for i in range(len(chars))]
        segs_short = self.builder.build_segments(chars, starts, ends)
        self.assertEqual(len(segs_short), 1)

        long_txt = "This is an even longer opening clause, followed by another long clause."
        l_chars = list(long_txt)
        l_starts = [i * 0.05 for i in range(len(l_chars))]
        l_ends = [(i + 1) * 0.05 for i in range(len(l_chars))]
        segs_long = self.builder.build_segments(l_chars, l_starts, l_ends)
        self.assertEqual(len(segs_long), 2)
        self.assertTrue(segs_long[0]["text"].endswith(","))
        self.assertTrue(segs_long[1]["text"].startswith("followed"))

    def test_parentheses_content_stays_together(self):
        text = "Sentence (2 कुरिन्थियों 6:14 देखें)।"
        chars = list(text)
        starts = [i * 0.05 for i in range(len(chars))]
        ends = [(i + 1) * 0.05 for i in range(len(chars))]
        segs = self.builder.build_segments(chars, starts, ends)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["text"], text)

    def test_numeric_word_merge(self):
        # word_level segmentation with a space between number and word should still combine
        chars = list("2026 बहनों")
        starts = [i * 0.05 for i in range(len(chars))]
        ends = [(i + 1) * 0.05 for i in range(len(chars))]
        segs = self.builder.build_segments(chars, starts, ends, word_level=True, words_per_line=1)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]['text'], "2026 बहनों")

    def test_word_level_parentheses_merge(self):
        # word-level mode should also treat the entire parentheses citation as one segment
        text = "Sentence (2 कुरिन्थियों 6:14 देखें)।"
        chars = list(text)
        starts = [i * 0.05 for i in range(len(chars))]
        ends = [(i + 1) * 0.05 for i in range(len(chars))]
        segs = self.builder.build_segments(chars, starts, ends, word_level=True, words_per_line=2)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["text"], text)

    def test_pause_short_merge(self):
        # a long pause should trigger a split, but a short fragment after it
        # must be folded back unless ended by punctuation.
        txt = "this is a test"
        chars = list(txt)
        starts = [i * 0.1 for i in range(len(chars))]
        ends = [(i + 1) * 0.1 for i in range(len(chars))]
        # insert a long gap before the final word to simulate a pause
        pause_index = txt.index("t")  # first letter of "test"
        starts[pause_index] = ends[pause_index - 1] + 1.0
        segs = self.builder.build_segments(chars, starts, ends)
        # should not split into ["this is a", "test"]; the short tail merges
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["text"], txt)

    def test_two_sentences_not_combined(self):
        # 两句话在句末句号边界应保持分离，不会被错误合并
        txt = (
            "mata air itu muncul dari tempat yang kering, retak, dan tampaknya tanpa harapan. "
            "Samson meminum air itu, kekuatannya dipulihkan, dan imannya dikuatkan."
        )
        chars = list(txt)
        starts = [i * 0.05 for i in range(len(chars))]
        ends = [(i + 1) * 0.05 for i in range(len(chars))]
        segs = self.builder.build_segments(chars, starts, ends)
        self.assertGreaterEqual(len(segs), 2)
        self.assertTrue(any(s["text"].strip().endswith("harapan.") for s in segs))
        self.assertTrue(any(s["text"].strip().startswith("Samson") for s in segs))
        self.assertFalse(any("harapan. Samson" in s["text"] for s in segs))
        self.assertFalse(any(s["text"].strip() == "kering," for s in segs))

    def test_ignore_line_length_flag(self):
        # verify ignore_line_length disables splitting by max_chars_per_line
        long_text = "x" * 50 + "."
        chars = list(long_text)
        starts = [i * 0.05 for i in range(len(chars))]
        ends = [(i + 1) * 0.05 for i in range(len(chars))]
        segs = self.builder.build_segments(chars, starts, ends, word_level=False, ignore_line_length=True)
        self.assertEqual(len(segs), 1)

if __name__ == '__main__':
    unittest.main()