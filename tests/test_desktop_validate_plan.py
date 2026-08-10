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
        "part_name": "desktop_validate_part",
        "metadata": {"name": "desktop_validate_part", "source": "test"},
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


class TestDesktopValidatePlan(unittest.TestCase):
    def test_validate_plan_runs_validation_chain(self):
        result = CoreEngineAdapter().validate_plan(valid_plan())

        self.assertTrue(result.ok, result.data.get("blocking_errors"))
        data = result.data
        self.assertTrue(data["passed"])
        self.assertTrue(data["dependency_result"]["passed"])
        self.assertTrue(data["constraint_result"]["passed"])
        self.assertTrue(data["schema_result"]["passed"])
        self.assertTrue(data["policy_result"]["passed"])
        self.assertEqual(data["execution_order"], ["new_001", "sketch_001", "rect_001", "extrude_001"])

    def test_validate_plan_calls_policy_engine(self):
        with patch("policy.policy_engine.PolicyEngine.validate") as validate_mock:
            validate_mock.return_value.allowed = True
            validate_mock.return_value.violations = ()
            result = CoreEngineAdapter().validate_plan(valid_plan())

        self.assertTrue(result.ok)
        validate_mock.assert_called_once()

    def test_dangerous_fields_are_rejected(self):
        plan = valid_plan()
        plan["operations"][0]["params"]["script"] = "do something"

        result = CoreEngineAdapter().validate_plan(plan)

        self.assertFalse(result.ok)
        self.assertFalse(result.data["can_dry_run"])
        self.assertTrue(any("script" in error.lower() for error in result.data["blocking_errors"]))

    def test_unknown_op_is_rejected(self):
        plan = valid_plan()
        plan["operations"].append({"id": "bad_001", "op": "make_magic_part", "params": {}, "depends_on": []})

        result = CoreEngineAdapter().validate_plan(plan)

        self.assertFalse(result.ok)
        self.assertTrue(any("unknown op" in error.lower() or "make_magic_part" in error for error in result.data["blocking_errors"]))

    def test_missing_reference_is_rejected(self):
        plan = valid_plan()
        plan["operations"][1]["depends_on"] = ["missing_001"]

        result = CoreEngineAdapter().validate_plan(plan)

        self.assertFalse(result.ok)
        self.assertTrue(any("missing" in error.lower() for error in result.data["blocking_errors"]))

    def test_cycle_dependency_is_rejected(self):
        plan = valid_plan()
        plan["operations"][0]["depends_on"] = ["extrude_001"]

        result = CoreEngineAdapter().validate_plan(plan)

        self.assertFalse(result.ok)
        self.assertTrue(any("cyclic" in error.lower() for error in result.data["blocking_errors"]))

    def test_blocking_errors_prevent_dry_run(self):
        plan = valid_plan()
        plan["unit"] = "inch"

        result = CoreEngineAdapter().validate_plan(plan)

        self.assertFalse(result.ok)
        self.assertFalse(result.data["can_dry_run"])
        self.assertTrue(result.data["blocking_errors"])

    def test_validation_result_is_saved_to_job_dir(self):
        job = JobStore().create_job("validate sample", provider="rule_based")
        result = CoreEngineAdapter().validate_plan(valid_plan(), job_id=job.job_id)

        self.assertTrue(result.ok, result.data.get("blocking_errors"))
        validation_path = OUTPUT_ROOT / job.job_id / "validation_result.json"
        self.assertTrue(validation_path.exists())
        self.assertIn(OUTPUT_ROOT.resolve(), validation_path.resolve().parents)
        saved = json.loads(validation_path.read_text(encoding="utf-8"))
        self.assertTrue(saved["passed"])
        self.assertIn("execution_order", saved)

    def test_scaffolded_operation_is_explicitly_marked(self):
        plan = valid_plan()
        plan["operations"].append(
            {
                "id": "rev_001",
                "op": "create_revolve_boss",
                "params": {"profile": "p1", "axis": "a1", "angle": 360},
                "depends_on": [],
            }
        )

        result = CoreEngineAdapter().validate_plan(plan)

        self.assertFalse(result.ok)
        statuses = result.data["registry_result"]["capability_status"]
        self.assertIn({"id": "rev_001", "op": "create_revolve_boss", "status": "scaffolded"}, statuses)

    def test_duplicate_base_plate_and_atomic_base_extrude_are_canonicalized_in_validation(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "duplicate_base_chain",
            "operations": [
                {"id": "base_plate_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
                {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "Top"}},
                {"id": "center_rectangle_001", "op": "sketch_center_rectangle", "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80}},
                {"id": "extrude_boss_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}},
                {"id": "through_hole_001", "op": "create_through_hole", "params": {"plane": "top_face", "center": [-40, 0], "diameter": 6}},
                {"id": "linear_pattern_001", "op": "create_linear_pattern", "params": {"seed_feature": "through_hole_001", "direction": "x", "count": 4, "spacing": 20}},
            ],
            "outputs": {},
        }

        result = CoreEngineAdapter().validate_plan(plan)

        self.assertTrue(result.ok, result.data)
        self.assertEqual(result.data["execution_order"], ["base_plate_001", "through_hole_001", "linear_pattern_001"])

    def test_seed_feature_suffix_reference_is_normalized_for_validation(self):
        plan = valid_plan()
        plan["operations"].extend(
            [
                {
                    "id": "hole_001",
                    "op": "create_through_hole",
                    "params": {"plane": "top_face", "center": [0, 0], "diameter": 6, "through_all": True},
                    "depends_on": ["extrude_001"],
                },
                {
                    "id": "pattern_001",
                    "op": "create_linear_pattern",
                    "params": {"seed_feature": "hole_001.feature_id", "direction": "x", "count": 4, "spacing": 20},
                    "depends_on": ["hole_001"],
                },
            ]
        )

        result = CoreEngineAdapter().validate_plan(plan)

        self.assertTrue(result.ok, result.data.get("blocking_errors"))
        self.assertEqual(result.data["execution_order"][-2:], ["hole_001", "pattern_001"])

    def test_app_main_still_imports(self):
        module = __import__("app.main", fromlist=["main"])
        self.assertIsNotNone(module)


if __name__ == "__main__":
    unittest.main()
