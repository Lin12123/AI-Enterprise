import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cad_dsl.feature_registry import default_registry
from solidworks_api.executor import SolidWorksApiExecutor
from solidworks_api.session import SolidWorksSession


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


class GuardedSession(SolidWorksSession):
    def __init__(self):
        super().__init__()
        self.connect_called = False

    def connect(self) -> None:
        self.connect_called = True
        raise AssertionError("dry_run must not connect to SolidWorks")


def p0_full_plan():
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": "p0_full_regression",
        "operations": [
            {"id": "new_001", "op": "create_new_part", "params": {}},
            {"id": "sketch_base", "op": "create_sketch", "params": {"name": "sketch_base", "plane": "Top"}},
            {
                "id": "rect_001",
                "op": "sketch_center_rectangle",
                "params": {"sketch": "sketch_base", "center": [0, 0], "length": 100, "width": 60},
            },
            {"id": "boss_001", "op": "extrude_boss", "params": {"sketch": "sketch_base", "depth": 10}},
            {"id": "sketch_hole", "op": "create_sketch", "params": {"name": "sketch_hole", "plane": "top_face"}},
            {"id": "circle_001", "op": "sketch_circle", "params": {"sketch": "sketch_hole", "center": [0, 0], "diameter": 10}},
            {"id": "cut_001", "op": "extrude_cut", "params": {"sketch": "sketch_hole", "through_all": True}},
            {"id": "hole_001", "op": "create_through_hole", "params": {"plane": "top_face", "center": [20, 0], "diameter": 6}},
            {"id": "fillet_001", "op": "add_fillet", "params": {"radius": 2, "target": "outer_edges"}},
            {"id": "rebuild_001", "op": "rebuild_model", "params": {}},
            {"id": "validate_001", "op": "validate_rebuild", "params": {}},
            {"id": "save_001", "op": "save_sldprt", "params": {}},
            {"id": "step_001", "op": "export_step", "params": {}},
            {"id": "png_001", "op": "capture_png", "params": {}},
        ],
        "outputs": {"save_sldprt": False, "export_step": False, "capture_png": False},
    }


class TestP0Regression(unittest.TestCase):
    def test_p0_13_operations_remain_registered_and_implemented(self):
        registry = default_registry()
        for op in P0_OPERATIONS:
            with self.subTest(op=op):
                definition = registry.require(op)
                self.assertEqual(definition.status, "implemented")
                self.assertTrue(definition.executor_function)
                self.assertTrue(definition.parameter_schema)

    def test_p0_full_featureplan_dry_run_still_passes(self):
        session = GuardedSession()
        result = SolidWorksApiExecutor(session=session).dry_run(p0_full_plan())
        self.assertEqual(result.status, "dry_run", result)
        self.assertFalse(session.connect_called)
        self.assertEqual(result.outputs, ())

    def test_p0_safety_rejections_still_apply(self):
        plan = p0_full_plan()
        plan["operations"][1]["params"]["script"] = "bad"
        session = GuardedSession()
        result = SolidWorksApiExecutor(session=session).dry_run(plan)
        self.assertEqual(result.status, "blocked")
        self.assertFalse(session.connect_called)
        self.assertTrue(any("禁止" in operation.message for operation in result.operations))

    def test_p1_did_not_change_p0_required_schema(self):
        registry = default_registry()
        self.assertEqual(set(registry.require("create_through_hole").required_parameters), {"plane", "center", "diameter"})
        self.assertEqual(set(registry.require("add_fillet").required_parameters), {"radius"})
        self.assertEqual(set(registry.require("extrude_boss").required_parameters), {"sketch", "depth"})


if __name__ == "__main__":
    unittest.main()
