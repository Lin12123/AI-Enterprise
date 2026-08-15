import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cad_dsl.feature_registry import FeatureDefinition, FeatureRegistry, default_registry
from policy.policy_engine import PolicyEngine
from solidworks_api.executor import SolidWorksApiExecutor


def valid_plan():
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": "ai_part_001",
        "operations": [
            {
                "id": "base_001",
                "op": "create_base_plate",
                "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"},
            },
            {
                "id": "hole_001",
                "op": "cut_corner_holes",
                "params": {"diameter": 6.6, "offset_x": 15, "offset_y": 15, "through_all": True},
            },
            {
                "id": "boss_001",
                "op": "create_center_boss",
                "params": {"diameter": 30, "height": 25, "plane": "top_face"},
            },
            {"id": "hole_002", "op": "cut_center_hole", "params": {"diameter": 10, "target": "boss", "through_all": True}},
            {"id": "fillet_001", "op": "add_fillet", "params": {"radius": 3, "target": "outer_edges"}},
        ],
        "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
    }


def complete_p0_plan():
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": "p0_complete_part",
        "operations": [
            {"id": "op_001", "op": "create_new_part", "params": {}},
            {"id": "op_002", "op": "create_sketch", "params": {"name": "sketch_base", "plane": "Top"}},
            {
                "id": "op_003",
                "op": "sketch_center_rectangle",
                "params": {"sketch": "sketch_base", "center": [0, 0], "length": 120, "width": 80},
            },
            {"id": "op_004", "op": "extrude_boss", "params": {"sketch": "sketch_base", "depth": 12}},
            {
                "id": "op_005",
                "op": "create_through_hole",
                "params": {"plane": "top_face", "center": [0, 0], "diameter": 10},
            },
            {"id": "op_006", "op": "add_fillet", "params": {"radius": 2, "target": "outer_edges"}},
            {"id": "op_007", "op": "rebuild_model", "params": {}},
            {"id": "op_008", "op": "validate_rebuild", "params": {}},
            {"id": "op_009", "op": "save_sldprt", "params": {}},
            {"id": "op_010", "op": "export_step", "params": {}},
            {"id": "op_011", "op": "capture_png", "params": {}},
        ],
        "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
    }


