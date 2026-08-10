import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from solidworks_api.features.base_plate import create_base_plate
from solidworks_api.features.boss import create_center_boss
from solidworks_api.features.chamfer import add_chamfer
from solidworks_api.features.cut import cut_rectangle_pocket, cut_slot
from solidworks_api.features.hole import create_blind_hole, create_counterbore_hole, create_countersink_hole, create_through_hole, cut_corner_holes
from solidworks_api.features.material_properties import set_custom_property, set_material
from solidworks_api.features.mirror import mirror_feature
from solidworks_api.features.modify import modify_named_dimension
from solidworks_api.features.pattern import create_circular_pattern, create_linear_pattern
from solidworks_api.features.reference_geometry import create_axis, create_offset_plane


class FakeFeature:
    def __init__(self):
        self.Name = ""

    def Select2(self, append, mark):
        return True


class SelectableFace:
    def __init__(self, box):
        self._box = tuple(box)
        self.select2_calls = 0
        self.select4_calls = 0

    def GetBox(self):
        return self._box

    def Select2(self, append, mark):
        self.select2_calls += 1
        return True

    def Select4(self, append, select_data):
        self.select4_calls += 1
        return True


class SelectableFeature(FakeFeature):
    def __init__(self, name, box):
        super().__init__()
        self.Name = name
        self.top_face = SelectableFace(box)

    def GetFaces(self):
        return [self.top_face]


class FakeFace:
    def __init__(self, box):
        self._box = tuple(box)

    def GetBox(self):
        return self._box


class BoxFeature(FakeFeature):
    def __init__(self, boxes):
        super().__init__()
        self._faces = [FakeFace(box) for box in boxes]

    def GetFaces(self):
        return self._faces


class FakePropertyManager:
    def __init__(self):
        self.calls = []

    def Add3(self, key, value_type, value, option):
        self.calls.append((key, value_type, value, option))
        return 1


class FakeExtension:
    def __init__(self):
        self.selections = []
        self.property_manager = FakePropertyManager()

    def SelectByID2(self, *args):
        self.selections.append(args)
        return True

    def CustomPropertyManager(self, config):
        return self.property_manager


class CenterRejectingFaceExtension(FakeExtension):
    def SelectByID2(self, *args):
        self.selections.append(args)
        object_type = args[1] if len(args) > 1 else ""
        x = float(args[2]) if len(args) > 2 else 0.0
        y = float(args[3]) if len(args) > 3 else 0.0
        z = float(args[4]) if len(args) > 4 else 0.0
        if object_type == "FACE" and abs(z - 0.012) < 1e-9 and abs(x) < 1e-12 and abs(y) < 1e-12:
            return False
        return True


class FakeSketchManager:
    def __init__(self):
        self.sketches = 0
        self.circles = []
        self.slots = []
        self.rectangles = []

    def InsertSketch(self, value):
        self.sketches += 1

    def CreateCircleByRadius(self, *args):
        self.circles.append(args)

    def CreateSketchSlot(self, *args):
        self.slots.append(args)

    def CreateCenterRectangle(self, *args):
        self.rectangles.append(args)


class RejectingSlotSketchManager(FakeSketchManager):
    def CreateSketchSlot(self, *args):
        raise RuntimeError("non-optional argument")


class NoSlotSketchManager(FakeSketchManager):
    def __getattribute__(self, name):
        if name == "CreateSketchSlot":
            raise AttributeError(name)
        return super().__getattribute__(name)


class FakeFeatureManager:
    def __init__(self):
        self.cuts = []
        self.chamfers = []
        self.linear_patterns = []
        self.circular_patterns = []
        self.mirrors = []
        self.planes = []
        self.axes = []

    def FeatureCut3(self, *args):
        self.cuts.append(args)
        return FakeFeature()

    def InsertFeatureChamfer(self, *args):
        self.chamfers.append(args)
        return FakeFeature()

    def FeatureLinearPattern5(self, *args):
        self.linear_patterns.append(args)
        return FakeFeature()

    def FeatureCircularPattern5(self, *args):
        self.circular_patterns.append(args)
        return FakeFeature()

    def InsertMirrorFeature2(self, *args):
        self.mirrors.append(args)
        return FakeFeature()

    def InsertRefPlane(self, *args):
        self.planes.append(args)
        return FakeFeature()

    def InsertRefAxis(self, *args):
        self.axes.append(args)
        return FakeFeature()


