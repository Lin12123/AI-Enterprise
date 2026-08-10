import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cad_dsl.featureplan import FeaturePlan, minimal_mounting_plate_plan


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestFeaturePlanSchema(unittest.TestCase):
    def test_schema_uses_featureplan_v2_shape(self):
        schema = json.loads((PROJECT_ROOT / "src" / "cad_dsl" / "featureplan_schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["version"]["const"], "2.0")
        self.assertEqual(schema["properties"]["unit"]["const"], "mm")
        self.assertIn("document_type", schema["required"])
        self.assertIn("part_name", schema["required"])
        operation_properties = schema["properties"]["operations"]["items"]["properties"]
        self.assertIn("op", operation_properties)
        self.assertIn("params", operation_properties)
        operation_required = schema["properties"]["operations"]["items"]["required"]
        self.assertIn("id", operation_required)
        self.assertIn("op", operation_required)
        self.assertIn("params", operation_required)

    def test_schema_outputs_do_not_allow_output_dir(self):
        schema = json.loads((PROJECT_ROOT / "src" / "cad_dsl" / "featureplan_schema.json").read_text(encoding="utf-8"))
        outputs_schema = schema["properties"]["outputs"]
        self.assertFalse(outputs_schema["additionalProperties"])
        self.assertNotIn("output_dir", outputs_schema["properties"])

    def test_featureplan_from_requested_shape(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "ai_part_001",
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12}}
            ],
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
        }
        plan = FeaturePlan.from_dict(data)
        self.assertEqual(plan.part_name, "ai_part_001")
        self.assertEqual(plan.operations[0].op, "create_base_plate")
        self.assertEqual(plan.operations[0].params["length"], 120)
        self.assertTrue(plan.outputs["save_sldprt"])

    def test_minimal_plan_is_v2_part_plan(self):
        plan = minimal_mounting_plate_plan()
        self.assertEqual(plan.version, "2.0")
        self.assertEqual(plan.unit, "mm")
        self.assertEqual(plan.document_type, "part")
        self.assertEqual(plan.operations[0].op, "create_base_plate")


if __name__ == "__main__":
    unittest.main()
