import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cad_dsl.featureplan import FeaturePlan
from solidworks_api.executor import SolidWorksApiExecutor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = PROJECT_ROOT / "examples" / "featureplans"


class TestP1FeaturePlanExamples(unittest.TestCase):
    def test_p1_full_dryrun_example_exists(self):
        self.assertTrue((EXAMPLE_DIR / "p1_full_dryrun.json").exists())

    def test_all_p1_examples_parse_as_featureplans(self):
        for path in EXAMPLE_DIR.glob("p1_*.json"):
            with self.subTest(path=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                plan = FeaturePlan.from_dict(data)
                self.assertEqual(plan.unit, "mm")
                self.assertEqual(plan.document_type, "part")
                self.assertTrue(plan.operations)

    def test_implemented_p1_examples_dry_run(self):
        for path in EXAMPLE_DIR.glob("p1_*.json"):
            with self.subTest(name=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                result = SolidWorksApiExecutor().dry_run(data)
                self.assertEqual(result.status, "dry_run")

    def test_p1_examples_do_not_include_user_paths_or_code_fields(self):
        forbidden = {
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
        }
        for path in EXAMPLE_DIR.glob("p1_*.json"):
            text = path.read_text(encoding="utf-8")
            for word in forbidden:
                self.assertNotIn(f'"{word}"', text, path.name)


if __name__ == "__main__":
    unittest.main()
