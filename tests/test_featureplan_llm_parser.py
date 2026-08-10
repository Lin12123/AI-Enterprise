import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cad_dsl.feature_registry import FeatureDefinition, FeatureRegistry, default_registry
from cad_dsl.featureplan_prompt import build_featureplan_prompt
from cad_dsl.nl_featureplan_parser import parse_prompt_to_featureplan
from app.openai_config import safe_exception_message
from policy.file_safety_rules import FORBIDDEN_KEYS
from policy.geometry_rules import MAX_PATTERN_COUNT
from policy.policy_prompt import build_policy_prompt_summary
from solidworks_api.executor import SolidWorksApiExecutor
from solidworks_api.session import SolidWorksSession


class GuardedSession(SolidWorksSession):
    def __init__(self):
        super().__init__()
        self.connect_called = False

    def connect(self) -> None:
        self.connect_called = True
        raise AssertionError("dry_run must not connect to SolidWorks")


IMPLEMENTED_NL_CASES = {
    "create_new_part": ("new part", {}),
    "create_sketch": ("create sketch on Top", {"name": "sketch_base", "plane": "Top"}),
    "sketch_center_rectangle": (
        "draw center rectangle",
        {"sketch": "sketch_base", "center": [0, 0], "length": 120, "width": 80},
    ),
    "sketch_circle": ("draw circle", {"sketch": "sketch_hole", "center": [0, 0], "diameter": 10}),
    "extrude_boss": ("extrude boss", {"sketch": "sketch_base", "depth": 12}),
    "extrude_cut": ("extrude cut through all", {"sketch": "sketch_hole", "through_all": True}),
    "create_through_hole": ("create through hole", {"plane": "top_face", "center": [0, 0], "diameter": 10}),
    "add_fillet": ("add R2 fillet", {"radius": 2, "target": "outer_edges"}),
    "save_sldprt": ("save part", {}),
    "export_step": ("export STEP", {}),
    "capture_png": ("capture PNG", {}),
    "rebuild_model": ("rebuild model", {}),
    "validate_rebuild": ("validate rebuild", {}),
    "create_base_plate": ("create 120x80x12 base plate", {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}),
    "cut_corner_holes": ("cut corner holes", {"diameter": 6.6, "offset_x": 50, "offset_y": 30, "through_all": True}),
    "create_center_boss": ("create center boss", {"diameter": 30, "height": 25, "plane": "top_face"}),
    "cut_center_hole": ("cut center hole", {"diameter": 10, "target": "base", "through_all": True}),
    "add_chamfer": ("add C2 chamfer", {"distance": 2, "angle": 45, "target": "outer_edges"}),
    "create_blind_hole": ("create blind hole", {"plane": "top_face", "center": [0, 0], "diameter": 10, "depth": 6}),
    "create_counterbore_hole": (
        "create counterbore hole",
        {"plane": "top_face", "center": [0, 0], "hole_diameter": 6.6, "counterbore_diameter": 12, "counterbore_depth": 4},
    ),
    "create_countersink_hole": (
        "create countersink hole",
        {"plane": "top_face", "center": [0, 0], "hole_diameter": 6.6, "countersink_diameter": 12, "angle": 90},
    ),
    "cut_slot": ("cut slot", {"plane": "top_face", "center": [0, 0], "length": 30, "width": 8, "through_all": False, "depth": 5}),
    "cut_rectangle_pocket": ("cut rectangle pocket", {"plane": "top_face", "center": [0, 0], "length": 40, "width": 20, "depth": 5}),
    "create_linear_pattern": ("create linear pattern", {"seed_feature": "hole_001", "direction": "x", "count": 3, "spacing": 20}),
    "create_circular_pattern": ("create circular pattern", {"seed_feature": "hole_001", "axis": "Axis_01", "count": 6, "angle": 360}),
    "mirror_feature": ("mirror feature", {"seed_feature": "pocket_001", "mirror_plane": "Front"}),
    "set_material": ("set material", {"material": "6061 Alloy"}),
    "set_custom_property": ("set custom property", {"key": "PartNumber", "value": "P-001"}),
    "modify_named_dimension": ("modify named dimension", {"dimension_name": "D_base_length", "value": 150}),
    "create_offset_plane": ("create offset plane", {"name": "Plane_Offset_01", "base_plane": "Top", "offset": 25}),
    "create_axis": ("create axis", {"name": "Axis_01", "reference_type": "two_planes", "references": ["Front", "Right"]}),
}