class RejectingLinearPatternFeatureManager(FakeFeatureManager):
    def FeatureLinearPattern5(self, *args):
        raise RuntimeError("type mismatch")

    def FeatureLinearPattern4(self, *args):
        raise RuntimeError("type mismatch")


class FirstLinearPatternSignatureRejectsFeatureManager(FakeFeatureManager):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def FeatureLinearPattern5(self, *args):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("type mismatch")
        self.linear_patterns.append(args)
        return FakeFeature()


class ReverseRetryBlindCutFeatureManager(FakeFeatureManager):
    def FeatureCut3(self, *args):
        self.cuts.append(args)
        reverse = bool(args[2]) if len(args) > 2 else False
        end_condition = args[3] if len(args) > 3 else None
        if end_condition == 0 and not reverse:
            return None
        return FakeFeature()


class SequencedExtrusionFeatureManager(FakeFeatureManager):
    def __init__(self, features):
        super().__init__()
        self._features = list(features)
        self.extrusions = []

    def FeatureExtrusion2(self, *args):
        self.extrusions.append(args)
        if self._features:
            return self._features.pop(0)
        return FakeFeature()


class GetFacesRejectingFeature(FakeFeature):
    def __getattr__(self, name):
        if name in {"GetFaces", "IGetFaces2"}:
            raise RuntimeError("read-only COM access failed")
        raise AttributeError(name)


class FakeDimension:
    def __init__(self):
        self.SystemValue = 0


class FakeModel:
    def __init__(self):
        self.Extension = FakeExtension()
        self.SketchManager = FakeSketchManager()
        self.FeatureManager = FakeFeatureManager()
        self.cleared = 0
        self.material_calls = []
        self.dimension = FakeDimension()
        self.SelectionManager = None

    def ClearSelection2(self, value):
        self.cleared += 1

    def FeatureByName(self, name):
        return FakeFeature()

    def SetMaterialPropertyName2(self, *args):
        self.material_calls.append(args)

    def Parameter(self, name):
        return self.dimension


class VerifyingMaterialModel(FakeModel):
    def __init__(self, accepted_name, reported_name=None):
        super().__init__()
        self.accepted_name = accepted_name
        self.reported_name = reported_name
        self.current_material = ""

    def SetMaterialPropertyName2(self, config, database, material):
        self.material_calls.append((config, database, material))
        if material == self.accepted_name:
            self.current_material = material
            return True
        return False

    def GetMaterialPropertyName2(self, config, database):
        return self.reported_name or self.current_material


class RejectingMaterialModel(FakeModel):
    def SetMaterialPropertyName2(self, config, database, material):
        self.material_calls.append((config, database, material))
        return True

    def GetMaterialPropertyName2(self, config, database):
        return "Different Material"


class EmptyMaterialGetterModel(VerifyingMaterialModel):
    def GetMaterialPropertyName2(self, config, database):
        return ""


