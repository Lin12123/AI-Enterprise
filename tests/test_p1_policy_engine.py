import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy.policy_engine import PolicyEngine


def plan_with(operation):
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": "p1_policy",
        "operations": [
            {"id": "new_001", "op": "create_new_part", "params": {}},
            operation,
        ],
        "outputs": {"save_sldprt": True, "export_step": False, "capture_png": False},
    }


class TestP1PolicyEngine(unittest.TestCase):
    def validate(self, operation):
        return PolicyEngine().validate(plan_with(operation))

    def test_p1_implemented_blind_hole_is_allowed(self):
        result = self.validate(
            {
                "id": "blind_001",
                "op": "create_blind_hole",
                "params": {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": 5},
            }
        )
        self.assertTrue(result.allowed, result.violations)

    def test_p1_implemented_rectangle_pocket_is_allowed(self):
        result = self.validate(
            {
                "id": "pocket_001",
                "op": "cut_rectangle_pocket",
                "params": {"plane": "top_face", "center": [0, 0], "length": 40, "width": 20, "depth": 4},
            }
        )
        self.assertTrue(result.allowed, result.violations)

    def test_all_p1_operations_with_valid_parameters_are_allowed(self):
        for op, params in {
            "add_chamfer": {"distance": 2, "angle": 45, "target": "outer_edges"},
            "create_counterbore_hole": {
                "plane": "top_face",
                "center": [0, 0],
                "hole_diameter": 6,
                "counterbore_diameter": 12,
                "counterbore_depth": 3,
            },
            "create_countersink_hole": {
                "plane": "top_face",
                "center": [0, 0],
                "hole_diameter": 6,
                "countersink_diameter": 12,
                "angle": 90,
            },
            "cut_slot": {"plane": "top_face", "center": [0, 0], "length": 30, "width": 8, "direction": "x", "through_all": False, "depth": 5},
            "create_linear_pattern": {"seed_feature": "blind_001", "direction": "x", "count": 3, "spacing": 20},
            "create_circular_pattern": {"seed_feature": "blind_001", "axis": "center_axis", "count": 6, "angle": 360},
            "mirror_feature": {"seed_feature": "pocket_001", "mirror_plane": "Front"},
            "set_material": {"material": "6061 Alloy"},
            "set_custom_property": {"key": "PartNumber", "value": "P-001"},
            "modify_named_dimension": {"dimension_name": "D_base_length", "value": 150},
            "create_offset_plane": {"name": "Plane_Offset_01", "base_plane": "Top", "offset": 25},
            "create_axis": {"name": "Axis_01", "reference_type": "two_planes", "references": ["Front", "Right"]},
        }.items():
            with self.subTest(op=op):
                result = self.validate({"id": "op_001", "op": op, "params": params})
                self.assertTrue(result.allowed, result.violations)

    def test_p1_illegal_parameters_are_rejected(self):
        cases = [
            ("create_blind_hole", {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": -1}, "depth"),
            ("add_chamfer", {"distance": 2, "angle": 120, "target": "outer_edges"}, "angle"),
            ("cut_slot", {"plane": "top_face", "center": [0, 0], "length": 8, "width": 10}, "length"),
            ("cut_slot", {"plane": "top_face", "center": [0, 0], "length": 30, "width": 8, "direction": "diag"}, "direction"),
            ("cut_rectangle_pocket", {"plane": "top_face", "center": [0, 0], "length": 40, "width": 20, "depth": 0}, "depth"),
            ("create_linear_pattern", {"seed_feature": "h1", "direction": "x", "count": 1, "spacing": 20}, "count"),
            ("create_linear_pattern", {"seed_feature": "h1", "direction": "x", "count": 3, "spacing": 0}, "spacing"),
            ("create_linear_pattern", {"seed_feature": "auto", "direction": "x", "count": 3, "spacing": 20}, "seed_feature"),
            ("mirror_feature", {"seed_feature": "h1", "mirror_plane": "some_face"}, "mirror_plane"),
            ("set_material", {"material": "UnknownMaterial"}, "material"),
            ("set_custom_property", {"key": "unsafe_key", "value": "x"}, "key"),
            ("modify_named_dimension", {"dimension_name": "D_everything", "value": 1}, "dimension_name"),
            ("create_offset_plane", {"name": "Plane_Offset_01", "base_plane": "Top", "offset": 0}, "offset"),
            ("create_axis", {"name": "Axis_01", "reference_type": "two_planes", "references": ["Front"]}, "references"),
        ]
        for op, params, expected in cases:
            with self.subTest(op=op, expected=expected):
                result = self.validate({"id": "bad_001", "op": op, "params": params})
                self.assertFalse(result.allowed)
                self.assertTrue(any(expected in v.message for v in result.violations))

    def test_dangerous_fields_still_rejected(self):
        plan = plan_with(
            {
                "id": "blind_001",
                "op": "create_blind_hole",
                "params": {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": 5, "script": "bad"},
            }
        )
        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any(v.code in {"file_safety", "parameters"} for v in result.violations))

    def test_description_custom_property_key_is_not_misclassified_as_script(self):
        result = self.validate(
            {
                "id": "prop_001",
                "op": "set_custom_property",
                "params": {"key": "Description", "value": "P1 API test part"},
            }
        )

        self.assertTrue(result.allowed, result.violations)

    def test_material_id_satisfies_set_material_required_catalog_parameter(self):
        result = self.validate(
            {
                "id": "mat_001",
                "op": "set_material",
                "params": {"material_id": "Aluminum_6061"},
            }
        )

        self.assertTrue(result.allowed, result.violations)

    def test_script_custom_property_key_is_still_rejected(self):
        result = self.validate(
            {
                "id": "prop_001",
                "op": "set_custom_property",
                "params": {"key": "script", "value": "bad"},
            }
        )

        self.assertFalse(result.allowed)
        self.assertTrue(any(v.code in {"file_safety", "geometry"} for v in result.violations), result.violations)

    def test_linear_pattern_cannot_use_cut_center_hole_as_seed_feature(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "pattern_seed_guard",
            "operations": [
                {
                    "id": "base_001",
                    "op": "create_base_plate",
                    "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"},
                },
                {
                    "id": "center_hole_001",
                    "op": "cut_center_hole",
                    "params": {"diameter": 6, "target": "base"},
                },
                {
                    "id": "pattern_001",
                    "op": "create_linear_pattern",
                    "params": {"seed_feature": "center_hole_001", "direction": "x", "count": 4, "spacing": 20},
                },
            ],
            "outputs": {},
        }

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any("cut_center_hole" in v.message and "seed_feature" in v.message for v in result.violations), result.violations)


if __name__ == "__main__":
    unittest.main()
