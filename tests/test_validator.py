import unittest

from app.validator import validate_cadplan


def valid_plan():
    return {
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


class TestValidator(unittest.TestCase):
    def test_valid_mounting_plate_passes(self):
        self.assertEqual(validate_cadplan(valid_plan())["template"], "mounting_plate")

    def test_blank_part_passes_without_base(self):
        plan = validate_cadplan(
            {
                "template": "blank_part",
                "unit": "mm",
                "part_name": "test_part",
                "outputs": {"save_sldprt": True},
            }
        )
        self.assertEqual(plan["template"], "blank_part")
        self.assertEqual(plan["part_name"], "test_part")
        self.assertNotIn("base", plan)
        self.assertTrue(plan["outputs"]["save_sldprt"])
        self.assertFalse(plan["outputs"]["export_step"])
        self.assertFalse(plan["outputs"]["capture_png"])

    def test_negative_size_rejected(self):
        plan = valid_plan()
        plan["base"]["length"] = -1
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_oversized_size_rejected(self):
        plan = valid_plan()
        plan["base"]["length"] = 1001
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_hole_diameter_too_large_rejected(self):
        plan = valid_plan()
        plan["corner_holes"]["diameter"] = 50
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_hole_position_out_of_bounds_rejected(self):
        plan = valid_plan()
        plan["corner_holes"]["offset_x"] = 60
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_enabled_corner_holes_missing_diameter_uses_fallback(self):
        plan = valid_plan()
        del plan["corner_holes"]["diameter"]
        validated = validate_cadplan(plan)
        self.assertEqual(validated["corner_holes"]["diameter"], 6.6)

    def test_enabled_features_missing_numbers_use_fallbacks(self):
        plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "base": {"shape": "rectangle"},
            "corner_holes": {"enabled": True, "through_all": True},
            "center_boss": {"enabled": True},
            "center_hole": {"enabled": True, "through_all": True},
            "fillet": {"enabled": True},
        }
        validated = validate_cadplan(plan)
        self.assertEqual(validated["base"]["length"], 120)
        self.assertEqual(validated["base"]["width"], 80)
        self.assertEqual(validated["base"]["thickness"], 12)
        self.assertEqual(validated["corner_holes"]["diameter"], 6.6)
        self.assertEqual(validated["center_boss"]["diameter"], 30)
        self.assertEqual(validated["center_boss"]["height"], 25)
        self.assertEqual(validated["center_hole"]["diameter"], 10)
        self.assertEqual(validated["fillet"]["radius"], 2)

    def test_center_hole_larger_than_boss_rejected(self):
        plan = valid_plan()
        plan["center_hole"]["diameter"] = 35
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_center_hole_on_base_without_boss_passes(self):
        plan = valid_plan()
        plan["center_boss"] = {"enabled": False}
        plan["center_hole"] = {"enabled": True, "diameter": 10, "through_all": True}
        validated = validate_cadplan(plan)
        self.assertEqual(validated["center_hole"]["target"], "base")
        self.assertEqual(validated["center_hole"]["diameter"], 10)

    def test_center_hole_on_base_too_large_rejected(self):
        plan = valid_plan()
        plan["center_boss"] = {"enabled": False}
        plan["center_hole"] = {"enabled": True, "diameter": 90, "through_all": True}
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_fillet_too_large_rejected(self):
        plan = valid_plan()
        plan["fillet"]["radius"] = 7
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_non_mounting_plate_template_rejected(self):
        plan = valid_plan()
        plan["template"] = "gear"
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_invalid_part_name_rejected(self):
        plan = valid_plan()
        plan["part_name"] = "../bad"
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_output_dir_field_rejected(self):
        plan = valid_plan()
        plan["output_dir"] = "workspace/outputs"
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_path_fields_rejected(self):
        for field in ("path", "save_path", "absolute_path"):
            plan = valid_plan()
            plan[field] = "workspace/outputs"
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_cadplan(plan)

    def test_nested_dangerous_runtime_content_rejected(self):
        plan = valid_plan()
        plan["notes"] = ["generate Python script"]
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_chinese_runtime_and_delete_content_rejected(self):
        for text in ("自动生成 VBA 宏运行", "删除旧文件"):
            plan = valid_plan()
            plan["notes"] = [text]
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_cadplan(plan)

    def test_nested_dangerous_runtime_field_rejected(self):
        plan = valid_plan()
        plan["outputs"]["macro"] = "run"
        with self.assertRaises(ValueError):
            validate_cadplan(plan)

    def test_windows_system32_intent_rejected(self):
        plan = valid_plan()
        plan["notes"] = ["保存到 C:\\Windows\\System32"]
        with self.assertRaises(ValueError):
            validate_cadplan(plan)


if __name__ == "__main__":
    unittest.main()