def llm_plan_for(op, params):
    operations = []
    if op in {"sketch_center_rectangle", "sketch_circle", "extrude_boss"}:
        sketch_name = params.get("sketch", "sketch_base")
        operations.append({"id": "ctx_sketch", "op": "create_sketch", "params": {"name": sketch_name, "plane": "Top"}})
    if op == "extrude_boss":
        operations.append(
            {
                "id": "ctx_rect",
                "op": "sketch_center_rectangle",
                "params": {"sketch": params.get("sketch", "sketch_base"), "center": [0, 0], "length": 120, "width": 80},
            }
        )
    if op in _solid_body_ops():
        operations.extend(_base_context_ops())
    if op == "extrude_cut":
        operations.extend(
            [
                {"id": "ctx_cut_sketch", "op": "create_sketch", "params": {"name": params.get("sketch", "sketch_hole"), "plane": "top_face"}},
                {"id": "ctx_cut_circle", "op": "sketch_circle", "params": {"sketch": params.get("sketch", "sketch_hole"), "center": [0, 0], "diameter": 10}},
            ]
        )
    if op == "create_linear_pattern":
        operations.append({"id": "hole_001", "op": "create_through_hole", "params": {"plane": "top_face", "center": [0, 0], "diameter": 6}})
        params = dict(params)
        params["seed_feature"] = "Hole1"
    if op == "create_circular_pattern":
        operations.append({"id": "hole_001", "op": "create_through_hole", "params": {"plane": "top_face", "center": [0, 0], "diameter": 6}})
    if op == "mirror_feature":
        operations.append({"id": "pocket_001", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [0, 0], "length": 20, "width": 10, "depth": 3}})
    operations.append({"id": "op_001", "op": op, "params": params})
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": f"nl_{op}",
        "operations": operations,
        "outputs": {"save_sldprt": False, "export_step": False, "capture_png": False},
    }


def _base_context_ops():
    return [
        {"id": "ctx_new", "op": "create_new_part", "params": {}},
        {"id": "ctx_base_sketch", "op": "create_sketch", "params": {"name": "ctx_base", "plane": "Top"}},
        {"id": "ctx_base_rect", "op": "sketch_center_rectangle", "params": {"sketch": "ctx_base", "center": [0, 0], "length": 120, "width": 80}},
        {"id": "ctx_base_extrude", "op": "extrude_boss", "params": {"sketch": "ctx_base", "depth": 12}},
    ]


def _solid_body_ops():
    return {
        "extrude_cut",
        "create_through_hole",
        "add_fillet",
        "cut_corner_holes",
        "create_center_boss",
        "cut_center_hole",
        "add_chamfer",
        "create_blind_hole",
        "create_counterbore_hole",
        "create_countersink_hole",
        "cut_slot",
        "cut_rectangle_pocket",
        "create_linear_pattern",
        "create_circular_pattern",
        "mirror_feature",
    }


