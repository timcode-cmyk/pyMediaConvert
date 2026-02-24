import unittest
import os
import sys

# make sure project root in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pyMediaTools.core.subtitle_builder import SubtitleSegmentBuilder


class TestSubtitleSegmentBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = SubtitleSegmentBuilder()

    def test_short_segment_merge(self):
        # simulate sequences where the trailing fragment is very short; in the updated logic
        # such pieces will always be merged back into the previous segment.
        for txt in ("Hello world. Hi!", "Hello world! Hi"):
            chars = list(txt)
            starts = [i * 0.1 for i in range(len(chars))]
            ends = [(i + 1) * 0.1 for i in range(len(chars))]
            segments = self.builder.build_segments(chars, starts, ends, word_level=False)
            self.assertEqual(len(segments), 1, f"expected merge for '{txt}'")
            self.assertTrue(segments[0]["text"].endswith(txt.split()[-1]))

    def test_should_merge_short(self):
        self.assertTrue(self.builder._should_merge_short("a b"))
        self.assertTrue(self.builder._should_merge_short("word!"))
        self.assertFalse(self.builder._should_merge_short("This is three"))
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

    def test_no_leading_punctuation(self):
        # segment should not start with comma
        chars = list("Hello , world.")
        starts = [i * 0.1 for i in range(len(chars))]
        ends = [(i + 1) * 0.1 for i in range(len(chars))]
        segs = self.builder.build_segments(chars, starts, ends)
        # should merge comma to previous
        self.assertEqual(len(segs), 1)
        self.assertFalse(segs[0]['text'].startswith(','))

    def test_parentheses_content_stays_together(self):
        text = "Sentence (2 कुरिन्थियों 6:14 देखें)। (©️BSI)।"
        chars = list(text)
        starts = [i * 0.05 for i in range(len(chars))]
        ends = [(i + 1) * 0.05 for i in range(len(chars))]
        segs = self.builder.build_segments(chars, starts, ends)
        # entire string should be one segment
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]['text'], text)

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