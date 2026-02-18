import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pyMediaTools.core.translation_manager import TranslationManager

class TestTranslationOptimization(unittest.TestCase):
    def setUp(self):
        self.tm = TranslationManager(api_key="test_key")
        self.tm.batch_size = 3  # Small batch size for testing

    @patch('requests.post')
    def test_batching_logic(self, mock_post):
        # Setup mock response for a batch translation
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "翻译1\n---\n翻译2\n---\n翻译3"
                }
            }]
        }
        mock_post.return_value = mock_response

        segments = [
            {"text": "Text 1"},
            {"text": "Text 2"},
            {"text": "Text 3"}
        ]

        translated = self.tm.translate_segments(segments)

        self.assertEqual(len(translated), 3)
        self.assertEqual(translated[0]["text"], "翻译1")
        self.assertEqual(translated[2]["text"], "翻译3")
        # Ensure only 1 API call was made for 3 segments
        self.assertEqual(mock_post.call_count, 1)

    @patch('requests.post')
    @patch('time.sleep', return_value=None)  # Don't actually sleep in tests
    def test_retry_on_429(self, mock_sleep, mock_post):
        # First call returns 429, second returns 200
        mock_429 = MagicMock()
        mock_429.status_code = 429
        
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Success"
                }
            }]
        }
        
        mock_post.side_effect = [mock_429, mock_200]

        result = self.tm._request_with_retry("system", "user")

        self.assertEqual(result, "Success")
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once()

    def test_numbering_alignment(self):
        # verify that numbering prefixes are added and that out-of-order results get re-aligned
        segments = [{"text": "First"}, {"text": "Second"}, {"text": "Third"}]

        # monkey-patch _translate_batch to simulate shuffled output with preserved prefixes
        def fake_translate(batch_texts):
            # ensure numbering prefix exists in the request
            self.assertTrue(batch_texts[0].startswith("1. "))
            self.assertTrue(batch_texts[1].startswith("2. "))
            self.assertTrue(batch_texts[2].startswith("3. "))
            # return results out of order
            return ["2. 第二", "1. 第一", "3. 第三"]
        self.tm._translate_batch = fake_translate

        translated = self.tm.translate_segments(segments)
        self.assertEqual(translated[0]["text"], "第一")
        self.assertEqual(translated[1]["text"], "第二")
        self.assertEqual(translated[2]["text"], "第三")

    def test_missing_index_fallback(self):
        # if the model does not return an index, translations should fall back sequentially
        segments = [{"text": "A"}, {"text": "B"}, {"text": "C"}]
        def fake_translate(batch_texts):
            return ["译A", "译B", "译C"]
        self.tm._translate_batch = fake_translate
        translated = self.tm.translate_segments(segments)
        self.assertEqual(translated[0]["text"], "译A")
        self.assertEqual(translated[1]["text"], "译B")
        self.assertEqual(translated[2]["text"], "译C")

if __name__ == '__main__':
    unittest.main()
