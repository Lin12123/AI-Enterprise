import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_desktop.adapters.core_engine_adapter import CoreEngineAdapter
from ui_desktop.services.job_store import OUTPUT_ROOT, REAL_RUN_CONFIRMATION


def valid_plan() -> dict:
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": "desktop_output_part",
        "metadata": {"name": "desktop_output_part", "source": "test"},
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


class TestDesktopOutputFiles(unittest.TestCase):
    def test_execution_log_and_outputs_json_are_saved(self):
        adapter = CoreEngineAdapter()
        job_id = "job_20260624_130001"
        job_dir = OUTPUT_ROOT / job_id
        plan = valid_plan()

        def executor(_plan, _context):
            return {
                "status": "succeeded",
                "message": "mock executed",
                "outputs": [
                    str(job_dir / "part.SLDPRT"),
                    str(job_dir / "part.STEP"),
                    str(job_dir / "part.PNG"),
                ],
            }

        result = adapter.real_run(plan, REAL_RUN_CONFIRMATION, context(adapter, job_id, plan), executor=executor)

        self.assertTrue(result.ok, result.data.get("errors"))
        execution_log = job_dir / "execution.log"
        outputs_json = job_dir / "outputs.json"
        self.assertTrue(execution_log.exists())
        self.assertTrue(outputs_json.exists())
        saved = json.loads(outputs_json.read_text(encoding="utf-8"))
        self.assertEqual(saved["files"]["sldprt"], str(job_dir / "part.SLDPRT"))
        self.assertEqual(saved["files"]["step"], str(job_dir / "part.STEP"))
        self.assertEqual(saved["files"]["png"], str(job_dir / "part.PNG"))

    def test_outputs_paths_are_under_outputs_jobs(self):
        job_id = "job_20260624_130002"
        job_dir = OUTPUT_ROOT / job_id
        adapter = CoreEngineAdapter()
        plan = valid_plan()

        result = adapter.real_run(
            plan,
            REAL_RUN_CONFIRMATION,
            context(adapter, job_id, plan),
            executor=lambda _plan, _context: {"status": "succeeded", "message": "ok", "outputs": [str(job_dir / "part.SLDPRT")]},
        )

        self.assertTrue(result.ok, result.data.get("errors"))
        outputs_json = job_dir / "outputs.json"
        saved = json.loads(outputs_json.read_text(encoding="utf-8"))
        for value in saved["files"].values():
            resolved = Path(value).resolve()
            self.assertTrue(resolved == OUTPUT_ROOT.resolve() or OUTPUT_ROOT.resolve() in resolved.parents)


if __name__ == "__main__":
    unittest.main()