class TestP1ApiExecutorBuild(unittest.TestCase):
    def setUp(self):
        self.model = FakeModel()
        self.state = {"base": {"length": 120, "width": 80, "thickness": 12}}

    def test_chamfer_fixed_path(self):
        with patch("solidworks_api.features.fillet._select_outer_vertical_edges", return_value=4):
            add_chamfer(self.model, {"distance": 2, "angle": 45, "target": "outer_edges"}, self.state)
        self.assertEqual(len(self.model.FeatureManager.chamfers), 1)

    def test_counterbore_and_countersink_fixed_paths(self):
        create_counterbore_hole(
            self.model,
            {"plane": "top_face", "center": [0, 0], "hole_diameter": 6, "counterbore_diameter": 12, "counterbore_depth": 3},
            self.state,
        )
        create_countersink_hole(
            self.model,
            {"plane": "top_face", "center": [0, 0], "hole_diameter": 6, "countersink_diameter": 12, "angle": 90},
            self.state,
        )
        self.assertGreaterEqual(len(self.model.FeatureManager.cuts), 4)

    def test_slot_pattern_mirror_fixed_paths(self):
        self.state["current_operation_id"] = "slot_001"
        cut_slot(self.model, {"plane": "top_face", "center": [0, 0], "length": 30, "width": 8}, self.state)
        self.state.pop("current_operation_id", None)
        create_linear_pattern(self.model, {"seed_feature": "slot_001", "direction": "x", "count": 3, "spacing": 20}, self.state)
        create_circular_pattern(self.model, {"seed_feature": "slot_001", "axis": "Axis_01", "count": 6, "angle": 360}, self.state)
        mirror_feature(self.model, {"seed_feature": "slot_001", "mirror_plane": "Front"}, self.state)
        self.assertEqual(len(self.model.SketchManager.rectangles), 3)
        self.assertEqual(len(self.model.SketchManager.slots), 0)
        self.assertEqual(len(self.model.FeatureManager.linear_patterns), 0)
        self.assertEqual(len(self.model.FeatureManager.circular_patterns), 1)
        self.assertEqual(len(self.model.FeatureManager.mirrors), 1)

    def test_slot_y_direction_uses_vertical_rectangular_fallback_by_default(self):
        cut_slot(self.model, {"plane": "top_face", "center": [-40, 0], "length": 80, "width": 10, "direction": "y", "through_all": True}, self.state)
        rect_args = self.model.SketchManager.rectangles[0]
        self.assertAlmostEqual(rect_args[0], -0.04)
        self.assertAlmostEqual(rect_args[1], 0.0)
        self.assertAlmostEqual(rect_args[3], -0.035)
        self.assertAlmostEqual(rect_args[4], 0.0401, places=4)

    def test_open_edge_slot_extends_sketch_slightly_past_base_boundary(self):
        cut_slot(self.model, {"plane": "top_face", "center": [-35, 0], "length": 80, "width": 10, "direction": "y", "depth": 7.5}, self.state)
        rect_args = self.model.SketchManager.rectangles[0]
        self.assertAlmostEqual(rect_args[0], -0.035)
        self.assertAlmostEqual(rect_args[1], 0.0)
        self.assertAlmostEqual(rect_args[3], -0.03)
        self.assertAlmostEqual(rect_args[4], 0.0401, places=4)
        self.assertEqual(len(self.model.FeatureManager.cuts), 1)

    def test_slot_native_api_is_opt_in_only(self):
        with patch.dict("os.environ", {"AI_SW_ENABLE_EXPERIMENTAL_SLOT_API": "1"}):
            cut_slot(self.model, {"plane": "top_face", "center": [0, 0], "length": 30, "width": 8}, self.state)
        self.assertEqual(len(self.model.SketchManager.slots), 1)

    def test_linear_pattern_falls_back_to_seed_hole_instances_when_native_pattern_rejects_signature(self):
        self.model.FeatureManager = RejectingLinearPatternFeatureManager()
        self.state["current_operation_id"] = "hole_001"
        create_through_hole(self.model, {"plane": "top_face", "center": [0, 0], "diameter": 6}, self.state)
        self.state.pop("current_operation_id", None)

        create_linear_pattern(self.model, {"seed_feature": "Hole1", "direction": "X", "count": 4, "spacing": 20}, self.state)

        self.assertEqual(len(self.model.SketchManager.circles), 4)
        self.assertEqual(self.model.SketchManager.circles[0][0], 0.0)
        self.assertAlmostEqual(self.model.SketchManager.circles[1][0], 0.02)
        self.assertAlmostEqual(self.model.SketchManager.circles[2][0], 0.04)
        self.assertAlmostEqual(self.model.SketchManager.circles[3][0], 0.06)
        self.assertEqual(len(self.model.FeatureManager.cuts), 4)

    def test_linear_pattern_replays_slot_seed_when_registered(self):
        self.model.FeatureManager = RejectingLinearPatternFeatureManager()
        self.state["current_operation_id"] = "slot_001"
        cut_slot(self.model, {"plane": "top_face", "center": [0, 0], "length": 30, "width": 8, "depth": 5}, self.state)
        self.state.pop("current_operation_id", None)

        create_linear_pattern(self.model, {"seed_feature": "slot_001", "direction": "x", "count": 3, "spacing": 20}, self.state)

        self.assertEqual(len(self.model.FeatureManager.linear_patterns), 0)
        self.assertEqual(len(self.model.FeatureManager.cuts), 3)
        self.assertEqual(len(self.model.SketchManager.rectangles), 3)

    def test_linear_pattern_tries_compatible_signatures_for_non_hole_seed(self):
        self.model.FeatureManager = FirstLinearPatternSignatureRejectsFeatureManager()

        create_linear_pattern(self.model, {"seed_feature": "slot_001", "direction": "x", "count": 3, "spacing": 20}, self.state)

        self.assertEqual(self.model.FeatureManager.calls, 2)
        self.assertEqual(len(self.model.FeatureManager.linear_patterns), 1)

    def test_slot_closes_preexisting_active_sketch_before_fixed_slot_path(self):
        self.state["active_sketch"] = "LLMExtraSketch"
        cut_slot(self.model, {"plane": "top_face", "center": [0, 0], "length": 40, "width": 10, "depth": 12}, self.state)

        self.assertNotIn("active_sketch", self.state)
        self.assertEqual(self.state["last_closed_sketch"], "LLMExtraSketch")

    def test_top_face_selection_avoids_center_after_boss_and_hole_split_base_face(self):
        self.model.Extension = CenterRejectingFaceExtension()
        self.state["boss"] = {"diameter": 20, "height": 15}

        cut_slot(self.model, {"plane": "top_face", "center": [-35, 0], "length": 80, "width": 10, "direction": "y", "depth": 7.5}, self.state)

        face_selections = [call for call in self.model.Extension.selections if len(call) > 1 and call[1] == "FACE"]
        self.assertGreaterEqual(len(face_selections), 1)
        self.assertFalse(any(abs(float(call[2])) < 1e-12 and abs(float(call[3])) < 1e-12 and abs(float(call[4]) - 0.012) < 1e-9 for call in face_selections))
        self.assertEqual(len(self.model.FeatureManager.cuts), 1)

    def test_base_plate_records_actual_top_z_from_feature_faces(self):
        self.model.FeatureManager = SequencedExtrusionFeatureManager([
            BoxFeature([(-0.06, -0.04, -0.015, 0.06, 0.04, 0.0)]),
        ])
        state = {}

        create_base_plate(self.model, {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}, state)

        self.assertAlmostEqual(state["base"]["top_z_m"], 0.0)
        self.assertAlmostEqual(state["base"]["bottom_z_m"], -0.015)

    def test_base_plate_falls_back_when_feature_faces_are_not_readable(self):
        self.model.FeatureManager = SequencedExtrusionFeatureManager([
            GetFacesRejectingFeature(),
        ])
        state = {}

        create_base_plate(self.model, {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}, state)

        self.assertAlmostEqual(state["base"]["top_z_m"], 0.015)
        self.assertAlmostEqual(state["base"]["bottom_z_m"], 0.0)

    def test_center_boss_uses_recorded_base_top_z_instead_of_nominal_thickness(self):
        self.model.FeatureManager = SequencedExtrusionFeatureManager([
            BoxFeature([(-0.06, -0.04, -0.015, 0.06, 0.04, 0.0)]),
            BoxFeature([(-0.01, -0.01, 0.0, 0.01, 0.01, 0.02)]),
        ])
        state = {}

        create_base_plate(self.model, {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}, state)
        create_center_boss(self.model, {"diameter": 20, "height": 20}, state)

        face_selections = [call for call in self.model.Extension.selections if len(call) > 1 and call[1] == "FACE"]
        self.assertGreaterEqual(len(face_selections), 1)
        self.assertAlmostEqual(float(face_selections[-1][4]), 0.0)
        self.assertAlmostEqual(state["boss"]["top_z_m"], 0.02)

    def test_top_face_selection_uses_recorded_base_top_z(self):
        self.model.Extension = CenterRejectingFaceExtension()
        self.state["base"]["top_z_m"] = 0.0
        self.state["boss"] = {"diameter": 20, "height": 15}

        cut_slot(self.model, {"plane": "top_face", "center": [-35, 0], "length": 80, "width": 10, "direction": "y", "depth": 7.5}, self.state)

        face_selections = [call for call in self.model.Extension.selections if len(call) > 1 and call[1] == "FACE"]
        self.assertGreaterEqual(len(face_selections), 1)
        self.assertTrue(any(abs(float(call[4])) < 1e-12 for call in face_selections))
        self.assertFalse(any(abs(float(call[4]) - 0.012) < 1e-9 for call in face_selections))

    def test_top_face_selection_prefers_base_feature_top_face(self):
        base_feature = SelectableFeature("BaseExtrude", (-0.06, -0.04, 0.0, 0.06, 0.04, 0.015))
        self.state["base"]["feature"] = base_feature
        self.state["base"]["top_z_m"] = 0.015

        cut_slot(self.model, {"plane": "top_face", "center": [0, 0], "length": 40, "width": 10, "depth": 5}, self.state)

        self.assertGreater(base_feature.top_face.select2_calls + base_feature.top_face.select4_calls, 0)

    def test_center_boss_prefers_base_feature_top_face(self):
        base_feature = SelectableFeature("BaseExtrude", (-0.06, -0.04, 0.0, 0.06, 0.04, 0.015))
        state = {"base": {"length": 120, "width": 80, "thickness": 15, "top_z_m": 0.015, "feature": base_feature}}
        self.model.FeatureManager = SequencedExtrusionFeatureManager([
            BoxFeature([(-0.01, -0.01, 0.015, 0.01, 0.01, 0.03)]),
        ])

        create_center_boss(self.model, {"diameter": 20, "height": 15}, state)

        self.assertGreater(base_feature.top_face.select2_calls + base_feature.top_face.select4_calls, 0)

    def test_corner_holes_prefer_base_feature_top_face(self):
        base_feature = SelectableFeature("BaseExtrude", (-0.06, -0.04, 0.0, 0.06, 0.04, 0.015))
        state = {"base": {"length": 120, "width": 80, "thickness": 15, "top_z_m": 0.015, "feature": base_feature}}

        cut_corner_holes(self.model, {"diameter": 10, "edge_margin": 10}, state)

        self.assertGreater(base_feature.top_face.select2_calls + base_feature.top_face.select4_calls, 0)

    def test_slot_falls_back_to_rectangular_cut_when_native_slot_rejects_signature(self):
        self.model.SketchManager = RejectingSlotSketchManager()

        cut_slot(self.model, {"plane": "top_face", "center": [0, 0], "length": 40, "width": 10, "through_all": True}, self.state)

        self.assertEqual(len(self.model.SketchManager.rectangles), 1)
        self.assertEqual(len(self.model.FeatureManager.cuts), 1)

    def test_slot_falls_back_to_rectangular_cut_when_native_slot_is_unavailable(self):
        self.model.SketchManager = NoSlotSketchManager()

        cut_slot(self.model, {"plane": "top_face", "center": [0, 0], "length": 40, "width": 10, "through_all": True}, self.state)

        self.assertEqual(len(self.model.SketchManager.rectangles), 1)
        self.assertEqual(len(self.model.FeatureManager.cuts), 1)

    def test_blind_slot_retries_with_reverse_direction_when_default_cut_returns_none(self):
        self.model.FeatureManager = ReverseRetryBlindCutFeatureManager()

        cut_slot(self.model, {"plane": "top_face", "center": [0, 0], "length": 40, "width": 10, "depth": 5}, self.state)

        self.assertEqual(len(self.model.FeatureManager.cuts), 2)
        self.assertFalse(self.model.FeatureManager.cuts[0][2])
        self.assertTrue(self.model.FeatureManager.cuts[1][2])

    def test_blind_pocket_retries_with_reverse_direction_when_default_cut_returns_none(self):
        self.model.FeatureManager = ReverseRetryBlindCutFeatureManager()

        cut_rectangle_pocket(self.model, {"plane": "top_face", "center": [0, 0], "length": 10, "width": 8, "depth": 4}, self.state)

        self.assertEqual(len(self.model.FeatureManager.cuts), 2)
        self.assertFalse(self.model.FeatureManager.cuts[0][2])
        self.assertTrue(self.model.FeatureManager.cuts[1][2])

    def test_blind_hole_retries_with_reverse_direction_when_default_cut_returns_none(self):
        self.model.FeatureManager = ReverseRetryBlindCutFeatureManager()

        create_blind_hole(self.model, {"plane": "top_face", "center": [0, 0], "diameter": 6, "depth": 4}, self.state)

        self.assertEqual(len(self.model.FeatureManager.cuts), 2)
        self.assertFalse(self.model.FeatureManager.cuts[0][2])
        self.assertTrue(self.model.FeatureManager.cuts[1][2])

    def test_material_property_dimension_reference_geometry_fixed_paths(self):
        set_material(self.model, {"material": "Aluminum_6061"}, self.state)
        set_custom_property(self.model, {"key": "PartNumber", "value": "P-001"}, self.state)
        modify_named_dimension(self.model, {"dimension_name": "D_base_length", "value": 150}, self.state)
        create_offset_plane(self.model, {"name": "Plane_Offset_01", "base_plane": "Top", "offset": 25}, self.state)
        create_axis(self.model, {"name": "Axis_01", "reference_type": "two_planes", "references": ["Front", "Right"]}, self.state)
        self.assertEqual(len(self.model.material_calls), 1)
        self.assertEqual(len(self.model.Extension.property_manager.calls), 1)
        self.assertAlmostEqual(self.model.dimension.SystemValue, 0.15)
        self.assertEqual(len(self.model.FeatureManager.planes), 1)
        self.assertEqual(len(self.model.FeatureManager.axes), 1)

    def test_material_uses_project_catalog_entry_for_enterprise_material(self):
        model = VerifyingMaterialModel("6061 Alloy")
        state = {}

        set_material(model, {"material": "Aluminum_6061"}, state)

        self.assertEqual(model.material_calls[0], ("", "SOLIDWORKS Materials", "6061 Alloy"))
        self.assertEqual(state["solidworks_material"]["material_id"], "Aluminum_6061")
        self.assertEqual(state["solidworks_material"]["name"], "6061 Alloy")
        self.assertNotIn("material_unverified", state)

    def test_material_alias_resolves_through_project_catalog(self):
        model = VerifyingMaterialModel("6061 Alloy")
        state = {}

        set_material(model, {"material": "6061"}, state)

        self.assertEqual(model.material_calls[0], ("", "SOLIDWORKS Materials", "6061 Alloy"))
        self.assertEqual(state["material"], "Aluminum_6061")

    def test_material_verification_accepts_project_catalog_alias_returned_by_solidworks(self):
        model = VerifyingMaterialModel("6061 Alloy", reported_name="Aluminum 6061")
        state = {}

        set_material(model, {"material": "Aluminum_6061"}, state)

        self.assertEqual(state["solidworks_material"]["material_id"], "Aluminum_6061")

    def test_material_tries_project_catalog_candidates_until_verified(self):
        model = VerifyingMaterialModel("6061-T6 (SS)")
        state = {}

        set_material(model, {"material": "Aluminum_6061"}, state)

        self.assertGreater(len(model.material_calls), 1)
        self.assertEqual(state["solidworks_material"]["name"], "6061-T6 (SS)")

    def test_material_empty_getter_marks_unverified_without_blocking_execution(self):
        model = EmptyMaterialGetterModel("6061 Alloy")
        state = {}

        set_material(model, {"material": "Aluminum_6061"}, state)

        self.assertTrue(state["material_unverified"])
        self.assertIn("getter returned <empty>", state["material_unverified_reason"])
        self.assertEqual(state["solidworks_material"]["material_id"], "Aluminum_6061")

    def test_material_id_parameter_resolves_through_project_catalog(self):
        model = VerifyingMaterialModel("6061 Alloy")
        state = {}

        set_material(model, {"material_id": "Aluminum_6061"}, state)

        self.assertEqual(model.material_calls[0], ("", "SOLIDWORKS Materials", "6061 Alloy"))
        self.assertEqual(state["material"], "Aluminum_6061")

    def test_material_unknown_catalog_entry_is_rejected(self):
        model = VerifyingMaterialModel("Titanium Freeform")

        with self.assertRaisesRegex(RuntimeError, "official SOLIDWORKS material catalog"):
            set_material(model, {"material": "Titanium_Freeform"}, {})

    def test_material_raises_when_project_catalog_entry_cannot_be_verified(self):
        model = RejectingMaterialModel()

        with self.assertRaisesRegex(RuntimeError, "different material"):
            set_material(model, {"material": "Aluminum_6061"}, {})


