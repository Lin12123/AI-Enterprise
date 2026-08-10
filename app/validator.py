import re
from copy import deepcopy


FORBIDDEN_FIELD_NAMES = {
    "output_dir",
    "path",
    "file_path",
    "save_path",
    "absolute_path",
    "system_path",
}

FORBIDDEN_CONTENT_WORDS = (
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

FORBIDDEN_PATH_HINTS = (
    "C:\\Windows",
    "System32",
    "Documents",
    "Downloads",
    "D:\\",
    "E:\\",
)

FALLBACK_NUMBERS = {
    ("base", "length"): 120,
    ("base", "width"): 80,
    ("base", "thickness"): 12,
    ("corner_holes", "diameter"): 6.6,
    ("center_boss", "diameter"): 30,
    ("center_boss", "height"): 25,
    ("center_hole", "diameter"): 10,
    ("fillet", "radius"): 2,
}

FALLBACK_NOTES = {
    ("base", "length"): "底板长度未给出明确推荐值，按保守默认 120mm 处理，需要用户确认。",
    ("base", "width"): "底板宽度未给出明确推荐值，按保守默认 80mm 处理，需要用户确认。",
    ("base", "thickness"): "底板厚度未给出明确推荐值，按保守默认 12mm 处理，需要用户确认。",
    ("corner_holes", "diameter"): "四角孔孔径未给出明确推荐值，按 M6 间隙孔 6.6mm 处理，需要用户确认。",
    ("center_boss", "diameter"): "中心凸台直径未给出明确推荐值，按保守默认 30mm 处理，需要用户确认。",
    ("center_boss", "height"): "中心凸台高度未给出明确推荐值，按保守默认 25mm 处理，需要用户确认。",
    ("center_hole", "diameter"): "中心孔孔径未给出明确推荐值，按保守默认 10mm 处理，需要用户确认。",
    ("fillet", "radius"): "圆角半径未给出明确推荐值，按小圆角 R2 处理，需要用户确认。",
}


def _walk_fields(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk_fields(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_fields(child)


def _contains_forbidden_path_intent(value) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return any(hint.lower() in lowered for hint in FORBIDDEN_PATH_HINTS)
    if isinstance(value, dict):
        return any(_contains_forbidden_path_intent(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_path_intent(child) for child in value)
    return False


def _contains_forbidden_runtime_intent(value) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return any(word in lowered for word in FORBIDDEN_CONTENT_WORDS)
    if isinstance(value, dict):
        return any(_contains_forbidden_runtime_intent(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_runtime_intent(child) for child in value)
    return False


def _require_number(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} 必须是数字")
    return float(value)


def _is_number(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _add_note(plan: dict, note: str) -> None:
    notes = plan.setdefault("notes", [])
    if isinstance(notes, list) and note not in notes:
        notes.append(note)


def _fill_fallback_number(plan: dict, section: str, field_name: str) -> None:
    section_value = plan.setdefault(section, {})
    if not isinstance(section_value, dict):
        return
    if _is_number(section_value.get(field_name)):
        return
    path = (section, field_name)
    section_value[field_name] = FALLBACK_NUMBERS[path]
    _add_note(plan, FALLBACK_NOTES[path])


def _default_outputs(plan: dict) -> None:
    outputs = plan.setdefault("outputs", {})
    outputs.setdefault("save_sldprt", True)
    outputs.setdefault("export_step", True)
    outputs.setdefault("capture_png", True)


def _default_blank_part_outputs(plan: dict) -> None:
    outputs = plan.setdefault("outputs", {})
    outputs.setdefault("save_sldprt", True)
    outputs.setdefault("export_step", False)
    outputs.setdefault("capture_png", False)


def validate_cadplan(cadplan: dict) -> dict:
    if not isinstance(cadplan, dict):
        raise ValueError("CADPlan 必须是对象")

    if cadplan.get("unsupported") is True:
        raise ValueError("包含不支持参数")

    for key, _ in _walk_fields(cadplan):
        if key in FORBIDDEN_FIELD_NAMES:
            raise ValueError(f"不允许字段：{key}")
        if str(key).lower() in FORBIDDEN_CONTENT_WORDS:
            raise ValueError(f"不允许字段：{key}")

    if _contains_forbidden_path_intent(cadplan):
        raise ValueError("检测到项目外路径意图，已拒绝")
    if _contains_forbidden_runtime_intent(cadplan):
        raise ValueError("检测到运行时代码或宏意图，已拒绝")

    plan = deepcopy(cadplan)
    plan.setdefault("template", "mounting_plate")
    plan.setdefault("unit", "mm")

    if plan["template"] not in {"mounting_plate", "blank_part"}:
        raise ValueError("template 必须是 mounting_plate")
    if plan["unit"] != "mm":
        raise ValueError("unit 必须是 mm")
    if plan["template"] == "blank_part":
        plan.setdefault("part_name", "blank_part")
    else:
        plan.setdefault("part_name", "ai_mounting_plate")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", str(plan["part_name"])):
        raise ValueError("part_name 只允许字母、数字、下划线、中划线")

    if plan["template"] == "blank_part":
        _default_blank_part_outputs(plan)
        plan.setdefault("notes", [])
        return plan

    base = plan.setdefault("base", {})
    shape = base.setdefault("shape", "rectangle")
    _fill_fallback_number(plan, "base", "length")
    _fill_fallback_number(plan, "base", "width")
    _fill_fallback_number(plan, "base", "thickness")
    thickness = _require_number("base.thickness", base.get("thickness"))
    if not (0 < thickness <= 100):
        raise ValueError("base.thickness 必须 > 0 且 <= 100")

    if shape == "circle":
        diameter = _require_number("base.diameter", base.get("diameter"))
        if not (0 < diameter <= 1000):
            raise ValueError("base.diameter 必须 > 0 且 <= 1000")
        base["diameter"] = diameter
        base["length"] = diameter
        base["width"] = diameter
        base_limit = diameter
    elif shape == "rectangle":
        length = _require_number("base.length", base.get("length"))
        width = _require_number("base.width", base.get("width"))
        if not (0 < length <= 1000):
            raise ValueError("base.length 必须 > 0 且 <= 1000")
        if not (0 < width <= 1000):
            raise ValueError("base.width 必须 > 0 且 <= 1000")
        base["length"] = length
        base["width"] = width
        base_limit = min(length, width)
    else:
        raise ValueError("base.shape 必须是 rectangle 或 circle")
    base["thickness"] = thickness

    corner = plan.setdefault("corner_holes", {})
    corner.setdefault("enabled", False)
    corner.setdefault("through_all", True)
    if corner["enabled"]:
        if shape != "rectangle":
            raise ValueError("圆形底座不支持四角孔")
        _fill_fallback_number(plan, "corner_holes", "diameter")
        diameter = _require_number("corner_holes.diameter", corner.get("diameter"))
        if not (diameter > 0):
            raise ValueError("corner_hole_diameter 必须 > 0")
        if not (diameter < base_limit / 2):
            raise ValueError("corner_hole_diameter 必须小于底板较短边的一半")
        corner.setdefault("offset_x", base["length"] / 2 - 10)
        corner.setdefault("offset_y", base["width"] / 2 - 10)
        offset_x = _require_number("corner_holes.offset_x", corner.get("offset_x"))
        offset_y = _require_number("corner_holes.offset_y", corner.get("offset_y"))
        if not (0 < offset_x < base["length"] / 2):
            raise ValueError("corner_hole_offset_x 必须 > 0 且 < length / 2")
        if not (0 < offset_y < base["width"] / 2):
            raise ValueError("corner_hole_offset_y 必须 > 0 且 < width / 2")
        corner["diameter"] = diameter
        corner["offset_x"] = offset_x
        corner["offset_y"] = offset_y

    boss = plan.setdefault("center_boss", {})
    boss.setdefault("enabled", False)
    if boss["enabled"]:
        _fill_fallback_number(plan, "center_boss", "diameter")
        _fill_fallback_number(plan, "center_boss", "height")
        boss_diameter = _require_number("center_boss.diameter", boss.get("diameter"))
        boss_height = _require_number("center_boss.height", boss.get("height"))
        if not (boss_diameter > 0 and boss_diameter < base_limit):
            raise ValueError("center_boss.diameter 必须 > 0 且小于底座直径或较短边")
        if not (0 < boss_height <= 300):
            raise ValueError("center_boss.height 必须 > 0 且 <= 300")
        boss["diameter"] = boss_diameter
        boss["height"] = boss_height

    center_hole = plan.setdefault("center_hole", {})
    center_hole.setdefault("enabled", False)
    center_hole.setdefault("through_all", True)
    if center_hole["enabled"]:
        _fill_fallback_number(plan, "center_hole", "diameter")
        hole_diameter = _require_number("center_hole.diameter", center_hole.get("diameter"))
        if not (hole_diameter > 0):
            raise ValueError("center_hole.diameter 必须 > 0")
        if boss.get("enabled"):
            if not (hole_diameter < boss["diameter"]):
                raise ValueError("center_hole.diameter 必须小于 center_boss.diameter")
            center_hole["target"] = "boss"
        else:
            if not (hole_diameter < base_limit):
                raise ValueError("center_hole.diameter 必须小于底板较短边或底座直径")
            center_hole["target"] = "base"
        center_hole["diameter"] = hole_diameter

    fillet = plan.setdefault("fillet", {})
    fillet.setdefault("enabled", False)
    if fillet["enabled"]:
        _fill_fallback_number(plan, "fillet", "radius")
        radius = _require_number("fillet.radius", fillet.get("radius"))
        if not (radius > 0 and radius < thickness / 2):
            raise ValueError("fillet.radius 必须 > 0 且 < base.thickness / 2")
        fillet["radius"] = radius

    _default_outputs(plan)
    plan.setdefault("notes", [])
    return plan
