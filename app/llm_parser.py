import os
import re
from copy import deepcopy

from app.llm_client import LlmCadplanError, parse_prompt_with_llm
from app.validator import validate_cadplan


FORBIDDEN_PATH_HINTS = (
    "C:\\Windows",
    "System32",
    "Documents",
    "Downloads",
    "D:\\",
    "E:\\",
)

FORBIDDEN_RUNTIME_WORDS = (
    "vba",
    "python",
    "shell",
    "powershell",
    "macro",
    "script",
    "宏",
    "脚本",
    "运行",
    "执行",
    "自动运行",
    "自动生成",
    "删除",
    "删掉",
    "清空",
)

ZH = {
    "middle": "\u4e2d\u95f4",
    "center": "\u4e2d\u5fc3",
    "boss": "\u51f8\u53f0",
    "raised": "\u51f8\u8d77",
    "cylinder": "\u5706\u67f1",
    "platform": "\u5e73\u53f0",
    "round_platform": "\u5706\u5f62\u5e73\u53f0",
    "circle_base": "\u5706\u5f62\u5e95\u5ea7",
    "round_base": "\u5706\u5e95\u5ea7",
    "disk": "\u5706\u76d8",
    "circle_plate": "\u5706\u5f62\u5b89\u88c5\u677f",
    "diameter": "\u76f4\u5f84",
    "hole_diameter": "\u5b54\u5f84",
    "height": "\u9ad8",
    "height_full": "\u9ad8\u5ea6",
    "length": "\u957f",
    "length_full": "\u957f\u5ea6",
    "width": "\u5bbd",
    "width_full": "\u5bbd\u5ea6",
    "thick": "\u539a",
    "thickness": "\u539a\u5ea6",
    "four_corners": "\u56db\u89d2",
    "four_corner_words": "\u56db\u4e2a\u89d2",
    "through_hole": "\u901a\u5b54",
    "open": "\u5f00",
    "change_to": "\u6539\u6210",
    "hole_change_to": "\u5b54\u6539\u6210",
    "margin": "\u8fb9\u8ddd",
    "hole_margin": "\u5b54\u8fb9\u8ddd",
    "fillet": "\u5706\u89d2",
    "smooth": "\u5706\u6ed1",
    "outer_contour": "\u5916\u8f6e\u5ed3",
    "bolt": "\u87ba\u6813",
    "screw": "\u87ba\u4e1d",
    "unsupported": "\u5305\u542b\u4e0d\u652f\u6301\u53c2\u6570",
}

SUPPORTED_FEATURE_WORDS = (
    ZH["middle"],
    ZH["center"],
    ZH["boss"],
    ZH["raised"],
    ZH["cylinder"],
    ZH["platform"],
    ZH["round_platform"],
    ZH["circle_base"],
    ZH["round_base"],
    ZH["disk"],
    ZH["circle_plate"],
    ZH["diameter"],
    ZH["hole_diameter"],
    ZH["height"],
    ZH["height_full"],
    ZH["length"],
    ZH["length_full"],
    ZH["width"],
    ZH["width_full"],
    ZH["thick"],
    ZH["thickness"],
    ZH["four_corners"],
    ZH["four_corner_words"],
    ZH["through_hole"],
    ZH["open"],
    ZH["change_to"],
    ZH["hole_change_to"],
    ZH["margin"],
    ZH["hole_margin"],
    ZH["fillet"],
    ZH["smooth"],
    ZH["outer_contour"],
    ZH["bolt"],
    ZH["screw"],
    "\u5b89\u88c5\u677f",
    "\u5e95\u5ea7",
    "\u5e95\u677f",
    "\u5916\u5f62\u5c3a\u5bf8",
    "\u94dd\u5408\u91d1",
    "\u6750\u6599",
    "\u5e03\u7f6e",
    "\u8bbe\u7f6e",
    "\u8d2f\u7a7f",
    "\u5706\u6ed1\u4e00\u70b9",
    "\u7a0d\u5fae\u5706\u6ed1",
    "\u8fb9\u7f18\u5706\u6ed1",
    "\u53bb\u9510\u8fb9",
    "\u5012\u5706",
    "\u5012\u5706\u89d2",
    "THRU",
    "through",
    "DIA",
    "THK",
    "L=",
    "W=",
    "T=",
    "\u56db\u5468",
    "\u753b",
    "\u505a",
    "\u4e00\u4e2a",
    "\u52a0",
    "\u6709",
    "\u628a",
)

