import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from doubao_responses import (
    DEFAULT_DOUBAO_MODEL,
    build_translation_input,
    extract_response_text,
)


class FakeOutputText:
    def __init__(self, text):
        self.text = text


class FakeContentItem:
    def __init__(self, text):
        self.type = "output_text"
        self.text = text


class FakeOutputItem:
    def __init__(self, text):
        self.content = [FakeContentItem(text)]


class FakeResponse:
    def __init__(self, output_text=None, output=None):
        self.output_text = output_text
        self.output = output or []


class DoubaoResponsesTests(unittest.TestCase):
    def test_default_model_uses_new_seed_model(self):
        self.assertEqual(DEFAULT_DOUBAO_MODEL, "doubao-seed-2-0-mini-260215")

    def test_build_translation_input_uses_responses_content_blocks(self):
        payload = build_translation_input("Translate like a game namer", "金币")

        self.assertEqual(payload[0]["role"], "system")
        self.assertEqual(payload[0]["content"][0]["type"], "input_text")
        self.assertEqual(payload[0]["content"][0]["text"], "Translate like a game namer")
        self.assertEqual(payload[1]["role"], "user")
        self.assertEqual(payload[1]["content"][0]["type"], "input_text")
        self.assertEqual(payload[1]["content"][0]["text"], "金币")

    def test_extract_response_text_prefers_output_text(self):
        response = FakeResponse(output_text="coin")

        self.assertEqual(extract_response_text(response), "coin")

    def test_extract_response_text_falls_back_to_output_items(self):
        response = FakeResponse(output=[FakeOutputItem("coinPusher")])

        self.assertEqual(extract_response_text(response), "coinPusher")


if __name__ == "__main__":
    unittest.main()
