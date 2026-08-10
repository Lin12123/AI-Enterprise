import json
import unittest

from app.config import JOBS_DIR, PROJECT_ROOT
from app.job_writer import write_cadplan_json, write_job_ini
from app.validator import validate_cadplan


def valid_plan():
    return validate_cadplan(
        {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"length": 120, "width": 80, "thickness": 12},
            "corner_holes": {
                "enabled": True,
                "diameter": 6.6,
                "offset_x": 50,
                "offset_y": 30,
                "through_all": True,
            },
            "center_boss": {"enabled": True, "diameter": 30, "height": 25},
            "center_hole": {"enabled": True, "diameter": 10, "through_all": True},
            "fillet": {"enabled": True, "radius": 3},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
        }
    )


class TestJobWriter(unittest.TestCase):
    def test_write_current_cadplan_json(self):
        path = write_cadplan_json(valid_plan())
        self.assertEqual(path, JOBS_DIR / "current_cadplan.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["template"], "mounting_plate")

    def test_write_current_job_ini(self):
        path = write_job_ini(valid_plan())
        self.assertEqual(path, JOBS_DIR / "current_job.ini")
        self.assertTrue(path.exists())

    def test_job_ini_contains_base_dimensions(self):
        text = write_job_ini(valid_plan()).read_text(encoding="utf-8")
        self.assertIn("base_shape=rectangle", text)
        self.assertIn("base_length=120", text)
        self.assertIn("base_width=80", text)
        self.assertIn("base_thickness=12", text)

    def test_job_ini_contains_circle_base(self):
        plan = validate_cadplan(
            {
                "template": "mounting_plate",
                "unit": "mm",
                "part_name": "ai_mounting_plate",
                "base": {"shape": "circle", "diameter": 100, "thickness": 10},
                "center_boss": {"enabled": True, "diameter": 30, "height": 100},
            }
        )
        text = write_job_ini(plan).read_text(encoding="utf-8")
        self.assertIn("base_shape=circle", text)
        self.assertIn("base_diameter=100", text)
        self.assertIn("base_length=100", text)
        self.assertIn("base_width=100", text)
        self.assertIn("center_boss_height=100", text)

    def test_job_ini_does_not_contain_output_dir(self):
        text = write_job_ini(valid_plan()).read_text(encoding="utf-8")
        self.assertNotIn("output_dir", text)

    def test_booleans_are_lowercase(self):
        text = write_job_ini(valid_plan()).read_text(encoding="utf-8")
        self.assertIn("corner_holes_enabled=true", text)
        self.assertNotIn("True", text)
        self.assertNotIn("False", text)

    def test_user_output_dir_rejected(self):
        plan = valid_plan()
        plan["output_dir"] = "C:\\Windows\\System32"
        with self.assertRaises(ValueError):
            write_job_ini(plan)

    def test_writes_stay_inside_workspace(self):
        json_path = write_cadplan_json(valid_plan()).resolve()
        ini_path = write_job_ini(valid_plan()).resolve()
        root = PROJECT_ROOT.resolve()
        self.assertIn(root, json_path.parents)
        self.assertIn(root, ini_path.parents)
        self.assertIn(JOBS_DIR.resolve(), json_path.parents)
        self.assertIn(JOBS_DIR.resolve(), ini_path.parents)


if __name__ == "__main__":
    unittest.main()
