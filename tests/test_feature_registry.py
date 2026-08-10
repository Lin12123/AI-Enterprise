import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cad_dsl.feature_registry import default_registry


P0_OPERATIONS = (
    "create_new_part",
    "create_sketch",
    "sketch_center_rectangle",
    "sketch_circle",
    "extrude_boss",
    "extrude_cut",
    "create_through_hole",
    "add_fillet",
    "save_sldprt",
    "export_step",
    "capture_png",
    "rebuild_model",
    "validate_rebuild",
)


class TestFeatureRegistry(unittest.TestCase):
    def test_implemented_operations_are_registered(self):
        registry = default_registry()
        for op in (
            "create_base_plate",
            "cut_corner_holes",
            "create_center_boss",
            "cut_center_hole",
            "add_fillet",
        ):
            definition = registry.require(op)
            self.assertEqual(definition.status, "implemented")
            self.assertTrue(definition.executor_function)
            self.assertTrue(definition.documentation_path)
            self.assertIn("required", definition.parameter_schema)

    def test_scaffolded_operations_are_registered_but_not_implemented(self):
        registry = default_registry()
        for op in (
            "create_revolve_boss",
            "create_sweep_boss",
            "add_shell",
            "create_reference_axis",
        ):
            self.assertEqual(registry.require(op).status, "scaffolded")

    def test_prd_p0_operations_have_registry_schemas(self):
        registry = default_registry()
        for op in P0_OPERATIONS:
            with self.subTest(op=op):
                definition = registry.require(op)
                self.assertEqual(definition.status, "implemented")
                self.assertEqual(definition.parameter_schema.get("type"), "object")
                self.assertIn("required", definition.parameter_schema)
                self.assertIn("properties", definition.parameter_schema)
                self.assertFalse(definition.parameter_schema.get("additionalProperties"))
                self.assertTrue(definition.executor_function)
                self.assertTrue(definition.documentation_path)

    def test_unknown_operation_is_not_registered(self):
        self.assertIsNone(default_registry().get("run_arbitrary_macro"))


if __name__ == "__main__":
    unittest.main()
