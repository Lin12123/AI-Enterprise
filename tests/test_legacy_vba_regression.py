import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import executor_mode, run_legacy_vba
from app.job_writer import write_cadplan_json, write_job_ini
from app.validator import validate_cadplan


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestLegacyVbaRegression(unittest.TestCase):
    def test_legacy_vba_files_still_exist(self):
        self.assertTrue((PROJECT_ROOT / "app" / "job_writer.py").exists())
        self.assertTrue((PROJECT_ROOT / "macros" / "AI_MVP_Runner.bas").exists())
        self.assertTrue((PROJECT_ROOT / "macros" / "AI_Enterprise_Runner.bas").exists())

    def test_default_executor_mode_is_legacy_vba(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(executor_mode(), "legacy_vba")

    def test_env_legacy_vba_mode_is_accepted(self):
        with patch.dict("os.environ", {"AI_SW_EXECUTOR_MODE": "legacy_vba"}, clear=True):
            self.assertEqual(executor_mode(), "legacy_vba")

    def test_legacy_vba_job_ini_flow_still_writes_controlled_job_files(self):
        cadplan = validate_cadplan(
            {
                "template": "mounting_plate",
                "unit": "mm",
                "part_name": "ai_mounting_plate",
                "base": {"length": 120, "width": 80, "thickness": 12},
                "corner_holes": {"enabled": True, "diameter": 6.6, "offset_x": 50, "offset_y": 30},
                "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            }
        )

        cadplan_path = write_cadplan_json(cadplan)
        job_path = write_job_ini(cadplan)
        job_text = job_path.read_text(encoding="utf-8")

        self.assertTrue(str(cadplan_path).endswith(r"workspace\jobs\current_cadplan.json"))
        self.assertTrue(str(job_path).endswith(r"workspace\jobs\current_job.ini"))
        self.assertIn("template=mounting_plate", job_text)
        self.assertIn("unit=mm", job_text)
        self.assertIn("base_length=120", job_text)
        self.assertIn("corner_holes_enabled=true", job_text)
        self.assertNotIn("output_dir", job_text)
        self.assertNotIn("script", job_text)
        self.assertNotIn("macro", job_text)

    def test_legacy_vba_mode_can_generate_current_job_ini_without_running_macro(self):
        cadplan = validate_cadplan(
            {
                "template": "mounting_plate",
                "unit": "mm",
                "part_name": "legacy_mode_regression",
                "base": {"length": 120, "width": 80, "thickness": 12},
                "outputs": {"save_sldprt": True, "export_step": False, "capture_png": False},
            }
        )
        with patch("builtins.input", return_value="y"):
            exit_code = run_legacy_vba(cadplan)

        job_path = PROJECT_ROOT / "workspace" / "jobs" / "current_job.ini"
        self.assertEqual(exit_code, 0)
        self.assertTrue(job_path.exists())
        self.assertIn("template=mounting_plate", job_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
