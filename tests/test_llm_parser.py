import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.llm_parser import parse_prompt_to_cadplan, parse_prompt_with_rules
from app.validator import validate_cadplan


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestLlmParser(unittest.TestCase):
    def test_default_uses_rule_parser_without_llm(self):
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "0"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm") as llm:
                plan = validate_cadplan(parse_prompt_to_cadplan("120x80x12mm"))
        llm.assert_not_called()
        self.assertEqual(plan["base"]["length"], 120)

    def test_blank_part_prompt_does_not_default_to_mounting_plate(self):
        prompt = "\u65b0\u5efa\u4e00\u4e2a\u7a7a\u767d\u96f6\u4ef6\uff0c\u4f7f\u7528\u9ed8\u8ba4\u6beb\u7c73\u6a21\u677f\uff0c\u4fdd\u5b58\u4e3a\u6d4b\u8bd5\u96f6\u4ef6\u3002"
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "0"}, clear=False):
            plan = parse_prompt_to_cadplan(prompt)

        self.assertEqual(plan["template"], "blank_part")
        self.assertEqual(plan["part_name"], "test_part")
        self.assertNotIn("base", plan)
        self.assertTrue(plan["outputs"]["save_sldprt"])
        self.assertFalse(plan["outputs"]["export_step"])
        self.assertFalse(plan["outputs"]["capture_png"])

    def test_cuboid_part_prompt_with_dimensions_is_not_blank_part(self):
        prompt = "\u521b\u5efa\u4e00\u4e2a 120\u00d780\u00d712mm \u7684\u957f\u65b9\u4f53\u96f6\u4ef6\u3002"
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "0"}, clear=False):
            plan = parse_prompt_to_cadplan(prompt)

        self.assertEqual(plan["template"], "mounting_plate")
        self.assertEqual(plan["base"]["shape"], "rectangle")
        self.assertEqual(plan["base"]["length"], 120)
        self.assertEqual(plan["base"]["width"], 80)
        self.assertEqual(plan["base"]["thickness"], 12)

    def test_cuboid_with_center_through_hole_without_boss_passes(self):
        prompt = "\u521b\u5efa\u4e00\u4e2a 120\u00d780\u00d712mm \u7684\u957f\u65b9\u4f53\u96f6\u4ef6\uff0c\u5728\u4e2d\u5fc3\u5f00\u4e00\u4e2a\u76f4\u5f84 10mm \u7684\u901a\u5b54\u3002"
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "0"}, clear=False):
            plan = parse_prompt_to_cadplan(prompt)

        self.assertEqual(plan["template"], "mounting_plate")
        self.assertEqual(plan["base"]["length"], 120)
        self.assertEqual(plan["base"]["width"], 80)
        self.assertEqual(plan["base"]["thickness"], 12)
        self.assertFalse(plan["center_boss"]["enabled"])
        self.assertTrue(plan["center_hole"]["enabled"])
        self.assertEqual(plan["center_hole"]["diameter"], 10)
        self.assertEqual(plan["center_hole"]["target"], "base")

    def test_llm_cuboid_with_center_through_hole_without_boss_passes(self):
        prompt = "\u521b\u5efa\u4e00\u4e2a 120\u00d780\u00d712mm \u7684\u957f\u65b9\u4f53\u96f6\u4ef6\uff0c\u5728\u4e2d\u5fc3\u5f00\u4e00\u4e2a\u76f4\u5f84 10mm \u7684\u901a\u5b54\u3002"
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": 120, "width": 80, "thickness": 12},
            "corner_holes": {"enabled": False, "through_all": True},
            "center_boss": {"enabled": False},
            "center_hole": {"enabled": True, "diameter": 10, "through_all": True},
            "fillet": {"enabled": False},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": [],
        }

        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan(prompt)

        self.assertEqual(plan["center_hole"]["target"], "base")
        self.assertEqual(plan["center_hole"]["diameter"], 10)

    def test_intent_only_part_prompt_uses_llm_recommended_dimensions_not_blank(self):
        prompt = "\u521b\u5efa\u4e00\u4e2a\u7528\u4e8e\u56fa\u5b9a\u5c0f\u7535\u673a\u7684\u96f6\u4ef6\u3002"
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": 140, "width": 90, "thickness": 10},
            "corner_holes": {"enabled": True, "diameter": 5.5, "through_all": True},
            "center_boss": {"enabled": False},
            "center_hole": {"enabled": False, "through_all": True},
            "fillet": {"enabled": True, "radius": 1.5},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": ["intent-only request; dimensions are recommended by LLM"],
        }

        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan(prompt)

        self.assertEqual(plan["template"], "mounting_plate")
        self.assertNotEqual(plan["template"], "blank_part")
        self.assertEqual(plan["base"]["length"], 140)
        self.assertEqual(plan["base"]["width"], 90)
        self.assertEqual(plan["base"]["thickness"], 10)

    def test_rule_parser_handles_compact_chinese_lwh_labels(self):
        prompt = "我需要一个比较简单的固定板，长100宽60厚10，四个角留螺丝孔，用M6间隙孔就行，边缘稍微圆滑一点。"
        plan = validate_cadplan(parse_prompt_with_rules(prompt))

        self.assertEqual(plan["base"]["length"], 100)
        self.assertEqual(plan["base"]["width"], 60)
        self.assertEqual(plan["base"]["thickness"], 10)

    def test_llm_mode_passes_original_prompt_and_uses_model_dimensions(self):
        prompt = "我需要一个比较简单的固定板，长100宽60厚10，四个角留螺丝孔，用M6间隙孔就行，边缘稍微圆滑一点。"
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": 100, "width": 60, "thickness": 10},
            "corner_holes": {"enabled": True, "diameter": 6.6, "through_all": True},
            "center_boss": {"enabled": False},
            "center_hole": {"enabled": False, "through_all": True},
            "fillet": {"enabled": True, "radius": 2},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": [],
        }

        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan) as llm:
                plan = parse_prompt_to_cadplan(prompt)

        llm.assert_called_once_with(prompt)
        self.assertEqual(plan["base"]["length"], 100)
        self.assertEqual(plan["base"]["width"], 60)
        self.assertEqual(plan["base"]["thickness"], 10)
        self.assertEqual(plan["corner_holes"]["offset_x"], 40)
        self.assertEqual(plan["corner_holes"]["offset_y"], 20)

    def test_llm_enabled_without_api_key_falls_back_to_rules(self):
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
                plan = validate_cadplan(parse_prompt_to_cadplan("120x80x12mm"))
        self.assertEqual(plan["base"]["length"], 120)

    def test_llm_dangerous_field_is_rejected_by_validator(self):
        dangerous = {
            "template": "mounting_plate",
            "unit": "mm",
            "base": {"length": 120, "width": 80, "thickness": 12},
            "corner_holes": {"enabled": False, "through_all": True},
            "center_boss": {"enabled": False},
            "center_hole": {"enabled": False, "through_all": True},
            "fillet": {"enabled": False},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "output_dir": "workspace/outputs",
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=dangerous):
                with self.assertRaises(ValueError):
                    parse_prompt_to_cadplan("120x80x12mm")

    def test_llm_m6_corner_hole_string_is_normalized(self):
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": 120, "width": 80, "thickness": 12},
            "corner_holes": {"enabled": True, "diameter": "M6", "through_all": True},
            "center_boss": {"enabled": True, "diameter": 30, "height": 25},
            "center_hole": {"enabled": True, "diameter": 10, "through_all": True},
            "fillet": {"enabled": True, "radius": 3},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": [],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan("四个角打 M6 孔")
        self.assertEqual(plan["corner_holes"]["diameter"], 6.6)

    def test_llm_m6_corner_hole_text_is_normalized(self):
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": 120, "width": 80, "thickness": 12},
            "corner_holes": {"enabled": True, "diameter": "M6孔", "through_all": True},
            "center_boss": {"enabled": False},
            "center_hole": {"enabled": False, "through_all": True},
            "fillet": {"enabled": False},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": [],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan("四个角打 M6 孔")
        self.assertEqual(plan["corner_holes"]["diameter"], 6.6)

    def test_llm_missing_required_corner_hole_diameter_uses_fallback(self):
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": 120, "width": 80, "thickness": 12},
            "corner_holes": {"enabled": True, "through_all": True},
            "center_boss": {"enabled": False},
            "center_hole": {"enabled": False, "through_all": True},
            "fillet": {"enabled": False},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": [],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan("四个角打 M6 孔")
        self.assertEqual(plan["corner_holes"]["diameter"], 6.6)

    def test_llm_truthy_enabled_string_missing_number_uses_fallback(self):
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": 120, "width": 80, "thickness": 12},
            "corner_holes": {"enabled": "需要", "through_all": True},
            "center_boss": {"enabled": False},
            "center_hole": {"enabled": False, "through_all": True},
            "fillet": {"enabled": False},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": [],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan("帮我做一个矩形底板，四角开孔的零件。")
        self.assertEqual(plan["corner_holes"]["diameter"], 6.6)

    def test_llm_missing_required_numbers_use_generic_fallbacks(self):
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle"},
            "corner_holes": {"enabled": True, "through_all": True},
            "center_boss": {"enabled": True},
            "center_hole": {"enabled": True, "through_all": True},
            "fillet": {"enabled": True},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": [],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan("做一个带四角孔、中心凸台、中心孔和圆角的矩形底板")
        self.assertEqual(plan["base"]["length"], 120)
        self.assertEqual(plan["base"]["width"], 80)
        self.assertEqual(plan["base"]["thickness"], 12)
        self.assertEqual(plan["corner_holes"]["diameter"], 6.6)
        self.assertEqual(plan["center_boss"]["diameter"], 30)
        self.assertEqual(plan["center_boss"]["height"], 25)
        self.assertEqual(plan["center_hole"]["diameter"], 10)
        self.assertEqual(plan["fillet"]["radius"], 2)

    def test_schema_requires_dimensions_when_features_are_enabled(self):
        schema = json.loads((PROJECT_ROOT / "schemas" / "cadplan_lite.schema.json").read_text(encoding="utf-8"))
        self.assertIn("allOf", schema["properties"]["corner_holes"])
        self.assertIn("allOf", schema["properties"]["center_boss"])
        self.assertIn("allOf", schema["properties"]["center_hole"])
        self.assertIn("allOf", schema["properties"]["fillet"])

    def test_llm_semantic_mapping_output_is_normalized(self):
        prompt = "帮我做一个安装板，长度大概 120，宽 80，厚 12，四个角打 M6 孔，中间做一个直径 30、高 25 的圆柱凸台，凸台中间再开一个 10 毫米的孔，外边缘做 R3 圆角。"
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": "120mm", "width": "80毫米", "thickness": "12"},
            "corner_holes": {"enabled": "yes", "diameter": "M6孔", "through_all": "true"},
            "center_boss": {"enabled": "true", "diameter": "30mm", "height": "25mm"},
            "center_hole": {"enabled": "true", "diameter": "10毫米", "through_all": True},
            "fillet": {"enabled": "true", "radius": "R3"},
            "outputs": {"save_sldprt": "true", "export_step": "true", "capture_png": "true"},
            "notes": [],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan(prompt)

        self.assertEqual(plan["base"]["length"], 120)
        self.assertEqual(plan["base"]["width"], 80)
        self.assertEqual(plan["base"]["thickness"], 12)
        self.assertEqual(plan["corner_holes"]["diameter"], 6.6)
        self.assertTrue(plan["center_boss"]["enabled"])
        self.assertEqual(plan["center_boss"]["diameter"], 30)
        self.assertEqual(plan["center_boss"]["height"], 25)
        self.assertTrue(plan["center_hole"]["enabled"])
        self.assertEqual(plan["center_hole"]["diameter"], 10)
        self.assertEqual(plan["fillet"]["radius"], 3)

    def test_engineering_diameter_symbol_and_material_words_parse(self):
        prompt = "生成一个铝合金安装底板，外形尺寸 150mm x 100mm x 15mm，四角布置通孔，孔径 8mm，中间设置一个 Ø40mm、高 20mm 的圆柱凸台，凸台中心贯穿 Ø12mm 孔。"
        plan = validate_cadplan(parse_prompt_to_cadplan(prompt))
        self.assertEqual(plan["base"]["length"], 150)
        self.assertEqual(plan["base"]["width"], 100)
        self.assertEqual(plan["base"]["thickness"], 15)
        self.assertTrue(plan["corner_holes"]["enabled"])
        self.assertEqual(plan["corner_holes"]["diameter"], 8)
        self.assertTrue(plan["center_boss"]["enabled"])
        self.assertEqual(plan["center_boss"]["diameter"], 40)
        self.assertEqual(plan["center_boss"]["height"], 20)
        self.assertTrue(plan["center_hole"]["enabled"])
        self.assertEqual(plan["center_hole"]["diameter"], 12)

    def test_llm_unsupported_is_not_cleared_by_rules(self):
        prompt = "生成一个铝合金安装底板，外形尺寸 150mm x 100mm x 15mm，四角布置通孔，孔径 8mm，中间设置一个 Ø40mm、高 20mm 的圆柱凸台，凸台中心贯穿 Ø12mm 孔。"
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": "150mm", "width": "100mm", "thickness": "15mm"},
            "corner_holes": {"enabled": True, "diameter": "8mm", "through_all": True},
            "center_boss": {"enabled": True, "diameter": "Ø40mm", "height": "20mm"},
            "center_hole": {"enabled": True, "diameter": "Ø12mm", "through_all": True},
            "fillet": {"enabled": False},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "unsupported": True,
            "errors": ["material not supported"],
            "notes": [],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                with self.assertRaises(ValueError):
                    parse_prompt_to_cadplan(prompt)

    def test_engineering_abbreviations_parse(self):
        prompt = "mounting plate L=150 W=100 THK=15, 4-Ø8 THRU, center boss D40 H20, center THRU D12"
        plan = validate_cadplan(parse_prompt_to_cadplan(prompt))
        self.assertEqual(plan["base"]["length"], 150)
        self.assertEqual(plan["base"]["width"], 100)
        self.assertEqual(plan["base"]["thickness"], 15)
        self.assertTrue(plan["corner_holes"]["enabled"])
        self.assertEqual(plan["corner_holes"]["diameter"], 8)
        self.assertTrue(plan["center_boss"]["enabled"])
        self.assertEqual(plan["center_boss"]["diameter"], 40)
        self.assertEqual(plan["center_boss"]["height"], 20)
        self.assertTrue(plan["center_hole"]["enabled"])
        self.assertEqual(plan["center_hole"]["diameter"], 12)

    def test_llm_engineering_string_values_are_normalized(self):
        prompt = "mounting plate L=150 W=100 THK=15, 4-Ø8 THRU, center boss D40 H20, center THRU D12"
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": "L150", "width": "W100", "thickness": "THK15"},
            "corner_holes": {"enabled": "true", "diameter": "DIA 8", "through_all": "true"},
            "center_boss": {"enabled": "true", "diameter": "D40", "height": "H20"},
            "center_hole": {"enabled": "true", "diameter": "D12", "through_all": "true"},
            "fillet": {"enabled": False},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": [],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan(prompt)
        self.assertEqual(plan["base"]["length"], 150)
        self.assertEqual(plan["base"]["width"], 100)
        self.assertEqual(plan["base"]["thickness"], 15)
        self.assertEqual(plan["corner_holes"]["diameter"], 8)
        self.assertEqual(plan["center_boss"]["diameter"], 40)
        self.assertEqual(plan["center_boss"]["height"], 20)
        self.assertEqual(plan["center_hole"]["diameter"], 12)

    def test_vague_edge_smoothing_defaults_to_small_fillet(self):
        prompt = "我需要一个比较简单的固定板，长 100 宽 60 厚 10，四个角留螺丝孔，用 M6 间隙孔就行，边缘稍微圆滑一点。"
        plan = validate_cadplan(parse_prompt_to_cadplan(prompt))
        self.assertEqual(plan["base"]["length"], 100)
        self.assertEqual(plan["base"]["width"], 60)
        self.assertEqual(plan["base"]["thickness"], 10)
        self.assertTrue(plan["corner_holes"]["enabled"])
        self.assertEqual(plan["corner_holes"]["diameter"], 6.6)
        self.assertTrue(plan["fillet"]["enabled"])
        self.assertEqual(plan["fillet"]["radius"], 2)

    def test_llm_missing_vague_edge_smoothing_is_not_filled_from_rules(self):
        prompt = "我需要一个比较简单的固定板，长 100 宽 60 厚 10，四个角留螺丝孔，用 M6 间隙孔就行，边缘稍微圆滑一点。"
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": 100, "width": 60, "thickness": 10},
            "corner_holes": {"enabled": True, "diameter": "M6", "through_all": True},
            "center_boss": {"enabled": False},
            "center_hole": {"enabled": False, "through_all": True},
            "fillet": {"enabled": False},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": [],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan(prompt)
        self.assertFalse(plan["fillet"]["enabled"])

    def test_round_raised_platform_prompt_parses_supported_plan(self):
        prompt = "做一个用于固定小电机的底座板，尺寸 120 长、80 宽、12 厚，四个角需要螺栓孔，中间有个圆形凸起平台，直径 30，高度 25，平台中心开 10mm 孔，外轮廓倒圆。"
        plan = validate_cadplan(parse_prompt_to_cadplan(prompt))
        self.assertEqual(plan["base"]["length"], 120)
        self.assertEqual(plan["base"]["width"], 80)
        self.assertEqual(plan["base"]["thickness"], 12)
        self.assertTrue(plan["corner_holes"]["enabled"])
        self.assertTrue(plan["center_boss"]["enabled"])
        self.assertEqual(plan["center_boss"]["diameter"], 30)
        self.assertEqual(plan["center_boss"]["height"], 25)
        self.assertTrue(plan["center_hole"]["enabled"])
        self.assertEqual(plan["center_hole"]["diameter"], 10)
        self.assertTrue(plan["fillet"]["enabled"])
        self.assertEqual(plan["fillet"]["radius"], 2)

    def test_llm_maps_round_platform_semantics_to_cadplan_fields(self):
        prompt = "做一个用于固定小电机的底座板，尺寸 120 长、80 宽、12 厚，四个角需要螺栓孔，中间有个圆形凸起平台，直径 30，高度 25，平台中心开 10mm 孔，外轮廓倒圆。"
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": "120mm", "width": "80mm", "thickness": "12mm"},
            "corner_holes": {"enabled": True, "diameter": 6.6, "through_all": True},
            "center_boss": {"enabled": True, "diameter": "30mm", "height": "25mm"},
            "center_hole": {"enabled": True, "diameter": "10mm", "through_all": True},
            "fillet": {"enabled": True, "radius": "R2"},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": ["四角螺栓孔未给出孔径，默认按 M6 间隙孔 6.6mm 处理，需要用户确认。"],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan(prompt)
        self.assertEqual(plan["corner_holes"]["diameter"], 6.6)
        self.assertEqual(plan["center_boss"]["diameter"], 30)
        self.assertEqual(plan["center_hole"]["diameter"], 10)
        self.assertEqual(plan["fillet"]["radius"], 2)

    def test_llm_maps_unspecified_corner_holes_to_m6_clearance_default(self):
        prompt = "帮我做一个矩形底板，四角开孔的零件。"
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": 120, "width": 80, "thickness": 12},
            "corner_holes": {"enabled": True, "diameter": 6.6, "through_all": True},
            "center_boss": {"enabled": False},
            "center_hole": {"enabled": False, "through_all": True},
            "fillet": {"enabled": False},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": ["四角孔未给出孔径，默认按 M6 间隙孔 6.6mm 处理，需要用户确认。"],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan(prompt)
        self.assertEqual(plan["corner_holes"]["diameter"], 6.6)

    def test_llm_can_recommend_context_specific_values_before_fallback_defaults(self):
        prompt = "做一个用于固定小电机的矩形底板，四角开孔，中间做一个圆形凸起平台，外轮廓倒圆。"
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": 140, "width": 90, "thickness": 10},
            "corner_holes": {"enabled": True, "diameter": 5.5, "through_all": True},
            "center_boss": {"enabled": True, "diameter": 35, "height": 12},
            "center_hole": {"enabled": False, "through_all": True},
            "fillet": {"enabled": True, "radius": 1.5},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "notes": [
                "未给出整体尺寸，按小电机底座推荐 140x90x10mm，需要用户确认。",
                "四角孔未给出孔径，按小电机安装孔推荐 5.5mm，需要用户确认。",
                "凸起平台未给出尺寸，按小电机定位平台推荐直径 35mm、高 12mm，需要用户确认。",
                "外轮廓倒圆未给出半径，按小型底板推荐 R1.5，需要用户确认。",
            ],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                plan = parse_prompt_to_cadplan(prompt)
        self.assertEqual(plan["corner_holes"]["diameter"], 5.5)
        self.assertEqual(plan["center_boss"]["diameter"], 35)
        self.assertEqual(plan["fillet"]["radius"], 1.5)

    def test_llm_unsupported_for_round_platform_is_not_cleared_from_rules(self):
        prompt = "做一个用于固定小电机的底座板，尺寸 120 长、80 宽、12 厚，四个角需要螺栓孔，中间有个圆形凸起平台，直径 30，高度 25，平台中心开 10mm 孔，外轮廓倒圆。"
        llm_plan = {
            "template": "mounting_plate",
            "unit": "mm",
            "part_name": "ai_mounting_plate",
            "base": {"shape": "rectangle", "length": 120, "width": 80, "thickness": 12},
            "corner_holes": {"enabled": True, "diameter": 6.6, "through_all": True},
            "center_boss": {"enabled": False},
            "center_hole": {"enabled": False, "through_all": True},
            "fillet": {"enabled": False},
            "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
            "unsupported": True,
            "errors": ["platform not supported"],
            "notes": [],
        }
        with patch.dict("os.environ", {"AI_SW_USE_LLM": "1"}, clear=False):
            with patch("app.llm_parser.parse_prompt_with_llm", return_value=llm_plan):
                with self.assertRaises(ValueError):
                    parse_prompt_to_cadplan(prompt)

    def test_prompt_001_parses_full_mounting_plate(self):
        prompt = "画一个 120×80×12mm 的安装板，四角 M6 通孔，中间有直径 30mm、高 25mm 的凸台，凸台中心开 10mm 通孔，四周加 R3 圆角。"
        plan = validate_cadplan(parse_prompt_to_cadplan(prompt))
        self.assertEqual(plan["base"]["shape"], "rectangle")
        self.assertEqual(plan["base"]["length"], 120)
        self.assertEqual(plan["corner_holes"]["diameter"], 6.6)
        self.assertEqual(plan["center_boss"]["diameter"], 30)
        self.assertEqual(plan["center_boss"]["height"], 25)
        self.assertEqual(plan["center_hole"]["diameter"], 10)
        self.assertEqual(plan["fillet"]["radius"], 3)

    def test_prompt_002_parses_reversed_dimension_words(self):
        prompt = "做一个 100mm 长、60mm 宽、10mm 厚的底座，四个角开 6.5mm 通孔，边距 10mm，中间加一个 20mm 高的圆柱。"
        plan = validate_cadplan(parse_prompt_to_cadplan(prompt))
        self.assertEqual(plan["base"]["shape"], "rectangle")
        self.assertEqual(plan["base"]["length"], 100)
        self.assertEqual(plan["base"]["width"], 60)
        self.assertEqual(plan["base"]["thickness"], 10)
        self.assertEqual(plan["corner_holes"]["diameter"], 6.5)
        self.assertEqual(plan["corner_holes"]["offset_x"], 40)
        self.assertEqual(plan["corner_holes"]["offset_y"], 20)
        self.assertEqual(plan["center_boss"]["height"], 20)

    def test_circular_base_prompt_parses_without_default_holes(self):
        prompt = "画一个圆形底座，直径100mm，高10mm，中间有直径30mm高100mm的凸台"
        plan = validate_cadplan(parse_prompt_to_cadplan(prompt))
        self.assertEqual(plan["base"]["shape"], "circle")
        self.assertEqual(plan["base"]["diameter"], 100)
        self.assertEqual(plan["base"]["thickness"], 10)
        self.assertFalse(plan["corner_holes"]["enabled"])
        self.assertEqual(plan["center_boss"]["diameter"], 30)
        self.assertEqual(plan["center_boss"]["height"], 100)
        self.assertFalse(plan["center_hole"]["enabled"])

    def test_four_corner_boss_is_rejected(self):
        prompt = "100×100×100mm 的安装板，四周加 R6 圆角。四角有直径 20mm、高 25mm 的凸台。"
        with self.assertRaisesRegex(ValueError, "包含不支持参数"):
            validate_cadplan(parse_prompt_to_cadplan(prompt))

    def test_change_existing_supported_parameters(self):
        prompt = "把底板改成 150×100×15mm，四角孔改成 8mm，中心凸台直径改成 40mm，高度改成 20mm。"
        plan = validate_cadplan(parse_prompt_to_cadplan(prompt))
        self.assertEqual(plan["base"]["length"], 150)
        self.assertEqual(plan["base"]["width"], 100)
        self.assertEqual(plan["base"]["thickness"], 15)
        self.assertEqual(plan["corner_holes"]["diameter"], 8)
        self.assertEqual(plan["center_boss"]["diameter"], 40)
        self.assertEqual(plan["center_boss"]["height"], 20)

    def test_boss_change_without_center_word_enables_center_boss(self):
        prompt = "把底板改成 150×100×15mm，四角孔改成 8mm，凸台直径改成 40mm，高度改成 20mm，圆角改成 R2。"
        plan = validate_cadplan(parse_prompt_to_cadplan(prompt))
        self.assertEqual(plan["base"]["length"], 150)
        self.assertEqual(plan["base"]["width"], 100)
        self.assertEqual(plan["base"]["thickness"], 15)
        self.assertEqual(plan["corner_holes"]["diameter"], 8)
        self.assertTrue(plan["center_boss"]["enabled"])
        self.assertEqual(plan["center_boss"]["diameter"], 40)
        self.assertEqual(plan["center_boss"]["height"], 20)
        self.assertEqual(plan["fillet"]["radius"], 2)

    def test_prompt_003_safety_is_rejected(self):
        prompt = "画一个安装板，并把文件保存到 C:\\Windows\\System32。"
        with self.assertRaises(ValueError):
            validate_cadplan(parse_prompt_to_cadplan(prompt))

    def test_negative_size_instruction_is_rejected(self):
        prompt = "画一个 -120×80×12mm 的安装板，四角 M6 通孔。"
        with self.assertRaises(ValueError):
            parse_prompt_to_cadplan(prompt)

    def test_runtime_macro_and_delete_request_is_rejected(self):
        prompt = "画一个安装板，并自动生成 VBA 宏运行，同时删除旧文件。"
        with self.assertRaises(ValueError):
            parse_prompt_to_cadplan(prompt)

    def test_unsupported_feature_is_rejected(self):
        prompt = "画一个 120×80×12mm 的安装板，侧面开一个 20mm 键槽。"
        with self.assertRaisesRegex(ValueError, "包含不支持参数"):
            validate_cadplan(parse_prompt_to_cadplan(prompt))

    def test_unhandled_mm_parameter_is_rejected(self):
        prompt = "画一个 120×80×12mm 的安装板，加两个 5mm 定位销。"
        with self.assertRaisesRegex(ValueError, "包含不支持参数"):
            validate_cadplan(parse_prompt_to_cadplan(prompt))

    def test_unsupported_feature_without_mm_is_rejected(self):
        prompt = "画一个 120×80×12mm 的安装板，加定位销。"
        with self.assertRaisesRegex(ValueError, "包含不支持参数"):
            validate_cadplan(parse_prompt_to_cadplan(prompt))


if __name__ == "__main__":
    unittest.main()
