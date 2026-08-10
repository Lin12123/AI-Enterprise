import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from solidworks_api.executor import SolidWorksApiExecutor
from solidworks_api.session import SolidWorksSession


class GuardedSession(SolidWorksSession):
    def __init__(self):
        super().__init__()
        self.connect_called = False

    def connect(self) -> None:
        self.connect_called = True
        raise AssertionError("dry_run must not connect to SolidWorks")


def p1_plan():
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": "p1_dryrun",
        "operations": [
            {"id": "new_001", "op": "create_new_part", "params": {}},
            {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12}},
            {
                "id": "blind_001",
                "op": "create_blind_hole",
                "params": {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": 5},
            },
            {
                "id": "pocket_001",
                "op": "cut_rectangle_pocket",
                "params": {"plane": "top_face", "center": [20, 0], "length": 30, "width": 15, "depth": 4},
            },
            {"id": "chamfer_001", "op": "add_chamfer", "params": {"distance": 2, "angle": 45, "target": "outer_edges"}},
            {
                "id": "cbore_001",
                "op": "create_counterbore_hole",
                "params": {"plane": "top_face", "center": [0, 20], "hole_diameter": 6, "counterbore_diameter": 12, "counterbore_depth": 3},
            },
            {
                "id": "csink_001",
                "op": "create_countersink_hole",
                "params": {"plane": "top_face", "center": [0, -20], "hole_diameter": 6, "countersink_diameter": 12, "angle": 90},
            },
            {"id": "slot_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [0, 0], "length": 30, "width": 8, "through_all": False, "depth": 5}},
            {"id": "linear_001", "op": "create_linear_pattern", "params": {"seed_feature": "blind_001", "direction": "x", "count": 3, "spacing": 20}},
            {"id": "circular_001", "op": "create_circular_pattern", "params": {"seed_feature": "blind_001", "axis": "center_axis", "count": 6, "angle": 360}},
            {"id": "mirror_001", "op": "mirror_feature", "params": {"seed_feature": "pocket_001", "mirror_plane": "Front"}},
            {"id": "material_001", "op": "set_material", "params": {"material": "6061 Alloy"}},
            {"id": "property_001", "op": "set_custom_property", "params": {"key": "PartNumber", "value": "P-001"}},
            {"id": "modify_001", "op": "modify_named_dimension", "params": {"dimension_name": "D_base_length", "value": 150}},
            {"id": "plane_001", "op": "create_offset_plane", "params": {"name": "Plane_Offset_01", "base_plane": "Top", "offset": 25}},
            {"id": "axis_001", "op": "create_axis", "params": {"name": "Axis_01", "reference_type": "two_planes", "references": ["Front", "Right"]}},
        ],
        "outputs": {"save_sldprt": True, "export_step": False, "capture_png": False},
    }


class TestP1ApiExecutorDryRun(unittest.TestCase):
    def test_p1_implemented_plan_dry_run_does_not_connect(self):
        session = GuardedSession()
        result = SolidWorksApiExecutor(session=session).dry_run(p1_plan())
        self.assertEqual(result.status, "dry_run")
        self.assertFalse(session.connect_called)
        self.assertEqual([op.operation_type for op in result.operations], [
            "create_new_part",
            "create_base_plate",
            "create_blind_hole",
            "cut_rectangle_pocket",
            "add_chamfer",
            "create_counterbore_hole",
            "create_countersink_hole",
            "cut_slot",
            "create_linear_pattern",
            "create_circular_pattern",
            "mirror_feature",
            "set_material",
            "set_custom_property",
            "modify_named_dimension",
            "create_offset_plane",
            "create_axis",
        ])

    def test_p2_scaffolded_dry_run_is_blocked_before_connection(self):
        plan = p1_plan()
        plan["operations"].append(
            {"id": "revolve_001", "op": "create_revolve_boss", "params": {"profile": "profile_001", "axis": "axis_001", "angle": 360}}
        )
        session = GuardedSession()
        result = SolidWorksApiExecutor(session=session).dry_run(plan)
        self.assertEqual(result.status, "blocked")
        self.assertFalse(session.connect_called)


if __name__ == "__main__":
    unittest.main()