if __name__ == "__main__":
    unittest.main()


class TestSemanticHostExecutorSelection(unittest.TestCase):
    def test_cut_slot_host_base_selects_base_top_face_even_when_boss_exists(self):
        model = FakeModel()
        base_feature = SelectableFeature("BaseExtrude", (-0.06, -0.04, 0.0, 0.06, 0.04, 0.015))
        boss_feature = SelectableFeature("BossExtrude", (-0.01, -0.01, 0.015, 0.01, 0.01, 0.03))
        state = {
            "base": {"length": 120, "width": 80, "thickness": 15, "top_z_m": 0.015, "feature": base_feature},
            "boss": {"diameter": 20, "height": 15, "top_z_m": 0.03, "feature": boss_feature},
        }

        cut_slot(model, {"plane": "top_face", "host": "base", "center": [0, 0], "length": 40, "width": 8, "depth": 5}, state)

        self.assertGreater(base_feature.top_face.select2_calls + base_feature.top_face.select4_calls, 0)
        self.assertEqual(boss_feature.top_face.select2_calls + boss_feature.top_face.select4_calls, 0)

    def test_create_through_hole_host_boss_selects_boss_top_face(self):
        model = FakeModel()
        base_feature = SelectableFeature("BaseExtrude", (-0.06, -0.04, 0.0, 0.06, 0.04, 0.015))
        boss_feature = SelectableFeature("BossExtrude", (-0.01, -0.01, 0.015, 0.01, 0.01, 0.03))
        state = {
            "base": {"length": 120, "width": 80, "thickness": 15, "top_z_m": 0.015, "feature": base_feature},
            "boss": {"diameter": 20, "height": 15, "top_z_m": 0.03, "feature": boss_feature},
        }

        create_through_hole(model, {"plane": "top_face", "host": "boss", "center": [0, 0], "diameter": 6}, state)

        self.assertEqual(base_feature.top_face.select2_calls + base_feature.top_face.select4_calls, 0)
        self.assertGreater(boss_feature.top_face.select2_calls + boss_feature.top_face.select4_calls, 0)
