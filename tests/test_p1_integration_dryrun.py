import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.job_writer import write_job_ini
from app.validator import validate_cadplan
from cad_dsl.feature_registry import default_registry
from solidworks_api.executor import SolidWorksApiExecutor
from solidworks_api.session import SolidWorksSession


class GuardedSession(SolidWorksSession):
    def __init__(self):
        super().__init__()
        self.connect_called = False

    def connect(self) -> None:
        self.connect_called = True
        raise AssertionError("dry_run must not connect to SolidWorks")


def plan_for(operations, part_name="p1_tc"):
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": part_name,
        "operations": operations,
        "outputs": {"save_sldprt": False, "export_step": False, "capture_png": False},
    }


def atomic_base_ops():
    return [
        {"id": "new_001", "op": "create_new_part", "params": {}},
        {"id": "sketch_001", "op": "create_sketch", "params": {"name": "sketch_base", "plane": "Top"}},
        {
            "id": "rect_001",
            "op": "sketch_center_rectangle",
            "params": {"sketch": "sketch_base", "center": [0, 0], "length": 100, "width": 60},
        },
        {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "sketch_base", "depth": 10}},
    ]


def dry_run(plan):
    session = GuardedSession()
    result = SolidWorksApiExecutor(session=session).dry_run(plan)
    return result, session


