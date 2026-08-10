import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cad_dsl.feature_registry import default_registry
from solidworks_api.model_builder import DISPATCH


PROJECT_ROOT = Path(__file__).resolve().parents[1]


P1_IMPLEMENTED = {
    "add_chamfer",
    "create_blind_hole",
    "create_counterbore_hole",
    "create_countersink_hole",
    "cut_slot",
    "cut_rectangle_pocket",
    "create_linear_pattern",
    "create_circular_pattern",
    "mirror_feature",
    "set_material",
    "set_custom_property",
    "modify_named_dimension",
    "create_offset_plane",
    "create_axis",
}

P1_REQUIRED_PARAMETERS = {
    "add_chamfer": {"distance"},
    "create_blind_hole": {"plane", "center", "diameter", "depth"},
    "create_counterbore_hole": {"plane", "center", "hole_diameter", "counterbore_diameter", "counterbore_depth"},
    "create_countersink_hole": {"plane", "center", "hole_diameter", "countersink_diameter", "angle"},
    "cut_slot": {"plane", "center", "length", "width"},
    "cut_rectangle_pocket": {"plane", "center", "length", "width", "depth"},
    "create_linear_pattern": {"seed_feature", "direction", "count", "spacing"},
    "create_circular_pattern": {"seed_feature", "axis", "count"},
    "mirror_feature": {"seed_feature", "mirror_plane"},
    "set_material": {"material"},
    "set_custom_property": {"key", "value"},
    "modify_named_dimension": {"dimension_name", "value"},
    "create_offset_plane": {"name", "base_plane", "offset"},
    "create_axis": {"name", "reference_type", "references"},
}


class TestP1FeatureRegistry(unittest.TestCase):
    def test_tc_p1_001_p1_operations_are_registered_with_schema_executor_and_docs(self):
        registry = default_registry()
        for op in P1_IMPLEMENTED:
            with self.subTest(op=op):
                definition = registry.get(op)
                self.assertIsNotNone(definition)
                self.assertEqual(definition.status, "implemented")
                self.assertEqual(definition.parameter_schema.get("type"), "object")
                self.assertIn("required", definition.parameter_schema)
                self.assertTrue(definition.parameter_schema.get("properties"))
                self.assertTrue(definition.executor_function)
                self.assertTrue(definition.documentation_path)
                self.assertIn(op, DISPATCH)
                docs_path = PROJECT_ROOT / definition.documentation_path
                self.assertTrue(docs_path.exists(), definition.documentation_path)
                self.assertIn(op, docs_path.read_text(encoding="utf-8"))

    def test_p1_statuses_are_implemented_after_executor_closure(self):
        registry = default_registry()
        for op in P1_IMPLEMENTED:
            self.assertEqual(registry.require(op).status, "implemented")

    def test_p1_required_parameters_match_contract(self):
        registry = default_registry()
        for op, required in P1_REQUIRED_PARAMETERS.items():
            with self.subTest(op=op):
                self.assertEqual(set(registry.require(op).required_parameters), required)


if __name__ == "__main__":
    unittest.main()