UNSUPPORTED_FEATURE_WORDS = (
    "\u69fd",
    "\u952e\u69fd",
    "\u5b9a\u4f4d\u9500",
    "\u9500",
    "\u6c89\u5934",
    "\u6c89\u5b54",
    "\u87ba\u7eb9",
    "\u5012\u89d2",
    "\u534a\u5f84",
    "\u692d\u5706",
    "\u4fa7\u9762",
    "\u5b54\u8ddd",
    "\u659c\u9762",
    "\u9635\u5217",
    "\u88c5\u914d",
    "\u5de5\u7a0b\u56fe",
    "BOM",
    "GD&T",
    "\u94a3\u91d1",
    "\u66f2\u9762",
    "\u65b9\u5f62\u51f8\u53f0",
    "\u65b9\u5f62\u5e95\u5ea7",
    "\u690e",
    "\u7403",
)

BLANK_PART_WORDS = (
    "\u7a7a\u767d\u96f6\u4ef6",
    "\u7a7a\u96f6\u4ef6",
    "\u65b0\u5efa\u7a7a\u767d",
    "blank part",
    "empty part",
)

GEOMETRY_INTENT_WORDS = (
    "\u5b89\u88c5\u677f",
    "\u56fa\u5b9a\u677f",
    "\u5e95\u677f",
    "\u5e95\u5ea7",
    "\u957f\u65b9\u4f53",
    "\u77e9\u5f62",
    "\u5b9e\u4f53",
    "\u5c3a\u5bf8",
    "\u5b54",
    "\u51f8\u53f0",
    "\u5706\u89d2",
    "cuboid",
    "rectangular solid",
    "block",
    "mounting plate",
    "base plate",
    "hole",
    "boss",
    "fillet",
)


def _default_plan() -> dict:
    return {
        "template": "mounting_plate",
        "unit": "mm",
        "part_name": "ai_mounting_plate",
        "base": {
            "shape": "rectangle",
            "length": 120.0,
            "width": 80.0,
            "thickness": 12.0,
        },
        "corner_holes": {
            "enabled": False,
            "through_all": True,
        },
        "center_boss": {
            "enabled": False,
        },
        "center_hole": {
            "enabled": False,
            "through_all": True,
        },
        "fillet": {
            "enabled": False,
        },
        "outputs": {
            "save_sldprt": True,
            "export_step": True,
            "capture_png": True,
        },
        "notes": [],
    }


def _default_blank_part_plan() -> dict:
    return {
        "template": "blank_part",
        "unit": "mm",
        "part_name": "blank_part",
        "outputs": {
            "save_sldprt": True,
            "export_step": False,
            "capture_png": False,
        },
        "notes": [],
    }


def _number(text: str) -> float:
    value = float(text)
    return int(value) if value.is_integer() else value


def _first_match(pattern: str, text: str, flags: int = re.IGNORECASE):
    return re.search(pattern, text, flags)


def _any_word(words: list[str]) -> str:
    return "(?:" + "|".join(re.escape(word) for word in words) + ")"


def _diameter_marker() -> str:
    return r"(?:%s|%s|[ØøΦφ⌀]|DIA\.?|DIAMETER|D(?=\s*\d))" % (
        re.escape(ZH["diameter"]),
        re.escape(ZH["hole_diameter"]),
    )


def _unit_pattern() -> str:
    return r"(?:mm|\u6beb\u7c73)?"


def _length_label() -> str:
    return r"(?:L|LEN(?:GTH)?|%s|%s)" % (re.escape(ZH["length"]), re.escape(ZH["length_full"]))


def _width_label() -> str:
    return r"(?:W|WIDTH|%s|%s)" % (re.escape(ZH["width"]), re.escape(ZH["width_full"]))


def _thickness_label() -> str:
    return r"(?:T|THK\.?|THICK(?:NESS)?|%s|%s)" % (re.escape(ZH["thick"]), re.escape(ZH["thickness"]))


def _height_label() -> str:
    return r"(?:H|HEIGHT|%s|%s)" % (re.escape(ZH["height"]), re.escape(ZH["height_full"]))


