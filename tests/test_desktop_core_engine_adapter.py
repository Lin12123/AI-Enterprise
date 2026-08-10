import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_desktop.adapters.core_engine_adapter import CoreEngineAdapter
from ui_desktop.services.job_store import OUTPUT_ROOT


class TestDesktopCoreEngineAdapter(unittest.TestCase):
    def test_core_engine_adapter_imports(self):
        module = importlib.import_module("ui_desktop.adapters.core_engine_adapter")
        self.assertTrue(hasattr(module, "CoreEngineAdapter"))

    def test_provider_allowlist_accepts_known_providers(self):
        adapter = CoreEngineAdapter()
        sample_plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "sample",
            "operations": [],
            "outputs": {},
        }
        with patch("app.providers.router.parse_featureplan_with_provider", return_value=sample_plan):
            for provider in ("local", "openai", "rule_based"):
                with self.subTest(provider=provider):
                    result = adapter.generate_plan("create a mock part", provider)
                    self.assertTrue(result.ok, result)
                    self.assertEqual(result.data["provider"], provider)

    def test_illegal_provider_is_rejected(self):
        result = CoreEngineAdapter().generate_plan("create a mock part", "bad_provider")

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "invalid_provider")

    def test_get_output_files_rejects_project_external_path(self):
        adapter = CoreEngineAdapter()
        result = adapter.get_output_files("../outside")

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "invalid_output_path")

    def test_get_output_files_stays_under_outputs_jobs(self):
        adapter = CoreEngineAdapter()
        result = adapter.get_output_files("job_20260624_120000")

        self.assertTrue(result.ok)
        for path in result.data["files"].values():
            resolved = Path(path).resolve()
            self.assertIn(OUTPUT_ROOT.resolve(), resolved.parents)

    def test_adapter_does_not_save_or_return_api_key(self):
        sample_plan = {"version": "2.0", "unit": "mm", "document_type": "part", "operations": [], "outputs": {}}
        with patch("app.providers.router.parse_featureplan_with_provider", return_value=sample_plan):
            result = CoreEngineAdapter().generate_plan("make part OPENAI_API_KEY=secret-value", "local")
        payload = str(result.to_dict())

        self.assertNotIn("secret-value", payload)
        self.assertNotIn("OPENAI_API_KEY':", payload)

    def test_app_main_still_imports(self):
        module = importlib.import_module("app.main")
        self.assertIsNotNone(module)

    def test_existing_providers_still_exist(self):
        project_root = Path(__file__).resolve().parents[1]
        for provider_file in (
            "app/providers/openai_provider.py",
            "app/providers/local_provider.py",
            "app/providers/rule_based_provider.py",
        ):
            with self.subTest(provider_file=provider_file):
                self.assertTrue((project_root / provider_file).exists())


if __name__ == "__main__":
    unittest.main()