class TestPolicyEngine(unittest.TestCase):
    def test_valid_implemented_plan_is_allowed(self):
        result = PolicyEngine().validate(valid_plan())
        self.assertTrue(result.allowed, result.violations)

    def test_corner_holes_can_use_edge_margin(self):
        plan = valid_plan()
        plan["operations"][1]["params"] = {"diameter": 6.6, "edge_margin": 10, "through_all": True}

        result = PolicyEngine().validate(plan)

        self.assertTrue(result.allowed, result.violations)

    def test_corner_holes_reject_missing_location(self):
        plan = valid_plan()
        plan["operations"][1]["params"] = {"diameter": 6.6, "through_all": True}

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any("edge_margin" in violation.message or "offset" in violation.message for violation in result.violations))

    def test_center_hole_can_use_depth(self):
        plan = valid_plan()
        plan["operations"][3]["params"] = {"diameter": 10, "target": "boss", "depth": 37, "through_all": False}

        result = PolicyEngine().validate(plan)

        self.assertTrue(result.allowed, result.violations)

    def test_center_hole_rejects_invalid_target(self):
        plan = valid_plan()
        plan["operations"][3]["params"] = {"diameter": 10, "target": "platform", "depth": 37}

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any("target" in violation.message for violation in result.violations))

    def test_center_hole_rejects_invalid_depth(self):
        plan = valid_plan()
        plan["operations"][3]["params"] = {"diameter": 10, "target": "boss", "depth": 0, "through_all": False}

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any("depth" in violation.message for violation in result.violations))

    def test_scaffolded_operation_is_not_executable(self):
        plan = valid_plan()
        plan["operations"] = [{"id": "revolve_001", "op": "create_revolve_boss", "params": {"profile": "profile_001", "axis": "axis_001", "angle": 360}}]
        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("scaffolded" in violation.message and "不能执行" in violation.message for violation in result.violations))

    def test_tc_p0_002_scaffolded_revolve_boss_cannot_execute(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "bad_part",
            "operations": [
                {
                    "id": "op_001",
                    "op": "create_revolve_boss",
                    "params": {"profile": "profile_001", "axis": "axis_001", "angle": 360},
                }
            ],
        }

        definition = default_registry().require("create_revolve_boss")
        self.assertIn(definition.status, {"scaffolded", "planned"})

        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(
            any(
                marker in violation.message
                for violation in result.violations
                for marker in ("not implemented", "scaffolded", "未实现", "不可执行", "涓嶈兘鎵ц")
            ),
            result.violations,
        )

        dry_run_result = SolidWorksApiExecutor().dry_run(plan)
        self.assertEqual(dry_run_result.status, "blocked")
        self.assertTrue(dry_run_result.operations)

    def test_tc_p0_003_unknown_operation_must_be_rejected(self):
        plan = valid_plan()
        plan["operations"] = [{"id": "op_001", "op": "make_magic_part", "params": {}}]

        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("未知" in v.message or "鏈煡" in v.message for v in result.violations))

        dry_run_result = SolidWorksApiExecutor().dry_run(plan)
        self.assertEqual(dry_run_result.status, "blocked")

    def test_tc_p0_004_top_level_output_dir_must_be_rejected(self):
        plan = valid_plan()
        plan["output_dir"] = "workspace/outputs"

        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("output_dir" in v.message for v in result.violations))

    def test_tc_p0_005_nested_path_fields_must_be_rejected(self):
        for field in ("save_path", "path", "file_path"):
            with self.subTest(field=field):
                plan = valid_plan()
                plan["operations"][0]["params"] = {"length": 120, "width": 80, "thickness": 12, field: "bad"}
                result = PolicyEngine().validate(plan)
                self.assertFalse(result.allowed)
                self.assertTrue(any(field in v.message for v in result.violations))

    def test_tc_p0_006_script_command_macro_fields_must_be_rejected(self):
        dangerous_fields = (
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
        for field in dangerous_fields:
            with self.subTest(field=field):
                plan = valid_plan()
                plan["operations"][0]["params"][field] = "bad"
                result = PolicyEngine().validate(plan)
                self.assertFalse(result.allowed)
                self.assertTrue(any(field in v.message for v in result.violations))

    def test_tc_p0_007_unit_must_be_mm(self):
        plan = valid_plan()
        plan["unit"] = "inch"

        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("unit" in v.message and "mm" in v.message for v in result.violations))

    def test_rectangular_slot_edge_distance_boundary_reports_center_when_size_fits(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "slot_boundary_case",
            "metadata": {"inferred_parameters": [], "explicit_parameters": []},
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "slot_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [60, 0], "length": 40, "width": 10, "through_all": True}},
            ],
            "outputs": {},
        }

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any("slot_001.params.center" in violation.message for violation in result.violations), result.violations)
        self.assertFalse(any("slot_001.params.length" in violation.message for violation in result.violations), result.violations)

    def test_rectangular_slot_oversize_reports_length_when_span_exceeds_base(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "slot_oversize_case",
            "metadata": {"inferred_parameters": [], "explicit_parameters": []},
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "slot_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [0, 0], "length": 140, "width": 10, "through_all": True}},
            ],
            "outputs": {},
        }

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any("slot_001.params.length" in violation.message for violation in result.violations), result.violations)

    def test_tc_p0_008_negative_or_zero_dimensions_must_be_rejected(self):
        for depth in (-12, 0):
            with self.subTest(depth=depth):
                plan = complete_p0_plan()
                plan["operations"] = [{"id": "op_001", "op": "extrude_boss", "params": {"sketch": "s1", "depth": depth}}]
                result = PolicyEngine().validate(plan)
                self.assertFalse(result.allowed)
                self.assertTrue(any("depth" in v.message or "尺寸" in v.message or "灏哄" in v.message for v in result.violations))

    def test_tc_p0_009_operation_missing_id_must_be_rejected(self):
        plan = valid_plan()
        plan["operations"] = [{"op": "create_sketch", "params": {"name": "sketch_base", "plane": "Top"}}]

        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("id" in v.message for v in result.violations))

    def test_tc_p0_011_complete_p0_featureplan_dry_run_passes(self):
        plan = complete_p0_plan()

        policy_result = PolicyEngine().validate(plan)
        self.assertTrue(policy_result.allowed, policy_result.violations)

        dry_run_result = SolidWorksApiExecutor().dry_run(plan)
        self.assertEqual(dry_run_result.status, "dry_run")
        self.assertEqual(len(dry_run_result.operations), len(plan["operations"]))
        self.assertTrue(all(operation.status == "planned" for operation in dry_run_result.operations))

    def test_offcenter_hole_on_base_must_stay_inside_base_boundary(self):
        plan = complete_p0_plan()
        plan["operations"] = [
            {"id": "new_001", "op": "create_new_part", "params": {}},
            {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "top_face"}},
            {
                "id": "rect_001",
                "op": "sketch_center_rectangle",
                "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
            },
            {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}},
            {"id": "hole_001", "op": "create_through_hole", "params": {"plane": "top_face", "center": [-60, 0], "diameter": 6}},
        ]

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any("base boundary" in violation.message for violation in result.violations), result.violations)

    def test_inferred_out_of_bounds_hole_requests_llm_recommendation(self):
        plan = complete_p0_plan()
        plan["metadata"] = {
            "name": "p0_complete_part",
            "source": "local",
            "inferred_parameters": ["hole_001.params.center"],
            "explicit_parameters": [],
        }
        plan["operations"] = [
            {"id": "new_001", "op": "create_new_part", "params": {}},
            {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "top_face"}},
            {
                "id": "rect_001",
                "op": "sketch_center_rectangle",
                "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
            },
            {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}},
            {"id": "hole_001", "op": "create_through_hole", "params": {"plane": "top_face", "center": [-60, 0], "diameter": 6}},
        ]

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any("Inferred parameter hole_001.params.center" in violation.message for violation in result.violations), result.violations)

    def test_explicit_out_of_bounds_hole_requires_user_confirmation(self):
        plan = complete_p0_plan()
        plan["metadata"] = {
            "name": "p0_complete_part",
            "source": "local",
            "inferred_parameters": [],
            "explicit_parameters": ["hole_001.params.center"],
        }
        plan["operations"] = [
            {"id": "new_001", "op": "create_new_part", "params": {}},
            {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "top_face"}},
            {
                "id": "rect_001",
                "op": "sketch_center_rectangle",
                "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
            },
            {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}},
            {"id": "hole_001", "op": "create_through_hole", "params": {"plane": "top_face", "center": [-60, 0], "diameter": 6}},
        ]

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any("Explicit user parameter hole_001.params.center" in violation.message for violation in result.violations), result.violations)


    def test_corner_holes_must_stay_inside_base_boundary(self):
        plan = complete_p0_plan()
        plan["operations"] = [
            {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
            {"id": "hole_001", "op": "cut_corner_holes", "params": {"diameter": 10, "edge_margin": 2.5, "through_all": True}},
        ]

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any("cut_corner_holes" in violation.message and "base boundary" in violation.message for violation in result.violations), result.violations)
    def test_metadata_parameter_paths_must_reference_operation_ids(self):
        plan = complete_p0_plan()
        plan["metadata"] = {
            "name": "p0_complete_part",
            "source": "local",
            "inferred_parameters": ["create_center_boss.params.diameter"],
            "explicit_parameters": [],
        }

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any(v.code == "metadata" and "unknown operation id" in v.message for v in result.violations), result.violations)

    def test_metadata_parameter_paths_must_reference_existing_parameters(self):
        plan = complete_p0_plan()
        plan["metadata"] = {
            "name": "p0_complete_part",
            "source": "local",
            "inferred_parameters": ["op_004.params.nope"],
            "explicit_parameters": [],
        }

        result = PolicyEngine().validate(plan)

        self.assertFalse(result.allowed)
        self.assertTrue(any(v.code == "metadata" and "missing operation parameter" in v.message for v in result.violations), result.violations)

    def test_metadata_parameter_paths_accept_dotted_operation_ids(self):
        # Local 7B models emit operation ids that contain a dot (e.g.
        # ``create_base_plate.001``). A parameter path like
        # ``create_base_plate.001.params.length`` therefore has 4 dot-separated
        # segments; the validator must split on ``.params.`` (not count 3
        # segments) so these legitimate paths are not falsely rejected as
        # "invalid parameter path".
        plan = complete_p0_plan()
        target_op = plan["operations"][3]
        dotted_id = "extrude_boss.004"
        target_op["id"] = dotted_id
        param_name = next(iter(target_op["params"]), None)
        self.assertIsNotNone(param_name, "fixture operation must expose at least one param")
        plan["metadata"] = {
            "name": "p0_complete_part",
            "source": "local",
            "inferred_parameters": [f"{dotted_id}.params.{param_name}"],
            "explicit_parameters": [],
        }

        result = PolicyEngine().validate(plan)

        self.assertFalse(
            any(v.code == "metadata" and "invalid parameter path" in v.message for v in result.violations),
            result.violations,
        )

    def test_offcenter_hole_with_left_edge_distance_coordinate_is_allowed(self):
        plan = complete_p0_plan()
        plan["operations"] = [
            {"id": "new_001", "op": "create_new_part", "params": {}},
            {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "top_face"}},
            {
                "id": "rect_001",
                "op": "sketch_center_rectangle",
                "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
            },
            {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}},
            {"id": "hole_001", "op": "create_through_hole", "params": {"plane": "top_face", "center": [-40, 0], "diameter": 6}},
        ]

        result = PolicyEngine().validate(plan)

        self.assertTrue(result.allowed, result.violations)

    def test_planned_operation_is_not_executable(self):
        features = dict(default_registry().features)
        features["future_op"] = FeatureDefinition(
            op="future_op",
            status="planned",
            description="Future planned operation.",
            parameter_schema={"type": "object", "required": [], "properties": {}, "additionalProperties": False},
            executor_function="future_op",
            documentation_path="docs/solidworks_feature_capability_matrix.md",
            limitations=("not executable",),
        )
        plan = valid_plan()
        plan["operations"] = [{"id": "future_001", "op": "future_op", "params": {}}]
        result = PolicyEngine(registry=FeatureRegistry(features=features)).validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("planned" in violation.message and "不能执行" in violation.message for violation in result.violations))

    def test_prd_p0_atomic_operation_is_executable_after_policy(self):
        plan = valid_plan()
        plan["operations"] = [
            {
                "id": "sketch_001",
                "op": "create_sketch",
                "params": {"name": "sketch_base", "plane": "Top"},
            }
        ]
        result = PolicyEngine().validate(plan)
        self.assertTrue(result.allowed, result.violations)

    def test_prd_p0_extra_parameter_is_rejected(self):
        plan = valid_plan()
        plan["operations"] = [
            {
                "id": "sketch_001",
                "op": "create_sketch",
                "params": {"name": "sketch_base", "plane": "Top", "unexpected": True},
            }
        ]
        result = PolicyEngine(registry=default_registry(), allow_non_implemented=True).validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("参数" in violation.message or "鍙傛暟" in violation.message for violation in result.violations))

    def test_prd_p0_invalid_geometry_is_rejected_even_when_allowing_scaffolded(self):
        plan = valid_plan()
        plan["operations"] = [
            {
                "id": "rect_001",
                "op": "sketch_center_rectangle",
                "params": {"sketch": "sketch_base", "center": [0, 0], "length": -100, "width": 60},
            }
        ]
        result = PolicyEngine(registry=default_registry(), allow_non_implemented=True).validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("length" in violation.message for violation in result.violations))

    def test_unknown_operation_is_rejected(self):
        plan = valid_plan()
        plan["operations"] = [{"id": "bad_001", "op": "launch_solidworks", "params": {}}]
        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("未知 op" in violation.message for violation in result.violations))

    def test_dangerous_fields_are_rejected(self):
        for field in (
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
        ):
            plan = valid_plan()
            plan["operations"][0]["params"][field] = "bad"
            with self.subTest(field=field):
                result = PolicyEngine().validate(plan)
                self.assertFalse(result.allowed)
                self.assertTrue(any("禁止字段" in violation.message for violation in result.violations))

    def test_top_level_output_dir_is_rejected_before_normalization(self):
        plan = valid_plan()
        plan["output_dir"] = "C:\\Windows\\System32"
        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("禁止字段" in violation.message for violation in result.violations))

    def test_unit_must_be_mm(self):
        plan = valid_plan()
        plan["unit"] = "inch"
        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("unit 只能是 mm" in violation.message for violation in result.violations))

    def test_outputs_must_be_allowlisted_booleans(self):
        plan = valid_plan()
        plan["outputs"] = {"save_sldprt": "yes", "output_dir": True}
        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("outputs" in violation.message for violation in result.violations))

    def test_invalid_geometry_is_rejected(self):
        plan = valid_plan()
        plan["operations"][0]["params"]["length"] = -120
        result = PolicyEngine().validate(plan)
        self.assertFalse(result.allowed)
        self.assertTrue(any("尺寸不能为负数" in violation.message for violation in result.violations))


if __name__ == "__main__":
    unittest.main()
