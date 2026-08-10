import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.providers.json_utils import extract_json_object
from app.providers.local_provider import DEFAULT_API_KEY, DEFAULT_BASE_URL, DEFAULT_MODEL
from app.providers.router import current_provider_name, parse_featureplan_with_provider


class TestLlmProviderRouter(unittest.TestCase):
    def test_default_provider_is_rule_based(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(current_provider_name(), "rule_based")

    def test_legacy_ai_sw_use_llm_selects_openai(self):
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=True):
            self.assertEqual(current_provider_name(), "openai")

    def test_json_extraction_handles_markdown_and_surrounding_text(self):
        data = extract_json_object('prefix ```json\n{"version":"2.0","operations":[]}\n``` suffix')

        self.assertEqual(data["version"], "2.0")
        self.assertEqual(data["operations"], [])

    def test_unknown_provider_falls_back_to_rule_based_featureplan(self):
        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "unknown"}, clear=True):
            plan = parse_featureplan_with_provider("120x80x12mm")

        self.assertEqual(plan["unit"], "mm")
        self.assertEqual(plan["operations"][0]["op"], "create_base_plate")

    def test_openai_provider_failure_falls_back_to_rule_based(self):
        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "openai"}, clear=True):
            with patch("app.providers.openai_provider.parse_featureplan", side_effect=RuntimeError("quota")):
                plan = parse_featureplan_with_provider("120x80x12mm")

        self.assertEqual(plan["operations"][0]["op"], "create_base_plate")

    def test_local_provider_failure_falls_back_to_rule_based(self):
        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch("app.providers.local_provider.parse_featureplan", side_effect=RuntimeError("ollama down")):
                plan = parse_featureplan_with_provider("120x80x12mm")

        self.assertEqual(plan["operations"][0]["op"], "create_base_plate")

    def test_local_provider_uses_ollama_defaults_without_openai_api_key(self):
        import app.providers.local_provider as local_provider

        captured = {}

        class FakeCompletions:
            def create(self, **kwargs):
                captured.update(kwargs)

                class Message:
                    content = '{"version":"2.0","unit":"mm","document_type":"part","part_name":"test_part","operations":[{"id":"new_001","op":"create_new_part","params":{}}],"outputs":{}}'

                class Choice:
                    message = Message()

                class Response:
                    choices = [Choice()]

                return Response()

        class FakeClient:
            def __init__(self, **kwargs):
                captured["client_kwargs"] = kwargs
                self.chat = type("Chat", (), {"completions": FakeCompletions()})()

        with patch.dict("os.environ", {"AI_SW_LOCAL_LLM_BASE_URL": "", "AI_SW_LOCAL_LLM_MODEL": "", "AI_SW_LOCAL_LLM_API_KEY": "", "OPENAI_API_KEY": ""}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeClient):
                plan = local_provider.parse_featureplan("新建空白零件")

        self.assertEqual(captured["client_kwargs"]["base_url"], DEFAULT_BASE_URL)
        self.assertEqual(captured["client_kwargs"]["api_key"], DEFAULT_API_KEY)
        self.assertEqual(captured["model"], DEFAULT_MODEL)
        self.assertEqual(captured["temperature"], 0)
        self.assertEqual(plan["operations"][0]["op"], "create_new_part")


if __name__ == "__main__":
    unittest.main()