def _dimension_value_from_label(prompt: str, label_pattern: str):
    labeled_first = _first_match(rf"(?:{label_pattern})\s*[:=]?\s*(\d+(?:\.\d+)?)\s*{_unit_pattern()}", prompt)
    if labeled_first:
        return _number(labeled_first.group(1))
    labeled_last = _first_match(rf"(\d+(?:\.\d+)?)\s*{_unit_pattern()}\s*(?:{label_pattern})", prompt)
    if labeled_last:
        return _number(labeled_last.group(1))
    return None


def _mark_unsupported(plan: dict) -> None:
    plan["unsupported"] = True
    plan.setdefault("errors", []).append(ZH["unsupported"])


def _contains_negative_dimension(prompt: str) -> bool:
    return bool(
        _first_match(
            r"(?<![\w.])-+\s*\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?(?=\s*(?:\u00d7|x|X|\*|mm|\u6beb\u7c73|\b|$))",
            prompt,
        )
    )


def _contains_forbidden_runtime_intent(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(word.lower() in lowered for word in FORBIDDEN_RUNTIME_WORDS)


def _boss_words() -> list[str]:
    return [ZH["boss"], ZH["raised"], ZH["cylinder"], ZH["platform"], ZH["round_platform"], "boss", "cylinder"]


def _contains_unsupported_feature(prompt: str) -> bool:
    corner_words = _any_word([ZH["four_corners"], ZH["four_corner_words"]])
    boss_words = _any_word(_boss_words())
    before_center = re.split(_any_word([ZH["middle"], ZH["center"]]), prompt, maxsplit=1)[0]
    if _first_match(rf"{corner_words}[^，。；;,.]{{0,24}}{boss_words}", before_center):
        return True
    return any(word in prompt for word in UNSUPPORTED_FEATURE_WORDS)


def _has_unhandled_mm_parameter(prompt: str) -> bool:
    cleaned = prompt
    patterns = [
        r"\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?\s*(?:\u00d7|x|X|\*)\s*\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?\s*(?:\u00d7|x|X|\*)\s*\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?",
        _diameter_marker() + r"\s*(?:" + re.escape(ZH["change_to"]) + r")?\s*\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?",
        _any_word([ZH["height"], ZH["height_full"], ZH["thick"], ZH["thickness"]]) + r"\s*(?:" + re.escape(ZH["change_to"]) + r")?\s*\d+(?:\.\d+)?\s*mm?",
        _length_label() + r"\s*[:=]?\s*\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?",
        r"\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?\s*" + _length_label(),
        _width_label() + r"\s*[:=]?\s*\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?",
        r"\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?\s*" + _width_label(),
        _thickness_label() + r"\s*[:=]?\s*\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?",
        r"\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?\s*" + _thickness_label(),
        _height_label() + r"\s*[:=]?\s*\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?",
        r"\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?\s*" + _height_label(),
        r"\d+(?:\.\d+)?\s*mm?\s*" + _any_word([ZH["height"], ZH["height_full"], ZH["thick"], ZH["thickness"]]),
        _any_word([ZH["length"], ZH["length_full"]]) + r"\s*(?:" + re.escape(ZH["change_to"]) + r")?\s*\d+(?:\.\d+)?\s*mm?",
        r"\d+(?:\.\d+)?\s*mm?\s*" + _any_word([ZH["length"], ZH["length_full"]]),
        _any_word([ZH["width"], ZH["width_full"]]) + r"\s*(?:" + re.escape(ZH["change_to"]) + r")?\s*\d+(?:\.\d+)?\s*mm?",
        r"\d+(?:\.\d+)?\s*mm?\s*" + _any_word([ZH["width"], ZH["width_full"]]),
        _any_word([ZH["margin"], ZH["hole_margin"]]) + r"\s*\d+(?:\.\d+)?\s*mm?",
        _any_word([ZH["four_corners"], ZH["four_corner_words"]]) + r".{0,24}(?:" + _diameter_marker() + r")?\s*(?:" + re.escape(ZH["change_to"]) + r")?\s*\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?",
        r"\u5b54\s*" + re.escape(ZH["change_to"]) + r"\s*\d+(?:\.\d+)?\s*mm?",
        r"\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?\s*(?:" + re.escape(ZH["through_hole"]) + r"|\u5b54)",
        r"(?:4\s*[-xX\u00d7]\s*)?(?:" + _diameter_marker() + r"|M\s*6)\s*\d*(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?\s*(?:THRU|THROUGH)?",
        r"M\s*6",
        r"R\s*\d+(?:\.\d+)?",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    return bool(re.search(r"\d+(?:\.\d+)?\s*mm?", cleaned, re.IGNORECASE))


def _text_before_feature(prompt: str) -> str:
    marker = _any_word([ZH["middle"], ZH["center"], ZH["boss"], ZH["raised"], ZH["platform"], ZH["round_platform"]])
    split = re.split(marker, prompt, maxsplit=1)
    return split[0] if split else prompt


def _text_from_keywords(prompt: str, keywords: list[str]) -> str:
    indexes = [prompt.find(keyword) for keyword in keywords if prompt.find(keyword) >= 0]
    return prompt[min(indexes):] if indexes else ""


def _center_feature_text(prompt: str) -> str:
    center_indexes = [prompt.find(ZH["middle"]), prompt.find(ZH["center"])]
    center_indexes = [index for index in center_indexes if index >= 0]
    if center_indexes:
        return prompt[min(center_indexes):]
    return _text_from_keywords(prompt, _boss_words())


def _parse_base(prompt: str, plan: dict) -> None:
    size = _first_match(
        r"(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?\s*(?:\u00d7|x|X|\*)\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?\s*(?:\u00d7|x|X|\*)\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?",
        prompt,
    )
    if size:
        plan["base"]["shape"] = "rectangle"
        plan["base"]["length"] = _number(size.group(1))
        plan["base"]["width"] = _number(size.group(2))
        plan["base"]["thickness"] = _number(size.group(3))
        return

    length_by_label = _dimension_value_from_label(prompt, _length_label())
    width_by_label = _dimension_value_from_label(prompt, _width_label())
    thickness_by_label = _dimension_value_from_label(prompt, _thickness_label())
    if length_by_label is not None:
        plan["base"]["length"] = length_by_label
    if width_by_label is not None:
        plan["base"]["width"] = width_by_label
    if thickness_by_label is not None:
        plan["base"]["thickness"] = thickness_by_label
    if length_by_label is not None and width_by_label is not None and thickness_by_label is not None:
        plan["base"]["shape"] = "rectangle"
        return

    base_text = _text_before_feature(prompt)
    circle_words = [ZH["circle_base"], ZH["round_base"], ZH["disk"], ZH["circle_plate"]]
    if any(word in base_text for word in circle_words):
        plan["base"]["shape"] = "circle"
        diameter = _first_match(_diameter_marker() + r"\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?", base_text)
        thickness_words = _any_word([ZH["height"], ZH["height_full"], ZH["thick"], ZH["thickness"]])
        thickness = _first_match(
            rf"(?:(?:{thickness_words})\s*(\d+(?:\.\d+)?)\s*mm?|(\d+(?:\.\d+)?)\s*mm?\s*(?:{thickness_words}))",
            base_text,
        )
        if diameter:
            value = _number(diameter.group(1))
            plan["base"]["diameter"] = value
            plan["base"]["length"] = value
            plan["base"]["width"] = value
        if thickness:
            plan["base"]["thickness"] = _number(thickness.group(1) or thickness.group(2))
        return

    length_words = _any_word([ZH["length"], ZH["length_full"]])
    width_words = _any_word([ZH["width"], ZH["width_full"]])
    thickness_words = _any_word([ZH["thick"], ZH["thickness"]])
    length = _first_match(
        rf"(?:(?:{length_words})\s*(\d+(?:\.\d+)?)\s*mm?|(\d+(?:\.\d+)?)\s*mm?\s*(?:{length_words}))",
        prompt,
    )
    width = _first_match(
        rf"(?:(?:{width_words})\s*(\d+(?:\.\d+)?)\s*mm?|(\d+(?:\.\d+)?)\s*mm?\s*(?:{width_words}))",
        prompt,
    )
    thickness = _first_match(
        rf"(?:(?:{thickness_words})\s*(\d+(?:\.\d+)?)\s*mm?|(\d+(?:\.\d+)?)\s*mm?\s*(?:{thickness_words}))",
        base_text,
    )
    if length:
        plan["base"]["length"] = _number(length.group(1) or length.group(2))
    if width:
        plan["base"]["width"] = _number(width.group(1) or width.group(2))
    if thickness:
        plan["base"]["thickness"] = _number(thickness.group(1) or thickness.group(2))


def _parse_corner_holes(prompt: str, plan: dict) -> None:
    engineering_corner_holes = _first_match(
        rf"(?:4\s*[-xX\u00d7]\s*(?:{_diameter_marker()}|M\s*6)|four\s+corner\s+holes?|corner\s+holes?)",
        prompt,
    )
    if ZH["four_corners"] not in prompt and ZH["four_corner_words"] not in prompt and not engineering_corner_holes:
        return
    if ZH["through_hole"] not in prompt and "\u5b54" not in prompt and not _first_match(r"THRU|THROUGH|HOLE", prompt):
        return

    plan["corner_holes"]["enabled"] = True
    if _first_match(r"M\s*6\s*(?:" + re.escape(ZH["through_hole"]) + r"|\u5b54|THRU|THROUGH|HOLE)?", prompt):
        plan["corner_holes"]["diameter"] = 6.6
        plan["notes"].append("M6 通孔默认按 6.6mm 间隙孔处理，需要用户确认。")

    corner_words = _any_word([ZH["four_corners"], ZH["four_corner_words"]])
    action_words = _any_word([ZH["open"], ZH["change_to"], ZH["hole_change_to"]])
    corner_text = _text_before_feature(prompt)
    corner_diameter = _first_match(
        rf"{corner_words}[^，。；;,.]{{0,32}}(?:(?:{action_words})|(?:{_diameter_marker()}))\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?",
        prompt,
    )
    if not corner_diameter:
        corner_diameter = _first_match(
            rf"(?:{_diameter_marker()})\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?",
            corner_text,
        )
    if not corner_diameter:
        corner_diameter = _first_match(
            rf"4\s*[-xX\u00d7]\s*(?:{_diameter_marker()})\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?",
            prompt,
        )
    if corner_diameter:
        plan["corner_holes"]["diameter"] = _number(corner_diameter.group(1))
    elif "diameter" not in plan["corner_holes"] and (ZH["bolt"] in prompt or ZH["screw"] in prompt):
        plan["corner_holes"]["diameter"] = 6.6
        plan["notes"].append("四角螺栓孔未给出孔径，默认按 M6 间隙孔 6.6mm 处理，需要用户确认。")

    margin_words = _any_word([ZH["margin"], ZH["hole_margin"]])
    margin = _first_match(rf"(?:{margin_words})\s*(\d+(?:\.\d+)?)\s*mm?", prompt)
    if margin:
        value = _number(margin.group(1))
        plan["corner_holes"]["offset_x"] = plan["base"]["length"] / 2 - value
        plan["corner_holes"]["offset_y"] = plan["base"]["width"] / 2 - value


def _parse_center_boss(prompt: str, plan: dict) -> None:
    boss_intent_words = _boss_words()
    if not any(word in prompt for word in boss_intent_words) and not any(word in prompt.lower() for word in ("boss", "cylinder")):
        return

    boss_text = _center_feature_text(prompt)
    if not boss_text:
        return

    diameter_word = _diameter_marker()
    height_words = _height_label()
    pair = _first_match(
        rf"{diameter_word}\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?\s*[，,、\s]*(?:{height_words})\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?",
        boss_text,
    )
    plan["center_boss"]["enabled"] = True
    if pair:
        plan["center_boss"]["diameter"] = _number(pair.group(1))
        plan["center_boss"]["height"] = _number(pair.group(2))
        return

    diameter = _first_match(rf"{diameter_word}(?:{re.escape(ZH['change_to'])})?\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?", boss_text)
    height = _first_match(
        rf"(?:(?:{height_words})(?:{re.escape(ZH['change_to'])})?\s*(\d+(?:\.\d+)?)\s*mm?|(\d+(?:\.\d+)?)\s*mm?\s*(?:{height_words}))",
        boss_text,
    )
    if diameter:
        plan["center_boss"]["diameter"] = _number(diameter.group(1))
    if height:
        plan["center_boss"]["height"] = _number(height.group(1) or height.group(2))
    if "diameter" not in plan["center_boss"]:
        plan["center_boss"]["diameter"] = 30.0
        plan["notes"].append("中心凸台未给出直径，默认按 30mm 处理，需要用户确认。")
    if "height" not in plan["center_boss"]:
        plan["center_boss"]["height"] = 25.0
        plan["notes"].append("中心凸台未给出高度，默认按 25mm 处理，需要用户确认。")


def _parse_center_hole(prompt: str, plan: dict) -> None:
    prefix = _any_word([
        ZH["boss"] + ZH["center"],
        ZH["boss"] + ZH["middle"],
        ZH["platform"] + ZH["center"],
        ZH["platform"] + ZH["middle"],
        ZH["center"],
        ZH["middle"],
        "center",
        "centre",
    ])
    hole_words = _any_word([ZH["through_hole"], "\u5b54", "THRU", "THROUGH", "HOLE"])
    center_hole = _first_match(rf"{prefix}.*?(?:\u8d2f\u7a7f|\u5f00)?\s*(?:{_diameter_marker()})?\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?\s*(?:\u7684)?\s*(?:{hole_words})", prompt)
    if not center_hole:
        center_hole = _first_match(rf"{prefix}.*?(?:THRU|THROUGH|\u8d2f\u7a7f|\u5f00).*?(?:{_diameter_marker()})\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?", prompt)
    if center_hole:
        plan["center_hole"]["enabled"] = True
        plan["center_hole"]["diameter"] = _number(center_hole.group(1))


def _parse_fillet(prompt: str, plan: dict) -> None:
    fillet = _first_match(r"R\s*(\d+(?:\.\d+)?)\s*(?:" + re.escape(ZH["fillet"]) + r")?", prompt)
    if fillet:
        plan["fillet"]["enabled"] = True
        plan["fillet"]["radius"] = _number(fillet.group(1))
        return

    smooth_words = (
        ZH["smooth"],
        "\u5706\u6ed1\u4e00\u70b9",
        "\u7a0d\u5fae\u5706\u6ed1",
        "\u8fb9\u7f18\u5706\u6ed1",
        "\u8fb9\u7f18\u7a0d\u5fae\u5706\u6ed1",
        "\u5916\u8fb9\u7f18\u5706\u6ed1",
        "\u5916\u8f6e\u5ed3\u5012\u5706",
        "\u5916\u8f6e\u5ed3\u5706\u6ed1",
        "\u53bb\u9510\u8fb9",
        "\u5012\u5706",
        "\u5012\u5706\u89d2",
    )
    if any(word in prompt for word in smooth_words):
        thickness = plan.get("base", {}).get("thickness", 12.0)
        radius = min(2.0, float(thickness) / 4)
        plan["fillet"]["enabled"] = True
        plan["fillet"]["radius"] = _number(str(radius))
        plan["notes"].append("未给出明确圆角半径，按小圆角 R%s 处理，需要用户确认。" % plan["fillet"]["radius"])


def _contains_blank_part_intent(prompt: str) -> bool:
    lowered = prompt.lower()
    has_geometry = any(word in lowered for word in GEOMETRY_INTENT_WORDS)
    has_dimension = bool(
        _first_match(
            r"\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?\s*(?:\u00d7|x|X|\*)\s*\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?(?:\s*(?:\u00d7|x|X|\*)\s*\d+(?:\.\d+)?\s*(?:mm|\u6beb\u7c73)?)?",
            prompt,
        )
    )
    has_geometry = has_geometry or has_dimension
    if any(word in lowered for word in BLANK_PART_WORDS):
        return not has_geometry
    return False


def _blank_part_name_from_prompt(prompt: str) -> str:
    lowered = prompt.lower()
    save_as = _first_match(r"(?:save\s+as)\s+([A-Za-z0-9_-]+)", prompt)
    if save_as:
        return save_as.group(1)
    if "\u6d4b\u8bd5\u96f6\u4ef6" in lowered:
        return "test_part"
    return "blank_part"


def _parse_blank_part(prompt: str) -> dict:
    plan = _default_blank_part_plan()
    plan["part_name"] = _blank_part_name_from_prompt(prompt)
    return plan


def llm_enabled() -> bool:
    return os.environ.get("AI_SW_LLM_PROVIDER", "").strip().lower() == "openai" or os.environ.get("AI_SW_USE_LLM") == "1"


def current_parse_mode() -> str:
    provider = os.environ.get("AI_SW_LLM_PROVIDER", "").strip().lower()
    if provider in {"rule_based", "openai", "local"}:
        return provider
    if provider:
        return f"{provider}->rule_based"
    return "openai" if os.environ.get("AI_SW_USE_LLM") == "1" else "rule_based"


def _coerce_llm_number(value, field_name: str):
    if not isinstance(value, str):
        return value

    text = value.strip()
    if field_name == "diameter" and re.search(r"M\s*6", text, re.IGNORECASE):
        return 6.6

    number = re.fullmatch(
        r"(?:R|[ØøΦφ⌀]|DIA\.?|DIAMETER|D|L|LEN(?:GTH)?|W|WIDTH|T|THK\.?|THICK(?:NESS)?|H|HEIGHT)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?",
        text,
        re.IGNORECASE,
    )
    if not number:
        number = re.fullmatch(
            r"(\d+(?:\.\d+)?)\s*(?:mm|毫米)?\s*(?:L|W|T|H|THK\.?|DIA\.?|D)",
            text,
            re.IGNORECASE,
        )
    if number:
        return _number(number.group(1))

    return value


def _coerce_llm_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "1", "yes", "y", "on", "enabled", "enable", "是", "有", "启用", "开启"):
            return True
        if text in ("false", "0", "no", "n", "off", "disabled", "disable", "否", "无", "不启用", "关闭"):
            return False
    return value


def _add_note(plan: dict, note: str) -> None:
    notes = plan.setdefault("notes", [])
    if isinstance(notes, list) and note not in notes:
        notes.append(note)


def _normalize_llm_cadplan(plan: dict, prompt: str = "") -> dict:
    normalized = deepcopy(plan)
    converted_m6 = False

    numeric_paths = (
        ("base", "diameter"),
        ("base", "length"),
        ("base", "width"),
        ("base", "thickness"),
        ("corner_holes", "diameter"),
        ("corner_holes", "offset_x"),
        ("corner_holes", "offset_y"),
        ("center_boss", "diameter"),
        ("center_boss", "height"),
        ("center_hole", "diameter"),
        ("fillet", "radius"),
    )

    bool_paths = (
        ("corner_holes", "enabled"),
        ("corner_holes", "through_all"),
        ("center_boss", "enabled"),
        ("center_hole", "enabled"),
        ("center_hole", "through_all"),
        ("fillet", "enabled"),
        ("outputs", "save_sldprt"),
        ("outputs", "export_step"),
        ("outputs", "capture_png"),
    )

    for section, field_name in bool_paths:
        section_value = normalized.get(section)
        if isinstance(section_value, dict) and field_name in section_value:
            section_value[field_name] = _coerce_llm_bool(section_value[field_name])

    for section, field_name in numeric_paths:
        section_value = normalized.get(section)
        if not isinstance(section_value, dict) or field_name not in section_value:
            continue
        before = section_value[field_name]
        after = _coerce_llm_number(before, field_name)
        if before != after and isinstance(before, str) and re.search(r"M\s*6", before.strip(), re.IGNORECASE):
            converted_m6 = True
        section_value[field_name] = after

    if converted_m6:
        _add_note(normalized, "M6 通孔默认按 6.6mm 间隙孔处理，需要用户确认。")

    return normalized


def parse_prompt_with_rules(prompt: str) -> dict:
    """Parse Chinese natural language into CADPlan Lite with local rules."""
    plan = deepcopy(_default_plan())
    prompt = prompt.strip()

    if any(hint.lower() in prompt.lower() for hint in FORBIDDEN_PATH_HINTS):
        plan["notes"].append("检测到疑似项目外路径意图，校验阶段将拒绝。")
        plan["unsafe_prompt"] = prompt
        return plan

    if _contains_forbidden_runtime_intent(prompt):
        _mark_unsupported(plan)
        plan.setdefault("errors", []).append("不允许生成、执行宏或脚本，也不允许删除文件。")
        return plan

    if _contains_negative_dimension(prompt):
        _mark_unsupported(plan)
        plan.setdefault("errors", []).append("尺寸不能为负数。")
        return plan

    if _contains_blank_part_intent(prompt):
        return _parse_blank_part(prompt)

    if _contains_unsupported_feature(prompt):
        _mark_unsupported(plan)
        return plan

    _parse_base(prompt, plan)
    _parse_corner_holes(prompt, plan)
    _parse_center_boss(prompt, plan)
    _parse_center_hole(prompt, plan)
    _parse_fillet(prompt, plan)
    if _has_unhandled_mm_parameter(prompt):
        _mark_unsupported(plan)
    return plan


def parse_prompt_to_cadplan(prompt: str) -> dict:
    """Parse Chinese natural language into a validated CADPlan Lite dict."""
    if not llm_enabled():
        return validate_cadplan(parse_prompt_with_rules(prompt))

    try:
        llm_plan = parse_prompt_with_llm(prompt)
    except LlmCadplanError:
        return validate_cadplan(parse_prompt_with_rules(prompt))

    return validate_cadplan(_normalize_llm_cadplan(llm_plan, prompt))
