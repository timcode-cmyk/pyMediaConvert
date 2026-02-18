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
        # simulate a sequence of characters forming two segments where second is very short
        chars = list("Hello world. Hi!")
        # fake timings: each char 0.1s start->end
        starts = [i * 0.1 for i in range(len(chars))]
        ends = [(i + 1) * 0.1 for i in range(len(chars))]

        segments = self.builder.build_segments(chars, starts, ends, word_level=False)
        # without merge, we would expect ['Hello world.', 'Hi!'] but since 'Hi!' is <=2 words and
        # previous sentence ends with '.' which is a sentence ender; the merging should not occur.
        self.assertEqual(len(segments), 2)

        # now change text to produce a short second piece without ender on first
        chars2 = list("Hello world! Hi")
        starts2 = [i * 0.1 for i in range(len(chars2))]
        ends2 = [(i + 1) * 0.1 for i in range(len(chars2))]
        seg2 = self.builder.build_segments(chars2, starts2, ends2, word_level=False)
        # now 'Hi' should merge with previous segment because it's only one word and previous ends with '!'
        self.assertEqual(len(seg2), 1)
        self.assertTrue(seg2[0]["text"].endswith("Hi"))

    def test_should_merge_short(self):
        self.assertTrue(self.builder._should_merge_short("a b"))
        self.assertTrue(self.builder._should_merge_short("word!"))
        self.assertFalse(self.builder._should_merge_short("This is three"))
        self.assertTrue(self.builder._should_merge_short("。"))  # punctuation only

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