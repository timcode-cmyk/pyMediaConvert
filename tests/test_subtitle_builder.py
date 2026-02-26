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
        # when a break is triggered purely by exceeding max_chars, any short
        # trailing fragment (<=3 words) should be folded back into the
        # previous segment. after the recent rule change we merge on length
        # as well, so only one segment remains.
        self.builder.reconfigure(srt_max_chars=5)
        txt = "hello world this is"
        chars = list(txt)
        starts = [i * 0.1 for i in range(len(chars))]
        ends = [(i + 1) * 0.1 for i in range(len(chars))]
        segments = self.builder.build_segments(chars, starts, ends, word_level=False)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["text"], "hello world this is")

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
        # Comma is now a sentence ender; it should cause a break before the
        # following text unless the fragment gets merged back due to being
        # short. Here both sides are nontrivial and remain separate.
        chars = list("Hello , world.")
        starts = [i * 0.1 for i in range(len(chars))]
        ends = [(i + 1) * 0.1 for i in range(len(chars))]
        segs = self.builder.build_segments(chars, starts, ends)
        self.assertEqual(len(segs), 2)
        self.assertTrue(segs[0]['text'].endswith(","))
        self.assertTrue(segs[1]['text'].startswith("world"))

    def test_parentheses_content_stays_together(self):
        text = "Sentence (2 कुरिन्थियों 6:14 देखें)। (©️BSI)।"
        chars = list(text)
        starts = [i * 0.05 for i in range(len(chars))]
        ends = [(i + 1) * 0.05 for i in range(len(chars))]
        segs = self.builder.build_segments(chars, starts, ends)
        # entire string should be one segment
        # also verify spacing around parentheses is preserved
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
        # two sentences separated by a period should remain in separate
        # segments even if internal commas also split. we merely assert that
        # a boundary occurs at the period and that at least two segments exist.
        txt = (
            "mata air itu muncul dari tempat yang kering, retak, dan tampaknya tanpa harapan. "
            "Samson meminum air itu, kekuatannya dipulihkan, dan imannya dikuatkan."
        )
        chars = list(txt)
        starts = [i * 0.05 for i in range(len(chars))]
        ends = [(i + 1) * 0.05 for i in range(len(chars))]
        segs = self.builder.build_segments(chars, starts, ends)
        self.assertGreaterEqual(len(segs), 2)
        # ensure the first sentence isn't artificially split by length
        self.assertTrue(any("tempat yang kering" in s["text"] for s in segs))
        # confirm there is a segment ending with the first sentence
        # check there is a segment ending with the period of the first sentence
        self.assertTrue(any(s["text"].strip().endswith("harapan.") for s in segs))
        self.assertTrue(any(s["text"].strip().startswith("Samson") for s in segs))
        # also verify that tiny comma fragments were not left alone
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