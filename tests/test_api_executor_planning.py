import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from io import StringIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import main, run_api_executor
from app.job_writer import write_job_ini
from app.validator import validate_cadplan
from cad_dsl.cadplan_adapter import cadplan_to_featureplan
from cad_dsl.featureplan import FeaturePlan
from solidworks_api.executor import SolidWorksApiExecutor
from solidworks_api.com_types import dispatch_none
from solidworks_api.features.fillet import (
    _edge_points,
    _is_outer_vertical_edge,
    _select_edge,
    _select_outer_edges,
    _select_outer_top_perimeter_edges,
)
from solidworks_api.model_builder import ModelBuilder
from solidworks_api.selectors import select_top_plane
from solidworks_api.session import SolidWorksSession
from solidworks_api.units import mm_to_m


def valid_featureplan():
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
            }
        ],
        "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
    }


class GuardedSession(SolidWorksSession):
    def __init__(self):
        super().__init__()
        self.connect_called = False

    def connect(self) -> None:
        self.connect_called = True
        raise AssertionError("dry_run must not connect to SOLIDWORKS")


class FakeFace:
    def __init__(self, top_z):
        self.top_z = float(top_z)
        self.select2_calls = 0
        self.select4_calls = 0

    def GetBox(self):
        return [0.0, 0.0, self.top_z, 0.0, 0.0, self.top_z]

    def Select2(self, append, mark):
        self.select2_calls += 1
        return True

    def Select4(self, append, select_data):
        self.select4_calls += 1
        return True


class FakeFeature:
    def __init__(self, name="", top_z=None):
        self.Name = name
        self.select2_calls = 0
        self.top_face = FakeFace(top_z) if top_z is not None else None

    def Select2(self, append, mark):
        self.select2_calls += 1
        return True

    def GetFaces(self):
        if self.top_face is None:
            return []
        return [self.top_face]


class FakeSketchManager:
    def __init__(self):
        self.insert_calls = 0
        self.rectangles = []
        self.circles = []
        self.slots = []

    def InsertSketch(self, value):
        self.insert_calls += 1

    def CreateCenterRectangle(self, *args):
        self.rectangles.append(args)

    def CreateCircleByRadius(self, *args):
        self.circles.append(args)

    def CreateSketchSlot(self, *args):
        self.slots.append(args)


class FakeFeatureManager:
    def __init__(self):
        self.extrusions = []
        self.extruded_features = []
        self.cuts = []
        self.linear_patterns = []
        self.current_top_z = 0.0

    def FeatureExtrusion2(self, *args):
        self.extrusions.append(args)
        depth = float(args[5]) if len(args) > 5 else 0.0
        self.current_top_z += depth
        feature = FakeFeature(f"Extrude{len(self.extrusions)}", top_z=self.current_top_z)
        self.extruded_features.append(feature)
        return feature

    def FeatureCut3(self, *args):
        self.cuts.append(args)
        return FakeFeature(f"Cut{len(self.cuts)}")

    def FeatureLinearPattern5(self, *args):
        self.linear_patterns.append(args)
        return FakeFeature(f"Pattern{len(self.linear_patterns)}")


class RejectingLinearPatternFeatureManager(FakeFeatureManager):
    def FeatureLinearPattern5(self, *args):
        raise RuntimeError("type mismatch")

    def FeatureLinearPattern4(self, *args):
        raise RuntimeError("type mismatch")



class BossNoneFeatureManager(FakeFeatureManager):
    def __init__(self):
        super().__init__()
        self._extrusion_calls = 0

    def FeatureExtrusion2(self, *args):
        self._extrusion_calls += 1
        self.extrusions.append(args)
        if self._extrusion_calls >= 2:
            return None
        return FakeFeature(f"BaseExtrude{self._extrusion_calls}", top_z=args[5] if len(args) > 5 else 0.0)


class NoFaceFeatureManager(FakeFeatureManager):
    def FeatureExtrusion2(self, *args):
        self.extrusions.append(args)
        feature = FakeFeature(f"Extrude{len(self.extrusions)}")
        self.extruded_features.append(feature)
        return feature


class CutNoneFeatureManager(FakeFeatureManager):
    def FeatureCut3(self, *args):
        self.cuts.append(args)
        return None


class FakeExtension:
    def __init__(self):
        self.selections = []
        self.saves = []

    def SelectByID2(self, *args):
        self.selections.append(args)
        return True

    def SaveAs(self, *args):
        self.saves.append(args)
        return True


class FakeModel:
    def __init__(self):
        self.Extension = FakeExtension()
        self.SketchManager = FakeSketchManager()
        self.FeatureManager = FakeFeatureManager()
        self.rebuilds = 0
        self.png_saves = []
        self.zoomed = False

    def ClearSelection2(self, value):
        self.cleared = value

    def ForceRebuild3(self, value):
        self.rebuilds += 1
        return True

    def ViewZoomtofit2(self):
        self.zoomed = True

    def SaveAs3(self, *args):
        self.png_saves.append(args)
        return True


class FakeApp:
    def __init__(self):
        self.model = FakeModel()
        self.new_document_calls = 0

    def GetUserPreferenceStringValue(self, preference):
        return r"C:\ProgramData\SOLIDWORKS\templates\Part.prtdot"

    def NewDocument(self, template, paper_size, width, height):
        self.new_document_calls += 1
        return self.model