class TestFeaturePlanLlmParser(unittest.TestCase):
    def test_llm_featureplan_parser_covers_all_p0_mvp_and_p1_implemented_operations(self):
        for op, (prompt, params) in IMPLEMENTED_NL_CASES.items():
            with self.subTest(op=op):
                with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
                    with patch("cad_dsl.nl_featureplan_parser.parse_featureplan_with_provider", return_value=llm_plan_for(op, params)) as llm:
                        plan = parse_prompt_to_featureplan(prompt)

                llm.assert_called_once_with(prompt)
                self.assertIsNotNone(plan)
                self.assertIn(op, [operation.op for operation in plan.operations])
                result = SolidWorksApiExecutor(session=GuardedSession()).dry_run(plan)
                self.assertEqual(result.status, "dry_run", result)

    def test_llm_prompt_is_generated_from_registry_and_includes_p0_p1_operations(self):
        prompt = build_featureplan_prompt()
        for op in IMPLEMENTED_NL_CASES:
            with self.subTest(op=op):
                self.assertIn(op, prompt)
        self.assertIn("Use only implemented operations", prompt)
        self.assertIn("Do not output scaffolded", prompt)
        self.assertIn("blank/new/empty part", prompt)
        self.assertIn("create no geometry", prompt)
        self.assertIn("create_new_part plus requested output operations", prompt)
        self.assertIn("metadata.inferred_parameters", prompt)
        self.assertIn("metadata.explicit_parameters", prompt)
        self.assertIn("edge distance into a center coordinate", prompt)
        self.assertIn("edge_margin", prompt)
        self.assertIn("hole-center distance from base edges", prompt)
        self.assertIn("cut_center_hole depth", prompt)
        self.assertIn("target='boss'", prompt)
        self.assertIn("Never output plane or center for cut_center_hole", prompt)
        self.assertIn("C2", prompt)
        self.assertIn("add_chamfer", prompt)
        self.assertIn("倒角", prompt)
        self.assertIn("R2", prompt)
        self.assertIn("add_fillet", prompt)
        self.assertIn("倒圆", prompt)
        self.assertIn("Aluminum_6061", prompt)
        self.assertIn("PartNumber", prompt)
        self.assertIn("Description", prompt)
        self.assertIn("零件编号", prompt)
        self.assertIn("描述", prompt)

    def test_chinese_c_chamfer_prompt_maps_to_add_chamfer_not_fillet(self):
        prompt = "创建一个 120×80×12mm 的长方体，外轮廓加 C2 倒角，保存并导出 STEP。"
        llm_featureplan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "cn_c2_chamfer",
            "operations": [
                {"id": "new_001", "op": "create_new_part", "params": {}},
                {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "top_face"}},
                {
                    "id": "rect_001",
                    "op": "sketch_center_rectangle",
                    "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
                },
                {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}},
                {"id": "chamfer_001", "op": "add_chamfer", "params": {"distance": 2, "angle": 45, "target": "outer_edges"}},
                {"id": "save_001", "op": "save_sldprt", "params": {}},
                {"id": "step_001", "op": "export_step", "params": {}},
            ],
            "outputs": {},
        }

        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("cad_dsl.nl_featureplan_parser.parse_featureplan_with_provider", return_value=llm_featureplan) as llm:
                plan = parse_prompt_to_featureplan(prompt)

        llm.assert_called_once_with(prompt)
        ops = [operation.op for operation in plan.operations]
        self.assertIn("add_chamfer", ops)
        self.assertNotIn("add_fillet", ops)
        result = SolidWorksApiExecutor(session=GuardedSession()).dry_run(plan)
        self.assertEqual(result.status, "dry_run", result)

    def test_new_implemented_registry_operation_is_automatically_exposed_to_llm_prompt(self):
        base = dict(default_registry().features)
        base["create_test_feature"] = FeatureDefinition(
            op="create_test_feature",
            status="implemented",
            description="Test-only operation.",
            parameter_schema={
                "type": "object",
                "required": ["size"],
                "properties": {"size": {}},
                "additionalProperties": False,
            },
            executor_function="create_test_feature",
            documentation_path="docs/test.md",
            limitations=("test limitation",),
        )
        prompt = build_featureplan_prompt(FeatureRegistry(features=base))

        self.assertIn("create_test_feature", prompt)
        self.assertIn("required=[size]", prompt)
        self.assertIn("test limitation", prompt)

    def test_scaffolded_operations_are_visible_as_blocked_not_executable_in_llm_prompt(self):
        prompt = build_featureplan_prompt()
        self.assertIn("create_sweep_boss: status=scaffolded", prompt)
        self.assertIn("Blocked non-implemented operations", prompt)

    def test_policy_summary_is_generated_from_policy_constants(self):
        summary = build_policy_prompt_summary()
        prompt = build_featureplan_prompt(compact=True)

        self.assertIn("Policy Engine constraints", summary)
        self.assertIn("output_dir", summary)
        self.assertIn("script", summary)
        self.assertIn(str(MAX_PATTERN_COUNT), summary)
        self.assertIn("6061 Alloy", summary)
        self.assertIn("PartNumber", summary)
        self.assertIn("D_base_length", summary)
        self.assertIn("create_sketch plane must be exactly", summary)
        self.assertIn("create_through_hole plane must be exactly", summary)
        self.assertIn("Do not output plane values such as Top Plane", summary)
        self.assertIn("Policy Engine constraints", prompt)
        for key in ("output_dir", "script", "macro", "command"):
            self.assertIn(key, FORBIDDEN_KEYS)
            self.assertIn(key, prompt)

    def test_llm_error_diagnostics_redact_sensitive_values(self):
        message = safe_exception_message(
            RuntimeError(
                "request failed with OPENAI_API_KEY=testsecret123456 "
                "and Authorization: Bearer anothersecret123456"
            )
        )

        self.assertIn("RuntimeError", message)
        self.assertIn("[redacted]", message)
        self.assertNotIn("testsecret", message)
        self.assertNotIn("anothersecret", message)


if __name__ == "__main__":
    unittest.main()


