import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cad_dsl import material_catalog
from cad_dsl.material_catalog import catalog_path, load_material_catalog, prompt_material_lines, resolve_material


class TestMaterialCatalog(unittest.TestCase):
    def test_catalog_loads_project_materials(self):
        records = load_material_catalog()
        ids = {record.material_id for record in records}

        self.assertIn("Aluminum_6061", ids)
        self.assertIn("Steel_304", ids)

    def test_resolve_material_by_id_search_term_and_solidworks_name(self):
        by_id = resolve_material("Aluminum_6061")
        by_search_term = resolve_material("aluminum alloy 6061")
        by_solidworks_name = resolve_material("6061 Alloy")

        self.assertIsNotNone(by_id)
        self.assertEqual(by_id.material_id, "Aluminum_6061")
        self.assertEqual(by_search_term.material_id, "Aluminum_6061")
        self.assertEqual(by_solidworks_name.material_id, "Aluminum_6061")

    def test_unknown_material_is_not_resolved(self):
        self.assertIsNone(resolve_material("Titanium_Freeform"))

    def test_catalog_exposes_solidworks_candidates(self):
        record = resolve_material("Aluminum_6061")

        self.assertIn(("SOLIDWORKS Materials", "6061 Alloy"), record.solidworks_candidates)
        self.assertIn(("SOLIDWORKS Materials", "6061-T6 (SS)"), record.solidworks_candidates)

    def test_prompt_material_lines_expose_official_material_names_without_paths(self):
        lines = prompt_material_lines()
        text = "\n".join(lines)

        self.assertIn("material_id=Aluminum_6061", text)
        self.assertIn("output material='6061 Alloy'", text)
        self.assertNotIn("path", text.lower())


if __name__ == "__main__":
    unittest.main()