class TestP1IntegrationDryRun(unittest.TestCase):
    def assert_dry_run(self, plan):
        result, session = dry_run(plan)
        self.assertEqual(result.status, "dry_run", result)
        self.assertFalse(session.connect_called)
        return result

    def assert_blocked(self, plan, expected_text):
        result, session = dry_run(plan)
        self.assertEqual(result.status, "blocked", result)
        self.assertFalse(session.connect_called)
        messages = " | ".join(operation.message for operation in result.operations)
        self.assertIn(expected_text, messages)
        return result

    def test_tc_p1_002_chamfer_dry_run_passes(self):
        operations = atomic_base_ops() + [
            {"id": "chamfer_001", "op": "add_chamfer", "params": {"distance": 2, "angle": 45, "target": "outer_edges"}},
            {"id": "rebuild_001", "op": "rebuild_model", "params": {}},
            {"id": "validate_001", "op": "validate_rebuild", "params": {}},
        ]
        self.assert_dry_run(plan_for(operations, "tc_p1_002_chamfer"))

    def test_tc_p1_003_invalid_chamfer_parameters_are_rejected(self):
        cases = [
            {"distance": 0, "angle": 45, "target": "outer_edges"},
            {"distance": -1, "angle": 45, "target": "outer_edges"},
            {"distance": 2, "angle": 0, "target": "outer_edges"},
            {"distance": 2, "angle": 90, "target": "outer_edges"},
            {"distance": 2, "angle": 45, "target": "some_edges"},
        ]
        for params in cases:
            with self.subTest(params=params):
                self.assert_blocked(
                    plan_for([{"id": "chamfer_001", "op": "add_chamfer", "params": params}]),
                    "add_chamfer",
                )

    def test_tc_p1_004_blind_hole_dry_run_passes(self):
        self.assert_dry_run(
            plan_for(
                atomic_base_ops()
                + [{"id": "blind_001", "op": "create_blind_hole", "params": {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": 5}}],
                "tc_p1_004_blind_hole",
            )
        )

    def test_tc_p1_005_invalid_blind_hole_parameters_are_rejected(self):
        for params in (
            {"plane": "top_face", "center": [0, 0], "diameter": 0, "depth": 5},
            {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": 0},
        ):
            with self.subTest(params=params):
                self.assert_blocked(plan_for([{"id": "blind_001", "op": "create_blind_hole", "params": params}]), "必须大于 0")

    def test_tc_p1_006_counterbore_hole_dry_run_passes(self):
        self.assert_dry_run(
            plan_for(
                atomic_base_ops()
                + [
                    {
                        "id": "cbore_001",
                        "op": "create_counterbore_hole",
                        "params": {"plane": "top_face", "center": [0, 0], "hole_diameter": 6.6, "counterbore_diameter": 12, "counterbore_depth": 4},
                    }
                ],
                "tc_p1_006_counterbore",
            )
        )

    def test_tc_p1_007_countersink_hole_dry_run_passes(self):
        self.assert_dry_run(
            plan_for(
                atomic_base_ops()
                + [
                    {
                        "id": "csink_001",
                        "op": "create_countersink_hole",
                        "params": {"plane": "top_face", "center": [0, 0], "hole_diameter": 6.6, "countersink_diameter": 12, "angle": 90},
                    }
                ],
                "tc_p1_007_countersink",
            )
        )

    def test_tc_p1_008_slot_cut_dry_run_passes(self):
        self.assert_dry_run(
            plan_for(
                atomic_base_ops()
                + [{"id": "slot_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [0, 0], "length": 30, "width": 8, "through_all": False, "depth": 5}}],
                "tc_p1_008_slot",
            )
        )

    def test_tc_p1_009_rectangle_pocket_dry_run_passes(self):
        self.assert_dry_run(
            plan_for(
                atomic_base_ops()
                + [{"id": "pocket_001", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [20, 0], "length": 35, "width": 18, "depth": 4}}],
                "tc_p1_009_pocket",
            )
        )

    def test_tc_p1_010_linear_pattern_dry_run_passes(self):
        self.assert_dry_run(
            plan_for(
                atomic_base_ops()
                + [
                    {"id": "blind_001", "op": "create_blind_hole", "params": {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": 5}},
                    {"id": "linear_001", "op": "create_linear_pattern", "params": {"seed_feature": "blind_001", "direction": "x", "count": 3, "spacing": 20}},
                ],
                "tc_p1_010_linear",
            )
        )

    def test_tc_p1_011_circular_pattern_dry_run_passes(self):
        self.assert_dry_run(
            plan_for(
                atomic_base_ops()
                + [
                    {"id": "blind_001", "op": "create_blind_hole", "params": {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": 5}},
                    {"id": "axis_001", "op": "create_axis", "params": {"name": "Axis_01", "reference_type": "two_planes", "references": ["Front", "Right"]}},
                    {"id": "circular_001", "op": "create_circular_pattern", "params": {"seed_feature": "blind_001", "axis": "Axis_01", "count": 6, "angle": 360}},
                ],
                "tc_p1_011_circular",
            )
        )

    def test_tc_p1_012_mirror_feature_dry_run_passes(self):
        self.assert_dry_run(
            plan_for(
                atomic_base_ops()
                + [
                    {"id": "pocket_001", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [20, 0], "length": 35, "width": 18, "depth": 4}},
                    {"id": "mirror_001", "op": "mirror_feature", "params": {"seed_feature": "pocket_001", "mirror_plane": "Front"}},
                ],
                "tc_p1_012_mirror",
            )
        )

    def test_tc_p1_013_material_allowlist_dry_run_and_rejection(self):
        self.assert_dry_run(plan_for([{"id": "mat_001", "op": "set_material", "params": {"material": "6061 Alloy"}}], "tc_p1_013_material"))
        self.assert_dry_run(plan_for([{"id": "mat_001", "op": "set_material", "params": {"material_id": "Aluminum_6061"}}], "tc_p1_013_material_id"))
        self.assert_blocked(plan_for([{"id": "mat_001", "op": "set_material", "params": {"material": "Titanium_Freeform"}}]), "官方 SOLIDWORKS 材料库")

    def test_tc_p1_014_custom_property_allowlist_dry_run_and_rejection(self):
        self.assert_dry_run(plan_for([{"id": "prop_001", "op": "set_custom_property", "params": {"key": "PartNumber", "value": "P-001"}}], "tc_p1_014_property"))
        self.assert_blocked(plan_for([{"id": "prop_001", "op": "set_custom_property", "params": {"key": "UnsafeKey", "value": "P-001"}}]), "允许字段")

    def test_tc_p1_015_modify_named_dimension_dry_run_and_rejection(self):
        self.assert_dry_run(plan_for([{"id": "dim_001", "op": "modify_named_dimension", "params": {"dimension_name": "D_base_length", "value": 150}}], "tc_p1_015_dimension"))
        self.assert_blocked(plan_for([{"id": "dim_001", "op": "modify_named_dimension", "params": {"dimension_name": "D_unknown", "value": 150}}]), "尺寸白名单")
        self.assert_blocked(plan_for([{"id": "dim_001", "op": "modify_named_dimension", "params": {"dimension_name": "D_base_length", "value": 0}}]), "必须大于 0")

    def test_tc_p1_016_offset_plane_dry_run_and_uniqueness_rejection(self):
        self.assert_dry_run(plan_for([{"id": "plane_001", "op": "create_offset_plane", "params": {"name": "Plane_Offset_01", "base_plane": "Top", "offset": 25}}], "tc_p1_016_plane"))
        self.assert_blocked(plan_for([{"id": "plane_001", "op": "create_offset_plane", "params": {"name": "Plane_Offset_01", "base_plane": "Top", "offset": 0}}]), "offset")
        self.assert_blocked(
            plan_for(
                [
                    {"id": "plane_001", "op": "create_offset_plane", "params": {"name": "Plane_Dupe", "base_plane": "Top", "offset": 25}},
                    {"id": "axis_001", "op": "create_axis", "params": {"name": "Plane_Dupe", "reference_type": "two_planes", "references": ["Front", "Right"]}},
                ]
            ),
            "唯一",
        )

    def test_tc_p1_017_create_axis_dry_run_and_reference_rejection(self):
        self.assert_dry_run(plan_for([{"id": "axis_001", "op": "create_axis", "params": {"name": "Axis_01", "reference_type": "two_planes", "references": ["Front", "Right"]}}], "tc_p1_017_axis"))
        self.assert_blocked(plan_for([{"id": "axis_001", "op": "create_axis", "params": {"name": "Axis_01", "reference_type": "two_planes", "references": ["auto", "Right"]}}]), "模糊引用")

    def test_tc_p1_018_dangerous_fields_are_rejected_recursively_in_p1_params(self):
        forbidden = (
            "output_dir",
            "path",
            "file_path",
            "save_path",
            "script",
            "macro",
            "command",
            "python_code",
            "vba_code",
            "powershell",
            "shell",
            "subprocess",
            "delete",
            "remove",
            "overwrite",
        )
        for key in forbidden:
            with self.subTest(key=key):
                params = {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": 5, "nested": {key: "blocked"}}
                self.assert_blocked(plan_for([{"id": "blind_001", "op": "create_blind_hole", "params": params}]), "禁止")

    def test_tc_p1_019_p2_p3_or_unknown_capabilities_cannot_execute(self):
        cases = [
            ("create_sweep_boss", {"profile": "profile_001", "path": "path_001"}),
            ("create_loft_boss", {"profiles": ["profile_001", "profile_002"]}),
            ("add_shell", {"thickness": 2}),
            ("add_rib", {"profile": "profile_001", "thickness": 2}),
            ("add_draft", {"angle": 2, "target": "outer_faces"}),
            ("split_body", {"tool": "Plane_01"}),
            ("combine_bodies", {"bodies": ["body_1", "body_2"]}),
        ]
        registry = default_registry()
        for op, params in cases:
            with self.subTest(op=op):
                definition = registry.get(op)
                if definition is not None:
                    self.assertNotEqual(definition.status, "implemented")
                result, session = dry_run(plan_for([{"id": "op_001", "op": op, "params": params}]))
                self.assertEqual(result.status, "blocked")
                self.assertFalse(session.connect_called)

    def test_tc_p1_020_full_p1_featureplan_dry_run_passes_without_outputs(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "p1_full_dryrun",
            "operations": atomic_base_ops()
            + [
                {"id": "blind_001", "op": "create_blind_hole", "params": {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": 5}},
                {"id": "slot_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [-20, 0], "length": 30, "width": 8, "through_all": False, "depth": 5}},
                {"id": "pocket_001", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [20, 0], "length": 35, "width": 18, "depth": 4}},
                {"id": "chamfer_001", "op": "add_chamfer", "params": {"distance": 2, "angle": 45, "target": "outer_edges"}},
                {"id": "linear_001", "op": "create_linear_pattern", "params": {"seed_feature": "blind_001", "direction": "x", "count": 3, "spacing": 20}},
                {"id": "mat_001", "op": "set_material", "params": {"material": "6061 Alloy"}},
                {"id": "prop_001", "op": "set_custom_property", "params": {"key": "PartNumber", "value": "P1-FULL"}},
                {"id": "rebuild_001", "op": "rebuild_model", "params": {}},
                {"id": "validate_001", "op": "validate_rebuild", "params": {}},
                {"id": "save_001", "op": "save_sldprt", "params": {}},
                {"id": "step_001", "op": "export_step", "params": {}},
                {"id": "png_001", "op": "capture_png", "params": {}},
            ],
            "outputs": {"save_sldprt": False, "export_step": False, "capture_png": False},
        }
        result = self.assert_dry_run(plan)
        self.assertEqual(result.outputs, ())

    def test_p0_dry_run_still_passes(self):
        p0_plan = plan_for(
            [
                {"id": "new_001", "op": "create_new_part", "params": {}},
                {"id": "sketch_base", "op": "create_sketch", "params": {"name": "sketch_base", "plane": "Top"}},
                {"id": "rect_001", "op": "sketch_center_rectangle", "params": {"sketch": "sketch_base", "center": [0, 0], "length": 120, "width": 80}},
                {"id": "base_001", "op": "extrude_boss", "params": {"sketch": "sketch_base", "depth": 12}},
                {"id": "sketch_cut", "op": "create_sketch", "params": {"name": "sketch_cut", "plane": "top_face"}},
                {"id": "circle_001", "op": "sketch_circle", "params": {"sketch": "sketch_cut", "center": [0, 0], "diameter": 10}},
                {"id": "cut_001", "op": "extrude_cut", "params": {"sketch": "sketch_cut", "through_all": True}},
                {"id": "fillet_001", "op": "add_fillet", "params": {"radius": 2, "target": "outer_edges"}},
                {"id": "rebuild_001", "op": "rebuild_model", "params": {}},
                {"id": "validate_001", "op": "validate_rebuild", "params": {}},
            ],
            "p0_regression_dryrun",
        )
        self.assert_dry_run(p0_plan)

    def test_legacy_vba_current_job_ini_flow_still_works_without_macro(self):
        cadplan = validate_cadplan(
            {
                "template": "mounting_plate",
                "unit": "mm",
                "part_name": "legacy_regression",
                "base": {"length": 120, "width": 80, "thickness": 12},
                "outputs": {"save_sldprt": True, "export_step": False, "capture_png": False},
            }
        )
        job_path = write_job_ini(cadplan)
        text = job_path.read_text(encoding="utf-8")
        self.assertTrue(str(job_path).endswith(r"workspace\jobs\current_job.ini"))
        self.assertIn("template=mounting_plate", text)
        self.assertIn("base_length=120", text)
        self.assertNotIn("script", text)
        self.assertNotIn("macro", text)


if __name__ == "__main__":
    unittest.main()
