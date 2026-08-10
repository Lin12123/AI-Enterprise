import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cad_dsl.feature_registry import default_registry
from solidworks_api.model_builder import DISPATCH


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATRIX = PROJECT_ROOT / "docs" / "solidworks_feature_capability_matrix.md"

P1_OPERATIONS = (
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
)

P2_P3_NOT_IMPLEMENTED = (
    "create_revolve_boss",
    "create_revolve_cut",
    "create_sweep_boss",
    "create_sweep_cut",
    "create_loft_boss",
    "create_loft_cut",
    "add_shell",
    "add_rib",
    "add_draft",
    "create_reference_plane",
    "create_reference_axis",
)


def matrix_rows():
    rows = {}
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "`" not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 6:
            continue
        match = re.search(r"`([^`]+)`", cells[2])
        if not match:
            continue
        op = match.group(1)
        rows.setdefault(op, []).append(cells)
    return rows


class TestCapabilityMatrixConsistency(unittest.TestCase):
    def test_p1_operations_are_in_capability_matrix_with_registry_status(self):
        registry = default_registry()
        rows = matrix_rows()
        for op in P1_OPERATIONS:
            with self.subTest(op=op):
                self.assertIn(op, rows)
                statuses = {row[3] for row in rows[op]}
                self.assertEqual(statuses, {registry.require(op).status})
                self.assertTrue(any(row[4].strip("`").startswith("src/") for row in rows[op]))
                self.assertTrue(any(row[5] and row[5] != "-" for row in rows[op]))

    def test_p2_p3_registry_statuses_are_not_implemented(self):
        registry = default_registry()
        for op in P2_P3_NOT_IMPLEMENTED:
            with self.subTest(op=op):
                self.assertIn(registry.require(op).status, {"scaffolded", "planned"})
                self.assertNotEqual(registry.require(op).status, "implemented")

    def test_executor_dispatch_contains_only_implemented_registry_operations(self):
        registry = default_registry()
        for op in DISPATCH:
            with self.subTest(op=op):
                self.assertEqual(registry.require(op).status, "implemented")

    def test_readme_does_not_claim_all_official_api_support(self):
        text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("已支持所有 solidworks 官方接口", text)
        self.assertNotIn("support all official solidworks", text)
        self.assertIn("does not claim support for every official solidworks feature api", text)


if __name__ == "__main__":
    unittest.main()
