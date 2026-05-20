import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from doubao_responses import (
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_DOUBAO_MODEL,
    build_chat_messages,
    build_translation_input,
    extract_chat_completion_text,
    extract_response_text,
    summarize_response,
    summarize_chat_completion_response,
)


class FakeOutputText:
    def __init__(self, text):
        self.text = text


class FakeContentItem:
    def __init__(self, text):
        self.type = "output_text"
        self.text = text


class FakeOutputItem:
    def __init__(self, text, output_type="message"):
        self.type = output_type
        self.content = [FakeContentItem(text)]


class FakeResponse:
    def __init__(self, output_text=None, output=None):
        self.output_text = output_text
        self.output = output or []


class FakeMessage:
    def __init__(self, content, reasoning_content=""):
        self.content = content
        self.reasoning_content = reasoning_content


class FakeChoice:
    def __init__(self, content, reasoning_content="", finish_reason="stop"):
        self.message = FakeMessage(content, reasoning_content)
        self.finish_reason = finish_reason


class FakeChatCompletionResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class DoubaoResponsesTests(unittest.TestCase):
    def test_default_model_uses_new_seed_model(self):
        self.assertEqual(DEFAULT_DOUBAO_MODEL, "doubao-seed-2-0-mini-260215")

    def test_default_deepseek_model_uses_v4_flash(self):
        self.assertEqual(DEFAULT_DEEPSEEK_MODEL, "deepseek-v4-flash")

    def test_build_translation_input_uses_responses_content_blocks(self):
        payload = build_translation_input("Translate like a game namer", "金币")

        self.assertEqual(payload[0]["role"], "system")
        self.assertEqual(payload[0]["content"][0]["type"], "input_text")
        self.assertEqual(payload[0]["content"][0]["text"], "Translate like a game namer")
        self.assertEqual(payload[1]["role"], "user")
        self.assertEqual(payload[1]["content"][0]["type"], "input_text")
        self.assertEqual(payload[1]["content"][0]["text"], "金币")

    def test_build_chat_messages_uses_openai_chat_format(self):
        payload = build_chat_messages("Translate like a game namer", "金币")

        self.assertEqual(payload[0], {"role": "system", "content": "Translate like a game namer"})
        self.assertEqual(payload[1], {"role": "user", "content": "金币"})

    def test_extract_response_text_prefers_output_text(self):
        response = FakeResponse(output_text="coin")

        self.assertEqual(extract_response_text(response), "coin")

    def test_extract_response_text_falls_back_to_output_items(self):
        response = FakeResponse(output=[FakeOutputItem("coinPusher")])

        self.assertEqual(extract_response_text(response), "coinPusher")

    def test_extract_response_text_reads_dict_output_items(self):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "countryChair",
                        }
                    ],
                }
            ]
        }

        self.assertEqual(extract_response_text(response), "countryChair")

    def test_extract_response_text_reads_top_level_output_text_dict(self):
        response = {"output_text": "countryChair"}

        self.assertEqual(extract_response_text(response), "countryChair")

    def test_extract_chat_completion_text_reads_first_message(self):
        response = FakeChatCompletionResponse("coin")

        self.assertEqual(extract_chat_completion_text(response), "coin")

    def test_extract_chat_completion_text_reads_dict_response(self):
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "countryChair",
                    },
                    "finish_reason": "stop",
                }
            ]
        }

        self.assertEqual(extract_chat_completion_text(response), "countryChair")

    def test_extract_chat_completion_text_ignores_reasoning_content(self):
        response = FakeChatCompletionResponse("")
        response.choices[0].message.reasoning_content = "countryChair"

        self.assertEqual(extract_chat_completion_text(response), "")

    def test_summarize_chat_completion_response_reports_empty_content(self):
        response = FakeChatCompletionResponse("")

        summary = summarize_chat_completion_response(response)

        self.assertIn("finish_reason=stop", summary)
        self.assertIn("content_preview=''", summary)

    def test_summarize_response_reports_output_content(self):
        response = FakeResponse(output=[FakeOutputItem("countryChair")])

        summary = summarize_response(response)

        self.assertIn("message[output_text:countryChair]", summary)


if __name__ == "__main__":
    unittest.main()
