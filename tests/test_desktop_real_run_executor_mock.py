import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_desktop.adapters.core_engine_adapter import CoreEngineAdapter
from ui_desktop.services.job_store import OUTPUT_ROOT, REAL_RUN_CONFIRMATION


def valid_plan() -> dict:
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": "desktop_executor_part",
        "metadata": {"name": "desktop_executor_part", "source": "test"},
        "operations": [
            {"id": "new_001", "op": "create_new_part", "params": {}, "depends_on": []},
            {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "Top"}, "depends_on": ["new_001"]},
            {
                "id": "rect_001",
                "op": "sketch_center_rectangle",
                "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
                "depends_on": ["sketch_001"],
            },
            {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}, "depends_on": ["rect_001"]},
        ],
        "outputs": {"save_sldprt": True},
    }


def context(adapter: CoreEngineAdapter, job_id: str, plan: dict) -> dict:
    return {
        "job_id": job_id,
        "status": "dry_run_passed",
        "validation_result": adapter.validate_plan(plan).data,
        "output_dir": str(OUTPUT_ROOT / job_id),
    }


class TestDesktopRealRunExecutorMock(unittest.TestCase):
    def test_mock_executor_success_returns_succeeded(self):
        adapter = CoreEngineAdapter()
        job_id = "job_20260624_140001"
        plan = valid_plan()

        with patch("solidworks_api.session.SolidWorksSession.connect", side_effect=AssertionError("connect called")):
            result = adapter.real_run(
                plan,
                REAL_RUN_CONFIRMATION,
                context(adapter, job_id, plan),
                executor=lambda _plan, _context: {"status": "succeeded", "message": "mock ok", "outputs": [str(OUTPUT_ROOT / job_id / "part.SLDPRT")]},
            )

        self.assertTrue(result.ok, result.data.get("errors"))
        self.assertEqual(result.status, "succeeded")

    def test_executor_exception_returns_failed_and_saves_log(self):
        adapter = CoreEngineAdapter()
        job_id = "job_20260624_140002"
        plan = valid_plan()

        def executor(_plan, _context):
            raise RuntimeError("mock executor failed")

        result = adapter.real_run(plan, REAL_RUN_CONFIRMATION, context(adapter, job_id, plan), executor=executor)

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "failed")
        self.assertTrue((OUTPUT_ROOT / job_id / "execution.log").exists())
        self.assertTrue((OUTPUT_ROOT / job_id / "outputs.json").exists())

    def test_cli_and_providers_are_not_broken(self):
        self.assertIsNotNone(importlib.import_module("app.main"))
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "app" / "providers" / "openai_provider.py").exists())
        self.assertTrue((root / "app" / "providers" / "local_provider.py").exists())
        self.assertTrue((root / "app" / "providers" / "rule_based_provider.py").exists())


if __name__ == "__main__":
    unittest.main()