class TestApiExecutorPlanning(unittest.TestCase):
    def test_mm_to_m_conversion(self):
        self.assertEqual(mm_to_m(1000), 1.0)
        self.assertEqual(mm_to_m(12), 0.012)

    def test_dispatch_none_helper_is_safe_without_connection(self):
        self.assertIsNot(dispatch_none, None)
        dispatch_none()

    def test_dry_run_does_not_connect_solidworks(self):
        session = GuardedSession()
        result = SolidWorksApiExecutor(session=session).dry_run(valid_featureplan())
        self.assertEqual(result.status, "dry_run")
        self.assertFalse(session.connect_called)
        self.assertEqual(result.operations[0].operation_type, "create_base_plate")
        self.assertEqual(result.operations[0].status, "planned")

    def test_execute_default_is_dry_run(self):
        session = GuardedSession()
        result = SolidWorksApiExecutor(session=session).execute(valid_featureplan())
        self.assertEqual(result.status, "dry_run")
        self.assertFalse(session.connect_called)

    def test_api_executor_requires_yes_before_real_execution(self):
        cadplan = validate_cadplan(
            {
                "template": "mounting_plate",
                "unit": "mm",
                "part_name": "ai_mounting_plate",
                "base": {"length": 120, "width": 80, "thickness": 12},
                "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            }
        )
        with patch.dict("os.environ", {"AI_SW_API_DRY_RUN": ""}, clear=False):
            with patch("builtins.input", return_value="NO"):
                with patch("app.main.SolidWorksApiExecutor.execute") as execute:
                    exit_code = run_api_executor(cadplan)

        self.assertEqual(exit_code, 0)
        execute.assert_not_called()

    def test_api_executor_parses_p1_box_chamfer_prompt_to_featureplan_dry_run(self):
        prompt = "create a 120x80x12mm box with C2 chamfer and export STEP"
        llm_featureplan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "api_box_chamfer",
            "operations": [
                {"id": "new_001", "op": "create_new_part", "params": {}},
                {"id": "sketch_001", "op": "create_sketch", "params": {"name": "sketch_base", "plane": "Top"}},
                {
                    "id": "rect_001",
                    "op": "sketch_center_rectangle",
                    "params": {"sketch": "sketch_base", "center": [0, 0], "length": 120, "width": 80},
                },
                {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "sketch_base", "depth": 12}},
                {"id": "chamfer_001", "op": "add_chamfer", "params": {"distance": 2, "angle": 45, "target": "outer_edges"}},
                {"id": "step_001", "op": "export_step", "params": {}},
            ],
            "outputs": {"save_sldprt": False, "export_step": False, "capture_png": False},
        }
        with patch.dict("os.environ", {"AI_SW_EXECUTOR_MODE": "api_executor", "AI_SW_API_DRY_RUN": "1", "AI_SW_USE_LLM": "1"}, clear=False):
            with patch.object(sys, "argv", ["app/main.py", prompt]):
                with patch("cad_dsl.nl_featureplan_parser.parse_featureplan_with_provider", return_value=llm_featureplan) as llm:
                    with patch("sys.stdout", new_callable=StringIO) as stdout:
                        exit_code = main()

        output = stdout.getvalue()
        llm.assert_called_once_with(prompt)
        self.assertEqual(exit_code, 0)
        self.assertIn('"op": "add_chamfer"', output)
        self.assertIn('"distance": 2', output)
        self.assertIn('"op": "export_step"', output)
        self.assertIn("dry_run 不连接 SOLIDWORKS", output)

    def test_api_executor_parses_p1_box_blind_hole_prompt_to_featureplan_dry_run(self):
        prompt = "create a 120x80x12mm box with a 10mm diameter 6mm deep blind hole"
        llm_featureplan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "api_box_blind_hole",
            "operations": [
                {"id": "new_001", "op": "create_new_part", "params": {}},
                {"id": "sketch_001", "op": "create_sketch", "params": {"name": "sketch_base", "plane": "Top"}},
                {
                    "id": "rect_001",
                    "op": "sketch_center_rectangle",
                    "params": {"sketch": "sketch_base", "center": [0, 0], "length": 120, "width": 80},
                },
                {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "sketch_base", "depth": 12}},
                {
                    "id": "blind_001",
                    "op": "create_blind_hole",
                    "params": {"plane": "top_face", "center": [0, 0], "diameter": 10, "depth": 6},
                },
            ],
            "outputs": {"save_sldprt": False, "export_step": False, "capture_png": False},
        }
        with patch.dict("os.environ", {"AI_SW_EXECUTOR_MODE": "api_executor", "AI_SW_API_DRY_RUN": "1", "AI_SW_USE_LLM": "1"}, clear=False):
            with patch.object(sys, "argv", ["app/main.py", prompt]):
                with patch("cad_dsl.nl_featureplan_parser.parse_featureplan_with_provider", return_value=llm_featureplan) as llm:
                    with patch("sys.stdout", new_callable=StringIO) as stdout:
                        exit_code = main()

        output = stdout.getvalue()
        llm.assert_called_once_with(prompt)
        self.assertEqual(exit_code, 0)
        self.assertIn('"op": "create_blind_hole"', output)
        self.assertIn('"diameter": 10', output)
        self.assertIn('"depth": 6', output)
        self.assertIn('"plane": "top_face"', output)
        self.assertIn("dry_run 不连接 SOLIDWORKS", output)

    def test_api_executor_parses_blank_part_prompt_without_creating_geometry(self):
        prompt = "create a blank part with default mm template and save as test_part"
        llm_featureplan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "test_part",
            "operations": [
                {"id": "new_001", "op": "create_new_part", "params": {}},
                {"id": "save_001", "op": "save_sldprt", "params": {}},
            ],
            "outputs": {"save_sldprt": False, "export_step": False, "capture_png": False},
        }
        with patch.dict("os.environ", {"AI_SW_EXECUTOR_MODE": "api_executor", "AI_SW_API_DRY_RUN": "1", "AI_SW_USE_LLM": "1"}, clear=False):
            with patch.object(sys, "argv", ["app/main.py", prompt]):
                with patch("cad_dsl.nl_featureplan_parser.parse_featureplan_with_provider", return_value=llm_featureplan) as llm:
                    with patch("sys.stdout", new_callable=StringIO) as stdout:
                        exit_code = main()

        output = stdout.getvalue()
        llm.assert_called_once_with(prompt)
        self.assertEqual(exit_code, 0)
        self.assertIn('"part_name": "test_part"', output)
        self.assertIn('"op": "create_new_part"', output)
        self.assertIn('"op": "save_sldprt"', output)
        self.assertNotIn('"op": "create_base_plate"', output)
        self.assertNotIn('"op": "sketch_center_rectangle"', output)
        self.assertIn("dry_run 不连接 SOLIDWORKS", output)

    def test_api_executor_parses_p0_box_center_through_hole_prompt_to_featureplan_dry_run(self):
        prompt = "create a 120x80x12mm box with a 10mm center through hole"
        llm_featureplan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "api_box_through_hole",
            "operations": [
                {"id": "new_001", "op": "create_new_part", "params": {}},
                {"id": "sketch_001", "op": "create_sketch", "params": {"name": "sketch_base", "plane": "Top"}},
                {
                    "id": "rect_001",
                    "op": "sketch_center_rectangle",
                    "params": {"sketch": "sketch_base", "center": [0, 0], "length": 120, "width": 80},
                },
                {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "sketch_base", "depth": 12}},
                {
                    "id": "hole_001",
                    "op": "create_through_hole",
                    "params": {"plane": "top_face", "center": [0, 0], "diameter": 10, "through_all": True},
                },
            ],
            "outputs": {"save_sldprt": False, "export_step": False, "capture_png": False},
        }
        with patch.dict("os.environ", {"AI_SW_EXECUTOR_MODE": "api_executor", "AI_SW_API_DRY_RUN": "1", "AI_SW_USE_LLM": "1"}, clear=False):
            with patch.object(sys, "argv", ["app/main.py", prompt]):
                with patch("cad_dsl.nl_featureplan_parser.parse_featureplan_with_provider", return_value=llm_featureplan) as llm:
                    with patch("sys.stdout", new_callable=StringIO) as stdout:
                        exit_code = main()

        output = stdout.getvalue()
        llm.assert_called_once_with(prompt)
        self.assertEqual(exit_code, 0)
        self.assertIn('"op": "create_through_hole"', output)
        self.assertIn('"diameter": 10', output)
        self.assertIn('"through_all": true', output)
        self.assertIn('"center": [\n          0,\n          0\n        ]', output)
        self.assertIn("dry_run 不连接 SOLIDWORKS", output)

    def test_api_executor_local_provider_failure_falls_back_to_rule_based(self):
        prompt = "120x80x12mm"
        from app.providers.local_provider import LocalProviderError

        with patch.dict("os.environ", {"AI_SW_EXECUTOR_MODE": "api_executor", "AI_SW_API_DRY_RUN": "1", "AI_SW_LLM_PROVIDER": "local"}, clear=False):
            with patch.object(sys, "argv", ["app/main.py", prompt]):
                with patch("app.providers.local_provider.parse_featureplan", side_effect=LocalProviderError("mock unavailable")):
                    with patch("sys.stdout", new_callable=StringIO) as stdout:
                        exit_code = main()

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("fallback to rule_based parser", output)
        self.assertIn('"op": "create_base_plate"', output)
        self.assertIn("dry_run", output)

    def test_legacy_vba_reports_chamfer_requires_api_executor(self):
        prompt = "create a 120x80x12mm box with C2 \u5012\u89d2 and export STEP"
        with patch.dict("os.environ", {"AI_SW_EXECUTOR_MODE": "legacy_vba"}, clear=False):
            with patch.object(sys, "argv", ["app/main.py", prompt]):
                with patch("sys.stdout", new_callable=StringIO) as stdout:
                    exit_code = main()

        output = stdout.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("legacy_vba 旧宏模式不支持倒角", output)
        self.assertIn("AI_SW_EXECUTOR_MODE=api_executor", output)

    def test_blank_part_cadplan_adapts_to_empty_part_plan(self):
        cadplan = validate_cadplan(
            {
                "template": "blank_part",
                "unit": "mm",
                "part_name": "test_part",
                "outputs": {"save_sldprt": True, "export_step": False, "capture_png": False},
            }
        )
        featureplan = cadplan_to_featureplan(cadplan)
        ops = [operation.op for operation in featureplan.operations]

        self.assertEqual(featureplan.part_name, "test_part")
        self.assertIn("create_new_part", ops)
        self.assertIn("save_sldprt", ops)
        self.assertNotIn("create_base_plate", ops)

    def test_blank_part_dry_run_does_not_connect_solidworks(self):
        cadplan = validate_cadplan(
            {
                "template": "blank_part",
                "unit": "mm",
                "part_name": "test_part",
                "outputs": {"save_sldprt": True, "export_step": False, "capture_png": False},
            }
        )
        session = GuardedSession()
        result = SolidWorksApiExecutor(session=session).dry_run(cadplan_to_featureplan(cadplan))

        self.assertEqual(result.status, "dry_run")
        self.assertFalse(session.connect_called)
        self.assertEqual(result.operations[0].operation_type, "create_new_part")

    def test_base_center_hole_adapts_to_create_through_hole(self):
        cadplan = validate_cadplan(
            {
                "template": "mounting_plate",
                "unit": "mm",
                "part_name": "center_hole_block",
                "base": {"shape": "rectangle", "length": 120, "width": 80, "thickness": 12},
                "center_boss": {"enabled": False},
                "center_hole": {"enabled": True, "diameter": 10, "through_all": True},
                "outputs": {"save_sldprt": True, "export_step": False, "capture_png": False},
            }
        )
        featureplan = cadplan_to_featureplan(cadplan)
        ops = [operation.op for operation in featureplan.operations]
        through_hole = next(operation for operation in featureplan.operations if operation.op == "create_through_hole")

        self.assertIn("create_base_plate", ops)
        self.assertIn("create_through_hole", ops)
        self.assertNotIn("cut_center_hole", ops)
        self.assertEqual(through_hole.params["center"], [0, 0])
        self.assertEqual(through_hole.params["diameter"], 10)

    def test_blocked_plan_returns_policy_errors(self):
        plan = valid_featureplan()
        plan["operations"][0]["op"] = "create_revolve_boss"
        plan["operations"][0]["params"] = {"profile": "profile_001", "axis": "axis_001", "angle": 360}
        result = SolidWorksApiExecutor().dry_run(plan)
        self.assertEqual(result.status, "blocked")
        self.assertTrue(result.operations)

    def test_prd_p0_atomic_dry_run_is_planned_without_connection(self):
        session = GuardedSession()
        plan = valid_featureplan()
        plan["operations"] = [
            {
                "id": "sketch_001",
                "op": "create_sketch",
                "params": {"name": "sketch_base", "plane": "Top"},
            }
        ]
        result = SolidWorksApiExecutor(session=session).dry_run(plan)
        self.assertEqual(result.status, "dry_run")
        self.assertFalse(session.connect_called)
        self.assertEqual(result.operations[0].operation_type, "create_sketch")
        self.assertEqual(result.operations[0].status, "planned")

    def test_missing_new_document_reports_clear_error(self):
        class MissingMembers:
            def __getattr__(self, name):
                raise AttributeError(f"鎵句笉鍒版垚鍛? {name}")

        with self.assertRaisesRegex(RuntimeError, "无法通过 SolidWorks API 新建零件"):
            ModelBuilder()._create_new_part(MissingMembers())

    def test_new_document_fallback_uses_default_part_template(self):
        class AppWithNewDocument:
            def __init__(self):
                self.template = None

            def GetUserPreferenceStringValue(self, preference):
                self.preference = preference
                return r"C:\ProgramData\SOLIDWORKS\templates\Part.prtdot"

            def NewDocument(self, template, paper_size, width, height):
                self.template = template
                self.paper_size = paper_size
                self.width = width
                self.height = height
                return object()

        app = AppWithNewDocument()
        self.assertIsNotNone(ModelBuilder()._create_new_part(app))
        self.assertEqual(app.preference, 1)
        self.assertEqual(app.template, r"C:\ProgramData\SOLIDWORKS\templates\Part.prtdot")
        self.assertEqual(app.paper_size, 0)

    def test_new_document_none_uses_active_doc_without_second_create(self):
        class AppWithActiveDoc:
            def __init__(self):
                self.new_document_calls = 0
                self.ActiveDoc = object()

            def GetUserPreferenceStringValue(self, preference):
                return r"C:\ProgramData\SOLIDWORKS\templates\Part.prtdot"

            def NewDocument(self, template, paper_size, width, height):
                self.new_document_calls += 1
                return None

        app = AppWithActiveDoc()
        self.assertIs(ModelBuilder()._create_new_part(app), app.ActiveDoc)
        self.assertEqual(app.new_document_calls, 1)

    def test_default_template_fallback_uses_get_document_template(self):
        class AppWithDocumentTemplate:
            def GetUserPreferenceStringValue(self, preference):
                self.preference = preference
                return ""

            def GetDocumentTemplate(self, doc_type, template_name, paper_size, width, height):
                self.doc_type = doc_type
                self.template_name = template_name
                self.paper_size = paper_size
                self.width = width
                self.height = height
                return r"C:\ProgramData\SolidWorks\SOLIDWORKS 2019\templates\闆朵欢.prtdot"

        app = AppWithDocumentTemplate()
        template = ModelBuilder()._default_part_template(app)
        self.assertEqual(template, r"C:\ProgramData\SolidWorks\SOLIDWORKS 2019\templates\闆朵欢.prtdot")
        self.assertEqual(app.preference, 1)
        self.assertEqual(app.doc_type, 1)
        self.assertEqual(app.paper_size, 0)

    def test_default_template_empty_api_results_are_rejected(self):
        class EmptyTemplateApp:
            def GetUserPreferenceStringValue(self, preference):
                return ""

            def GetDocumentTemplate(self, doc_type, template_name, paper_size, width, height):
                return ""

        with self.assertRaisesRegex(RuntimeError, "无法从 SolidWorks 读取默认 Part 模板路径"):
            ModelBuilder()._default_part_template(EmptyTemplateApp())

    def test_save_outputs_uses_com_safe_saveas_arguments(self):
        class Extension:
            def __init__(self):
                self.calls = []

            def SaveAs(self, target, version, options, export_data, errors, warnings):
                self.calls.append((target, version, options, export_data, errors, warnings))

        class Model:
            def __init__(self):
                self.Extension = Extension()
                self.zoomed = False
                self.png_calls = []

            def ViewZoomtofit2(self):
                self.zoomed = True

            def SaveAs3(self, target, version, options):
                self.png_calls.append((target, version, options))

        model = Model()
        outputs = ModelBuilder()._save_outputs(model, FeaturePlan.from_dict(valid_featureplan()))

        self.assertEqual(len(outputs), 3)
        self.assertEqual(len(model.Extension.calls), 2)
        for call in model.Extension.calls:
            self.assertIsNotNone(call[3])
            self.assertIsNotNone(call[4])
            self.assertIsNotNone(call[5])
        self.assertTrue(model.zoomed)
        self.assertEqual(len(model.png_calls), 1)

    def test_p0_atomic_rectangle_extrude_build_uses_fixed_api_calls(self):
        app = FakeApp()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "p0_atomic_rect",
                "operations": [
                    {"id": "new_001", "op": "create_new_part", "params": {}},
                    {"id": "sketch_001", "op": "create_sketch", "params": {"name": "sketch_base", "plane": "Top"}},
                    {
                        "id": "rect_001",
                        "op": "sketch_center_rectangle",
                        "params": {"sketch": "sketch_base", "center": [0, 0], "length": 100, "width": 60},
                    },
                    {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "sketch_base", "depth": 10}},
                    {"id": "rebuild_001", "op": "rebuild_model", "params": {}},
                    {"id": "validate_001", "op": "validate_rebuild", "params": {}},
                ],
                "outputs": {},
            }
        )

        outputs = ModelBuilder().build(app, plan)

        self.assertEqual(len(outputs), 3)
        self.assertEqual(app.new_document_calls, 1)
        self.assertEqual(len(app.model.SketchManager.rectangles), 1)
        self.assertEqual(len(app.model.FeatureManager.extrusions), 1)
        self.assertGreaterEqual(app.model.rebuilds, 1)

    def test_p0_atomic_through_hole_build_uses_fixed_cut_call(self):
        app = FakeApp()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "p0_atomic_hole",
                "operations": [
                    {"id": "new_001", "op": "create_new_part", "params": {}},
                    {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "Top"}},
                    {
                        "id": "rect_001",
                        "op": "sketch_center_rectangle",
                        "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
                    },
                    {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}},
                    {
                        "id": "hole_001",
                        "op": "create_through_hole",
                        "params": {"plane": "Top", "center": [5, 6], "diameter": 6.6},
                    },
                ],
                "outputs": {},
            }
        )

        outputs = ModelBuilder().build(app, plan)

        self.assertEqual(len(outputs), 3)
        self.assertEqual(len(app.model.SketchManager.circles), 1)
        self.assertEqual(len(app.model.FeatureManager.cuts), 1)

    def test_slot_and_pocket_plan_with_extra_llm_sketches_builds_with_fixed_api_calls(self):
        app = FakeApp()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "slot_pocket_with_extra_sketches",
                "operations": [
                    {"id": "new_001", "op": "create_new_part", "params": {}},
                    {"id": "base_sketch", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "top_face"}},
                    {
                        "id": "base_rect",
                        "op": "sketch_center_rectangle",
                        "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
                    },
                    {"id": "base_extrude", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}},
                    {"id": "slot_sketch", "op": "create_sketch", "params": {"name": "SlotSketch", "plane": "top_face"}},
                    {
                        "id": "slot_rect",
                        "op": "sketch_center_rectangle",
                        "params": {"sketch": "SlotSketch", "center": [0, 20], "length": 40, "width": 10},
                    },
                    {
                        "id": "slot_cut",
                        "op": "cut_slot",
                        "params": {"plane": "top_face", "center": [0, 20], "length": 40, "width": 10, "depth": 12},
                    },
                    {"id": "pocket_sketch", "op": "create_sketch", "params": {"name": "PocketSketch", "plane": "top_face"}},
                    {
                        "id": "pocket_rect",
                        "op": "sketch_center_rectangle",
                        "params": {"sketch": "PocketSketch", "center": [0, -20], "length": 30, "width": 20},
                    },
                    {
                        "id": "pocket_cut",
                        "op": "cut_rectangle_pocket",
                        "params": {"plane": "top_face", "center": [0, -20], "length": 30, "width": 20, "depth": 5},
                    },
                ],
                "outputs": {},
            }
        )

        ModelBuilder().build(app, plan)

        self.assertEqual(len(app.model.SketchManager.slots), 0)
        self.assertGreaterEqual(len(app.model.SketchManager.rectangles), 3)
        self.assertEqual(len(app.model.FeatureManager.cuts), 2)

    def test_linear_pattern_hole_plan_uses_fixed_hole_fallback_when_native_pattern_rejects_signature(self):
        app = FakeApp()
        app.model.FeatureManager = RejectingLinearPatternFeatureManager()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "linear_hole_pattern",
                "operations": [
                    {"id": "1", "op": "create_new_part", "params": {}},
                    {"id": "2", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "top_face"}},
                    {
                        "id": "3",
                        "op": "sketch_center_rectangle",
                        "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
                    },
                    {"id": "4", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}},
                    {"id": "5", "op": "create_through_hole", "params": {"plane": "top_face", "center": [0, 0], "diameter": 6}},
                    {
                        "id": "6",
                        "op": "create_linear_pattern",
                        "params": {"seed_feature": "Hole1", "direction": "X", "count": 4, "spacing": 20},
                    },
                    {"id": "7", "op": "save_sldprt", "params": {}},
                ],
                "outputs": {},
            }
        )

        outputs = ModelBuilder().build(app, plan)

        self.assertEqual(len(app.model.SketchManager.circles), 4)
        self.assertEqual(len(app.model.FeatureManager.cuts), 4)
        self.assertEqual(len(app.model.FeatureManager.linear_patterns), 0)
        self.assertEqual(len(outputs), 1)

    def test_duplicate_base_plate_and_atomic_base_extrude_are_canonicalized_in_dry_run(self):
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

        result = SolidWorksApiExecutor(session=GuardedSession()).dry_run(plan)

        self.assertEqual(result.status, "dry_run", result)
        self.assertEqual(
            [operation.operation_id for operation in result.operations],
            ["base_plate_001", "through_hole_001", "linear_pattern_001"],
        )

    def test_linear_pattern_seed_feature_suffix_is_normalized_in_dry_run(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "linear_seed_suffix",
            "operations": [
                {"id": "1", "op": "create_new_part", "params": {}},
                {"id": "2", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "top_face"}},
                {
                    "id": "3",
                    "op": "sketch_center_rectangle",
                    "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
                },
                {"id": "4", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}},
                {"id": "5", "op": "create_through_hole", "params": {"plane": "top_face", "center": [0, 0], "diameter": 6}},
                {
                    "id": "6",
                    "op": "create_linear_pattern",
                    "params": {"seed_feature": "5.feature_id", "direction": "X", "count": 4, "spacing": 20},
                },
            ],
            "outputs": {},
        }

        result = SolidWorksApiExecutor(session=GuardedSession()).dry_run(plan)

        self.assertEqual(result.status, "dry_run")
        self.assertEqual([operation.operation_id for operation in result.operations][-2:], ["5", "6"])

    def test_mvp_corner_edge_margin_and_center_hole_depth_build_use_fixed_api_calls(self):
        app = FakeApp()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "mvp_hole_controls",
                "operations": [
                    {
                        "id": "base_001",
                        "op": "create_base_plate",
                        "params": {"length": 220, "width": 80, "thickness": 12, "plane": "Top"},
                    },
                    {
                        "id": "corner_001",
                        "op": "cut_corner_holes",
                        "params": {"diameter": 6.6, "edge_margin": 10, "through_all": True},
                    },
                    {
                        "id": "boss_001",
                        "op": "create_center_boss",
                        "params": {"diameter": 30, "height": 25, "plane": "top_face"},
                    },
                    {
                        "id": "center_001",
                        "op": "cut_center_hole",
                        "params": {"diameter": 10, "target": "boss", "depth": 37, "through_all": False},
                    },
                ],
                "outputs": {},
            }
        )

        ModelBuilder().build(app, plan)

        self.assertEqual(len(app.model.SketchManager.circles), 6)
        self.assertEqual(len(app.model.FeatureManager.cuts), 2)
        corner_x = app.model.SketchManager.circles[0][0]
        corner_y = app.model.SketchManager.circles[0][1]
        center_cut_depth = app.model.FeatureManager.cuts[-1][5]
        self.assertEqual(corner_x, mm_to_m(-100))
        self.assertEqual(corner_y, mm_to_m(-30))
        self.assertEqual(center_cut_depth, mm_to_m(37))

    def test_dry_run_reorders_boss_before_boss_target_center_hole(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "reordered_boss_hole",
            "operations": [
                {
                    "id": "base_001",
                    "op": "create_base_plate",
                    "params": {"length": 220, "width": 80, "thickness": 12, "plane": "Top"},
                },
                {
                    "id": "center_001",
                    "op": "cut_center_hole",
                    "params": {"diameter": 10, "target": "boss", "depth": 37},
                },
                {
                    "id": "boss_001",
                    "op": "create_center_boss",
                    "params": {"diameter": 30, "height": 25, "plane": "top_face"},
                },
            ],
            "outputs": {},
        }

        result = SolidWorksApiExecutor(session=GuardedSession()).dry_run(plan)

        self.assertEqual(result.status, "dry_run")
        self.assertEqual([operation.operation_id for operation in result.operations], ["base_001", "boss_001", "center_001"])

    def test_dry_run_reorders_corner_holes_after_atomic_base_extrude(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "reordered_corner_holes",
            "operations": [
                {"id": "new_001", "op": "create_new_part", "params": {}},
                {
                    "id": "holes_001",
                    "op": "cut_corner_holes",
                    "params": {"diameter": 10, "edge_margin": 20},
                },
                {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "top_face"}},
                {
                    "id": "rect_001",
                    "op": "sketch_center_rectangle",
                    "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 100, "width": 80},
                },
                {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 5}},
            ],
            "outputs": {},
        }

        result = SolidWorksApiExecutor(session=GuardedSession()).dry_run(plan)

        self.assertEqual(result.status, "dry_run")
        self.assertEqual(
            [operation.operation_id for operation in result.operations],
            ["new_001", "sketch_001", "rect_001", "extrude_001", "holes_001"],
        )

    def test_plain_box_center_hole_without_target_defaults_to_base(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "plain_box_center_hole",
            "operations": [
                {"id": "new_001", "op": "create_new_part", "params": {}},
                {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "top_face"}},
                {
                    "id": "rect_001",
                    "op": "sketch_center_rectangle",
                    "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
                },
                {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 12}},
                {"id": "hole_001", "op": "cut_center_hole", "params": {"diameter": 10, "through_all": True}},
            ],
            "outputs": {},
        }

        result = SolidWorksApiExecutor(session=GuardedSession()).dry_run(plan)

        self.assertEqual(result.status, "dry_run", result)
        self.assertEqual(
            [operation.operation_id for operation in result.operations],
            ["new_001", "sketch_001", "rect_001", "extrude_001", "hole_001"],
        )

    def test_cut_before_completed_base_solid_is_blocked_in_dry_run(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "missing_base_solid",
            "operations": [
                {"id": "new_001", "op": "create_new_part", "params": {}},
                {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "top_face"}},
                {
                    "id": "rect_001",
                    "op": "sketch_center_rectangle",
                    "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80},
                },
                {"id": "hole_001", "op": "cut_center_hole", "params": {"diameter": 6, "target": "base"}},
            ],
            "outputs": {},
        }

        result = SolidWorksApiExecutor(session=GuardedSession()).dry_run(plan)

        self.assertEqual(result.status, "blocked")
        self.assertIn("requires a completed base solid", result.message + result.operations[0].message)

    def test_model_builder_reorders_boss_before_boss_target_center_hole(self):
        app = FakeApp()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "builder_reordered_boss_hole",
                "operations": [
                    {
                        "id": "base_001",
                        "op": "create_base_plate",
                        "params": {"length": 220, "width": 80, "thickness": 12, "plane": "Top"},
                    },
                    {
                        "id": "center_001",
                        "op": "cut_center_hole",
                        "params": {"diameter": 10, "target": "boss", "depth": 37},
                    },
                    {
                        "id": "boss_001",
                        "op": "create_center_boss",
                        "params": {"diameter": 30, "height": 25, "plane": "top_face"},
                    },
                ],
                "outputs": {},
            }
        )

        ModelBuilder().build(app, plan)

        self.assertEqual(len(app.model.FeatureManager.extrusions), 2)
        self.assertEqual(len(app.model.FeatureManager.cuts), 1)
        self.assertEqual(app.model.FeatureManager.cuts[0][5], mm_to_m(37))

    def test_dry_run_explicit_save_operation_only_plans_sldprt_output(self):
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "explicit_save_only",
            "operations": [
                {"id": "new_001", "op": "create_new_part", "params": {}},
                {"id": "save_001", "op": "save_sldprt", "params": {}},
            ],
            "outputs": {},
        }

        result = SolidWorksApiExecutor(session=GuardedSession()).dry_run(plan)

        self.assertEqual(result.status, "dry_run")
        self.assertEqual(len(result.outputs), 1)
        self.assertTrue(result.outputs[0].endswith(".SLDPRT"))
        self.assertFalse(any(path.endswith(".STEP") for path in result.outputs))

    def test_cut_center_hole_target_boss_prefers_known_top_z_before_feature_face(self):
        app = FakeApp()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "boss_target_face_selection",
                "operations": [
                    {
                        "id": "base_001",
                        "op": "create_base_plate",
                        "params": {"length": 150, "width": 100, "thickness": 15, "plane": "Top"},
                    },
                    {
                        "id": "boss_001",
                        "op": "create_center_boss",
                        "params": {"diameter": 40, "height": 20, "plane": "top_face"},
                    },
                    {
                        "id": "hole_001",
                        "op": "cut_center_hole",
                        "params": {"diameter": 12, "target": "boss", "through_all": True},
                    },
                ],
                "outputs": {},
            }
        )

        ModelBuilder().build(app, plan)

        boss_feature = app.model.FeatureManager.extruded_features[1]
        self.assertEqual(boss_feature.top_face.select2_calls + boss_feature.top_face.select4_calls, 0)
        self.assertTrue(
            any(
                len(selection) > 4 and selection[1] == "FACE" and abs(float(selection[4]) - mm_to_m(35)) < 1e-9
                for selection in app.model.Extension.selections
            )
        )

    def test_center_hole_target_boss_without_boss_fails_in_fixed_executor(self):
        app = FakeApp()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "missing_boss_target",
                "operations": [
                    {
                        "id": "base_001",
                        "op": "create_base_plate",
                        "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"},
                    },
                    {
                        "id": "center_001",
                        "op": "cut_center_hole",
                        "params": {"diameter": 10, "target": "boss", "depth": 5},
                    },
                ],
                "outputs": {},
            }
        )

        with self.assertRaisesRegex(RuntimeError, "Cannot plan cut_center_hole target=boss"):
            ModelBuilder().build(app, plan)


    def test_center_boss_none_return_is_not_silent(self):
        app = FakeApp()
        app.model.FeatureManager = BossNoneFeatureManager()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "boss_none",
                "operations": [
                    {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
                    {"id": "boss_001", "op": "create_center_boss", "params": {"diameter": 30, "height": 25, "plane": "top_face"}},
                ],
                "outputs": {},
            }
        )

        with self.assertRaisesRegex(RuntimeError, "create_center_boss failed: FeatureExtrusion2 returned None"):
            ModelBuilder().build(app, plan)

    def test_cut_center_hole_none_return_is_not_silent(self):
        app = FakeApp()
        app.model.FeatureManager = CutNoneFeatureManager()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "center_hole_none",
                "operations": [
                    {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
                    {"id": "hole_001", "op": "cut_center_hole", "params": {"diameter": 10, "target": "base", "through_all": True}},
                ],
                "outputs": {},
            }
        )

        with self.assertRaisesRegex(RuntimeError, "cut_center_hole failed: API returned None"):
            ModelBuilder().build(app, plan)
    def test_face_selection_failure_is_not_silent(self):
        class RejectingExtension(FakeExtension):
            def SelectByID2(self, *args):
                self.selections.append(args)
                if args[1] == "PLANE":
                    return True
                return False

        app = FakeApp()
        app.model.Extension = RejectingExtension()
        app.model.FeatureManager = NoFaceFeatureManager()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "selection_failure",
                "operations": [
                    {
                        "id": "base_001",
                        "op": "create_base_plate",
                        "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"},
                    },
                    {
                        "id": "corner_001",
                        "op": "cut_corner_holes",
                        "params": {"diameter": 6.6, "edge_margin": 10},
                    },
                ],
                "outputs": {},
            }
        )

        with self.assertRaisesRegex(RuntimeError, "Unable to select FACE"):
            ModelBuilder().build(app, plan)

    def test_p0_explicit_output_operations_do_not_duplicate_default_outputs(self):
        app = FakeApp()
        plan = FeaturePlan.from_dict(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "p0_atomic_output",
                "operations": [
                    {"id": "new_001", "op": "create_new_part", "params": {}},
                    {"id": "save_001", "op": "save_sldprt", "params": {}},
                ],
                "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            }
        )

        outputs = ModelBuilder().build(app, plan)

        self.assertEqual(len(outputs), 1)
        self.assertEqual(len(app.model.Extension.saves), 1)
        self.assertFalse(app.model.png_saves)

    def test_select_top_plane_can_use_feature_by_name_fallback(self):
        class Extension:
            def SelectByID2(self, *args):
                return False

        class Feature:
            def __init__(self):
                self.selected = False

            def Select2(self, append, mark):
                self.selected = True
                return True

        class Model:
            def __init__(self):
                self.Extension = Extension()
                self.feature = Feature()
                self.cleared = False

            def ClearSelection2(self, value):
                self.cleared = value

            def FeatureByName(self, name):
                if name == "Top Plane":
                    return self.feature
                return None

        model = Model()
        select_top_plane(model)
        self.assertTrue(model.cleared)
        self.assertTrue(model.feature.selected)

    def test_fillet_edge_selection_can_fallback_without_select_data(self):
        class Edge:
            def __init__(self):
                self.select2_called = False

            def Select4(self, append, select_data):
                raise AttributeError("CreateSelectData is unavailable")

            def Select2(self, append, mark):
                self.select2_called = True
                self.append = append
                self.mark = mark
                return True

        edge = Edge()
        self.assertTrue(_select_edge(edge, True, None))
        self.assertTrue(edge.select2_called)
        self.assertTrue(edge.append)
        self.assertEqual(edge.mark, 0)

    def test_fillet_geometry_can_use_curve_params_fallback(self):
        class Edge:
            def __getattr__(self, name):
                if name in {"GetStartVertex", "GetEndVertex"}:
                    raise AttributeError(name)
                raise AttributeError(name)

            def GetCurveParams2(self):
                return [0.06, 0.0, 0.04, 0.06, 0.012, 0.04]

        p1, p2 = _edge_points(Edge())
        self.assertEqual(p1, [0.06, 0.0, 0.04])
        self.assertEqual(p2, [0.06, 0.012, 0.04])
        self.assertTrue(_is_outer_vertical_edge(Edge(), 0.06, 0.04, 0.012, 0.00035))

    def test_fillet_geometry_accepts_z_extrusion_outer_edges(self):
        class Edge:
            def __getattr__(self, name):
                if name in {"GetStartVertex", "GetEndVertex"}:
                    raise AttributeError(name)
                raise AttributeError(name)

            def GetCurveParams2(self):
                return [0.06, 0.04, 0.0, 0.06, 0.04, 0.012]

        p1, p2 = _edge_points(Edge())
        self.assertEqual(p1, [0.06, 0.04, 0.0])
        self.assertEqual(p2, [0.06, 0.04, 0.012])
        self.assertTrue(_is_outer_vertical_edge(Edge(), 0.06, 0.04, 0.012, 0.00035))
    def test_fillet_prefers_top_outer_loop_edges_when_available(self):
        class Edge:
            def __init__(self):
                self.selected = 0

            def Select4(self, append, select_data):
                self.selected += 1
                return True

        class Loop:
            def __init__(self, edges):
                self._edges = edges

            def IsOuter(self):
                return True

            def GetEdges(self):
                return self._edges

        class Face:
            def __init__(self, box, loop):
                self._box = box
                self._loop = loop

            def GetBox(self):
                return self._box

            def GetLoops(self):
                return [self._loop]

        class Body:
            def __init__(self, faces):
                self._faces = faces

            def GetFaces(self):
                return self._faces

        class SelectionManager:
            def CreateSelectData(self):
                return object()

        class Model:
            def __init__(self, body):
                self.SelectionManager = SelectionManager()
                self._body = body

            def GetBodies2(self, body_type, visible_only):
                return [self._body]

        edges = [Edge(), Edge(), Edge(), Edge()]
        outer_loop = Loop(edges)
        top_face = Face([-0.06, -0.04, 0.012, 0.06, 0.04, 0.012], outer_loop)
        boss_top = Face([-0.01, -0.01, 0.025, 0.01, 0.01, 0.025], Loop([Edge()]))
        model = Model(Body([boss_top, top_face]))

        selected = _select_outer_top_perimeter_edges(model, 120, 80, 12)
        self.assertEqual(selected, 4)
        self.assertTrue(all(edge.selected == 1 for edge in edges))

    def test_fillet_outer_edges_can_fallback_from_top_loop_to_vertical_edges(self):
        class Body:
            def __init__(self, edges):
                self._edges = edges

            def GetFaces(self):
                return []

            @property
            def GetEdges(self):
                return lambda: self._edges

        class SelectionManager:
            def CreateSelectData(self):
                return object()

        class Vertex:
            def __init__(self, point):
                self._point = point

            def GetPoint(self):
                return self._point

        class Edge:
            def __init__(self, p1, p2):
                self._start = Vertex(p1)
                self._end = Vertex(p2)
                self.selected = 0

            def GetStartVertex(self):
                return self._start

            def GetEndVertex(self):
                return self._end

            def Select4(self, append, select_data):
                self.selected += 1
                return True

        class Model:
            def __init__(self, body):
                self.SelectionManager = SelectionManager()
                self._body = body

            def GetBodies2(self, body_type, visible_only):
                return [self._body]

        edges = [
            Edge([0.06, 0.04, 0.0], [0.06, 0.04, 0.012]),
            Edge([0.06, -0.04, 0.0], [0.06, -0.04, 0.012]),
            Edge([-0.06, 0.04, 0.0], [-0.06, 0.04, 0.012]),
            Edge([-0.06, -0.04, 0.0], [-0.06, -0.04, 0.012]),
        ]
        model = Model(Body(edges))

        selected = _select_outer_edges(model, 120, 80, 12)
        self.assertEqual(selected, 4)
        self.assertTrue(all(edge.selected == 1 for edge in edges))


    def test_legacy_vba_job_writer_flow_still_works(self):
        cadplan = validate_cadplan(
            {
                "template": "mounting_plate",
                "unit": "mm",
                "part_name": "ai_mounting_plate",
                "base": {"length": 120, "width": 80, "thickness": 12},
            }
        )
        text = write_job_ini(cadplan).read_text(encoding="utf-8")
        self.assertIn("template=mounting_plate", text)
        self.assertIn("base_length=120", text)
        self.assertNotIn("output_dir", text)


if __name__ == "__main__":
    unittest.main()



