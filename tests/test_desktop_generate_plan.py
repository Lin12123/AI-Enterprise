import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_desktop.adapters.core_engine_adapter import CoreEngineAdapter
from ui_desktop.services.job_store import JobStore, OUTPUT_ROOT


SAMPLE_PLAN = {
    "version": "2.0",
    "unit": "mm",
    "document_type": "part",
    "part_name": "adapter_sample",
    "metadata": {"name": "adapter_sample"},
    "operations": [
        {
            "id": "op_001",
            "op": "create_new_part",
            "params": {},
            "depends_on": [],
        }
    ],
    "outputs": {"save_sldprt": True},
}


class TestDesktopGeneratePlan(unittest.TestCase):
    def test_rule_based_provider_generates_real_plan(self):
        adapter = CoreEngineAdapter()
        result = adapter.generate_plan("创建一个 120×80×12mm 的长方体零件。", "rule_based")

        self.assertTrue(result.ok, result.message)
        self.assertIn(result.status, {"planned", "need_user_input"})
        self.assertEqual(result.data["provider"], "rule_based")
        self.assertEqual(result.data["plan"]["unit"], "mm")
        self.assertIsInstance(result.data["plan"].get("operations"), list)

    def test_local_provider_can_be_selected_with_mocked_call(self):
        with patch("app.providers.router.parse_featureplan_with_provider", return_value=SAMPLE_PLAN) as parse_mock:
            result = CoreEngineAdapter().generate_plan("make a local plan", "local")

        self.assertTrue(result.ok, result.message)
        self.assertEqual(result.data["provider"], "local")
        self.assertEqual(result.data["actual_parse_source"], "local")
        self.assertFalse(result.data["parse_info"]["fallback_used"])
        parse_mock.assert_called_once()

    def test_local_provider_fallback_to_rule_based_is_visible_in_parse_info(self):
        def fake_parse(_prompt):
            print("Local LLM unavailable, fallback to rule_based parser. Reason: timeout")
            print("LLM provider: rule_based")
            return SAMPLE_PLAN

        with patch("app.providers.router.parse_featureplan_with_provider", side_effect=fake_parse):
            result = CoreEngineAdapter().generate_plan("make a local plan", "local")

        self.assertTrue(result.ok, result.message)
        self.assertEqual(result.data["provider"], "local")
        self.assertEqual(result.data["actual_parse_source"], "rule_based")
        self.assertTrue(result.data["parse_info"]["fallback_used"])
        self.assertIn("fallback to rule_based parser", result.data["parse_info"]["router_output"])

    def test_openai_provider_can_be_selected_with_mocked_call(self):
        with patch("app.providers.router.parse_featureplan_with_provider", return_value=SAMPLE_PLAN) as parse_mock:
            result = CoreEngineAdapter().generate_plan("make an openai plan", "openai")

        self.assertTrue(result.ok, result.message)
        self.assertEqual(result.data["provider"], "openai")
        parse_mock.assert_called_once()

    def test_invalid_json_or_parser_error_returns_clear_error(self):
        with patch("app.providers.router.parse_featureplan_with_provider", side_effect=ValueError("invalid json")):
            result = CoreEngineAdapter().generate_plan("bad model response", "local")

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "planning_failed")
        self.assertIn("invalid json", result.message)

    def test_generate_plan_writes_candidate_and_input_to_job_dir(self):
        job = JobStore().create_job("create sample", provider="rule_based")

        with patch("app.providers.router.parse_featureplan_with_provider", return_value=SAMPLE_PLAN):
            result = CoreEngineAdapter().generate_plan("create sample", "rule_based", job_id=job.job_id)

        self.assertTrue(result.ok, result.message)
        job_dir = OUTPUT_ROOT / job.job_id
        candidate_path = job_dir / "featureplan_candidate.json"
        input_path = job_dir / "input.txt"
        self.assertTrue(candidate_path.exists())
        self.assertTrue(input_path.exists())
        self.assertIn(OUTPUT_ROOT.resolve(), candidate_path.resolve().parents)
        saved = json.loads(candidate_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["metadata"]["provider"], "rule_based")

    def test_generate_plan_does_not_leak_api_key(self):
        job = JobStore().create_job("placeholder", provider="local")
        prompt = "create part OPENAI_API_KEY=secret-value"

        with patch("app.providers.router.parse_featureplan_with_provider", return_value=SAMPLE_PLAN):
            result = CoreEngineAdapter().generate_plan(prompt, "local", job_id=job.job_id)

        self.assertTrue(result.ok, result.message)
        payload = str(result.to_dict())
        input_text = (OUTPUT_ROOT / job.job_id / "input.txt").read_text(encoding="utf-8")
        candidate_text = (OUTPUT_ROOT / job.job_id / "featureplan_candidate.json").read_text(encoding="utf-8")
        self.assertNotIn("secret-value", payload)
        self.assertNotIn("secret-value", input_text)
        self.assertNotIn("secret-value", candidate_text)


if __name__ == "__main__":
    unittest.main()
