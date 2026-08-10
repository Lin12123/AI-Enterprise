import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_desktop.adapters.core_engine_adapter import CoreEngineAdapter
from ui_desktop.services.job_store import JobStore, OUTPUT_ROOT


def valid_plan() -> dict:
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": "desktop_dry_run_part",
        "metadata": {"name": "desktop_dry_run_part", "source": "test"},
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


class TestDesktopDryRun(unittest.TestCase):
    def test_cannot_dry_run_without_validation_passed(self):
        result = CoreEngineAdapter().dry_run(valid_plan())

        self.assertFalse(result.ok)
        self.assertFalse(result.data["passed"])
        self.assertTrue(any("validate_plan" in error for error in result.data["errors"]))

    def test_blocking_errors_prevent_dry_run(self):
        adapter = CoreEngineAdapter()
        plan = valid_plan()
        plan["unit"] = "inch"
        validation = adapter.validate_plan(plan).data

        result = adapter.dry_run(plan, validation_result=validation)

        self.assertFalse(result.ok)
        self.assertFalse(result.data["passed"])
        self.assertTrue(result.data["errors"])

    def test_dry_run_does_not_connect_win32com_or_solidworks(self):
        adapter = CoreEngineAdapter()
        plan = valid_plan()
        validation = adapter.validate_plan(plan).data

        with patch("solidworks_api.session.SolidWorksSession.connect", side_effect=AssertionError("connect called")):
            result = adapter.dry_run(plan, validation_result=validation)

        self.assertTrue(result.ok, result.data.get("errors"))
        self.assertFalse(result.data["connected_solidworks"])
        self.assertTrue(result.data["steps"])

    def test_dry_run_files_are_saved_under_outputs_jobs(self):
        adapter = CoreEngineAdapter()
        job = JobStore().create_job("dry run sample", provider="rule_based")
        plan = valid_plan()
        validation = adapter.validate_plan(plan, job_id=job.job_id).data

        result = adapter.dry_run(plan, validation_result=validation, job_id=job.job_id)

        self.assertTrue(result.ok, result.data.get("errors"))
        dry_run_log = OUTPUT_ROOT / job.job_id / "dry_run.log"
        dry_run_result = OUTPUT_ROOT / job.job_id / "dry_run_result.json"
        self.assertTrue(dry_run_log.exists())
        self.assertTrue(dry_run_result.exists())
        self.assertIn(OUTPUT_ROOT.resolve(), dry_run_log.resolve().parents)
        self.assertIn(OUTPUT_ROOT.resolve(), dry_run_result.resolve().parents)
        saved = json.loads(dry_run_result.read_text(encoding="utf-8"))
        self.assertTrue(saved["passed"])
        self.assertTrue(saved["steps"])
        self.assertNotIn("secret-value", dry_run_log.read_text(encoding="utf-8"))

    def test_dry_run_result_does_not_save_api_key(self):
        adapter = CoreEngineAdapter()
        job = JobStore().create_job("OPENAI_API_KEY=secret-value", provider="local")
        plan = valid_plan()
        validation = adapter.validate_plan(plan, job_id=job.job_id).data

        result = adapter.dry_run(plan, validation_result=validation, job_id=job.job_id)

        self.assertTrue(result.ok, result.data.get("errors"))
        payload = str(result.to_dict())
        dry_run_text = (OUTPUT_ROOT / job.job_id / "dry_run_result.json").read_text(encoding="utf-8")
        self.assertNotIn("secret-value", payload)
        self.assertNotIn("secret-value", dry_run_text)


if __name__ == "__main__":
    unittest.main()
