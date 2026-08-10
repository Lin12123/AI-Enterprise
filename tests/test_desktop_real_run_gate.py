import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_desktop.adapters.core_engine_adapter import CoreEngineAdapter
from ui_desktop.services.job_store import OUTPUT_ROOT, REAL_RUN_CONFIRMATION


def valid_plan() -> dict:
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": "desktop_real_run_part",
        "metadata": {"name": "desktop_real_run_part", "source": "test"},
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


def valid_context(adapter: CoreEngineAdapter, plan: dict | None = None) -> dict:
    plan = plan or valid_plan()
    validation = adapter.validate_plan(plan).data
    return {
        "job_id": "job_20260624_120000",
        "status": "dry_run_passed",
        "validation_result": validation,
        "output_dir": str(OUTPUT_ROOT / "job_20260624_120000"),
    }


class TestDesktopRealRunGate(unittest.TestCase):
    def test_missing_confirmation_rejects_real_run(self):
        adapter = CoreEngineAdapter()
        executor = Mock()

        result = adapter.real_run(valid_plan(), "", valid_context(adapter), executor=executor)

        self.assertFalse(result.ok)
        self.assertIn("confirmation", " ".join(result.data["errors"]))
        executor.assert_not_called()

    def test_wrong_confirmation_rejects_real_run(self):
        adapter = CoreEngineAdapter()
        executor = Mock()

        result = adapter.real_run(valid_plan(), "YES", valid_context(adapter), executor=executor)

        self.assertFalse(result.ok)
        executor.assert_not_called()

    def test_not_dry_run_passed_rejects_real_run(self):
        adapter = CoreEngineAdapter()
        context = valid_context(adapter)
        context["status"] = "validation_passed"

        result = adapter.real_run(valid_plan(), REAL_RUN_CONFIRMATION, context, executor=Mock())

        self.assertFalse(result.ok)
        self.assertTrue(any("dry_run_passed" in error for error in result.data["errors"]))

    def test_blocking_errors_reject_real_run(self):
        adapter = CoreEngineAdapter()
        context = valid_context(adapter)
        context["validation_result"]["blocking_errors"] = ["bad geometry"]

        result = adapter.real_run(valid_plan(), REAL_RUN_CONFIRMATION, context, executor=Mock())

        self.assertFalse(result.ok)
        self.assertTrue(any("blocking_errors" in error for error in result.data["errors"]))

    def test_dangerous_fields_reject_real_run(self):
        adapter = CoreEngineAdapter()
        plan = valid_plan()
        plan["operations"][0]["params"]["script"] = "run me"

        result = adapter.real_run(plan, REAL_RUN_CONFIRMATION, valid_context(adapter), executor=Mock())

        self.assertFalse(result.ok)
        self.assertTrue(any("script" in error.lower() for error in result.data["errors"]))

    def test_unknown_op_rejects_real_run(self):
        adapter = CoreEngineAdapter()
        plan = valid_plan()
        plan["operations"].append({"id": "bad_001", "op": "make_magic_part", "params": {}, "depends_on": []})

        result = adapter.real_run(plan, REAL_RUN_CONFIRMATION, valid_context(adapter), executor=Mock())

        self.assertFalse(result.ok)
        self.assertTrue(any("unknown op" in error.lower() or "make_magic_part" in error for error in result.data["errors"]))

    def test_scaffolded_op_rejects_real_run(self):
        adapter = CoreEngineAdapter()
        plan = valid_plan()
        plan["operations"].append(
            {"id": "rev_001", "op": "create_revolve_boss", "params": {"profile": "p", "axis": "a", "angle": 360}, "depends_on": []}
        )

        result = adapter.real_run(plan, REAL_RUN_CONFIRMATION, valid_context(adapter), executor=Mock())

        self.assertFalse(result.ok)
        self.assertTrue(any("scaffolded" in error.lower() for error in result.data["errors"]))

    def test_planned_op_rejects_real_run(self):
        adapter = CoreEngineAdapter()
        context = valid_context(adapter)
        context["validation_result"]["registry_result"]["capability_status"].append(
            {"id": "future_001", "op": "future_feature", "status": "planned"}
        )

        result = adapter.real_run(valid_plan(), REAL_RUN_CONFIRMATION, context, executor=Mock())

        self.assertFalse(result.ok)
        self.assertTrue(any("planned" in error.lower() for error in result.data["errors"]))

    def test_unsafe_output_path_rejects_real_run(self):
        adapter = CoreEngineAdapter()
        context = valid_context(adapter)
        context["output_dir"] = str(OUTPUT_ROOT.parent / "outside")

        result = adapter.real_run(valid_plan(), REAL_RUN_CONFIRMATION, context, executor=Mock())

        self.assertFalse(result.ok)
        self.assertTrue(any("output_dir" in error for error in result.data["errors"]))

    def test_mock_executor_success_enters_succeeded_without_solidworks(self):
        adapter = CoreEngineAdapter()
        executor = Mock(return_value={"status": "succeeded", "message": "mock executed"})

        with patch("solidworks_api.session.SolidWorksSession.connect", side_effect=AssertionError("connect called")):
            result = adapter.real_run(valid_plan(), REAL_RUN_CONFIRMATION, valid_context(adapter), executor=executor)

        self.assertTrue(result.ok, result.data.get("errors"))
        self.assertEqual(result.status, "succeeded")
        self.assertTrue(result.data["executed"])
        executor.assert_called_once()


if __name__ == "__main__":
    unittest.main()
