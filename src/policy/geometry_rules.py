"""Geometry safety rules for FeaturePlan v2."""

from __future__ import annotations

from typing import Any, Iterable

from cad_dsl.material_catalog import resolve_material


MAX_DIMENSION_MM = 1000.0
MIN_POSITIVE_MM = 0.001
MAX_PATTERN_COUNT = 50

ALLOWED_PLANES = {"Top", "Front", "Right", "top_face", "bottom_face", "front_face", "right_face"}
ALLOWED_PATTERN_DIRECTIONS = {"x", "y", "z", "X", "Y", "Z"}
ALLOWED_SLOT_DIRECTIONS = {"x", "y", "X", "Y"}
ALLOWED_MIRROR_PLANES = {"Top", "Front", "Right", "center_x", "center_y", "center_z"}
ALLOWED_CHAMFER_TARGETS = {"outer_edges", "selected_edges"}
ALLOWED_REFERENCE_PLANES = {"Top", "Front", "Right", "top_face", "bottom_face"}
ALLOWED_HOSTS = {"base", "boss"}
ALLOWED_CUSTOM_PROPERTIES = {"PartNumber", "Description", "Designer", "ProjectNo", "Revision", "MaterialSpec"}
ALLOWED_NAMED_DIMENSIONS = {
    "D_base_length",
    "D_base_width",
    "D_base_thickness",
    "D_hole_diameter",
    "D_boss_diameter",
    "D_boss_height",
    "D_fillet_radius",
    "D_chamfer_distance",
}
AMBIGUOUS_REFERENCES = {"", "auto", "default", "any", "some", "selected", "unknown", "*"}


def iter_numbers(value: Any) -> Iterable[float]:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key == "center":
                continue
            yield from iter_numbers(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from iter_numbers(child)


def validate_numeric_bounds(parameters: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for number in iter_numbers(parameters):
        if number < 0:
            errors.append(f"尺寸不能为负数: {number}")
        if number > MAX_DIMENSION_MM:
            errors.append(f"尺寸超过上限 {MAX_DIMENSION_MM} mm: {number}")
    return errors


def _positive(parameters: dict[str, Any], name: str, operation_type: str, errors: list[str]) -> float:
    try:
        value = float(parameters.get(name, 0))
    except (TypeError, ValueError):
        errors.append(f"{operation_type} {name} must be numeric")
        return 0.0
    if value <= 0:
        errors.append(f"{operation_type} {name} 必须大于 0")
    return value


def _center(parameters: dict[str, Any], operation_type: str, errors: list[str]) -> None:
    center = parameters.get("center")
    if not isinstance(center, (list, tuple)) or len(center) != 2:
        errors.append(f"{operation_type} center must be [x, y]")


def _plane(parameters: dict[str, Any], operation_type: str, errors: list[str]) -> None:
    if parameters.get("plane") not in ALLOWED_PLANES:
        errors.append(f"{operation_type} plane must be a controlled plane or face selector")


def _host(parameters: dict[str, Any], operation_type: str, errors: list[str]) -> None:
    host = parameters.get("host")
    if host is None:
        return
    if str(host) not in ALLOWED_HOSTS:
        errors.append(f"{operation_type} host must be base or boss")


def _explicit_reference(value: Any, name: str, operation_type: str, errors: list[str]) -> None:
    text = str(value or "").strip()
    if text.lower() in AMBIGUOUS_REFERENCES:
        errors.append(f"{operation_type} {name} must be explicit; 模糊引用 is not allowed")


def _explicit_reference_list(value: Any, name: str, operation_type: str, errors: list[str]) -> None:
    if not isinstance(value, (list, tuple)) or not value:
        errors.append(f"{operation_type} {name} must be a non-empty reference list")
        return
    for item in value:
        _explicit_reference(item, name, operation_type, errors)


def validate_feature_geometry(operation_type: str, parameters: dict[str, Any]) -> list[str]:
    errors = validate_numeric_bounds(parameters)

    if operation_type == "create_new_part":
        template = parameters.get("template")
        if template is not None and template != "enterprise_part_mm":
            errors.append("create_new_part template must be enterprise_part_mm")

    if operation_type == "create_sketch":
        _host(parameters, operation_type, errors)
        if parameters.get("plane") not in {"Top", "Front", "Right", "top_face"}:
            errors.append("create_sketch plane must be exactly Top/Front/Right/top_face")
        if not str(parameters.get("name", "")).strip():
            errors.append("create_sketch name cannot be empty")

    if operation_type in {"sketch_center_rectangle", "sketch_circle", "create_through_hole"}:
        _center(parameters, operation_type, errors)

    if operation_type == "sketch_center_rectangle":
        _positive(parameters, "length", operation_type, errors)
        _positive(parameters, "width", operation_type, errors)

    if operation_type == "sketch_circle":
        _positive(parameters, "diameter", operation_type, errors)

    if operation_type == "extrude_boss":
        _positive(parameters, "depth", operation_type, errors)
        if parameters.get("direction", "one_side") not in {"one_side", "midplane"}:
            errors.append("extrude_boss direction must be one_side/midplane")

    if operation_type == "extrude_cut":
        if parameters.get("through_all", False) is False:
            _positive(parameters, "depth", operation_type, errors)
        if parameters.get("direction", "normal") not in {"normal", "reverse"}:
            errors.append("extrude_cut direction must be normal/reverse")

    if operation_type == "create_through_hole":
        _host(parameters, operation_type, errors)
        if parameters.get("plane") not in {"Top", "Front", "Right", "top_face"}:
            errors.append("create_through_hole plane must be exactly Top/Front/Right/top_face")
        _positive(parameters, "diameter", operation_type, errors)

    if operation_type == "create_blind_hole":
        _host(parameters, operation_type, errors)
        _plane(parameters, operation_type, errors)
        _center(parameters, operation_type, errors)
        _positive(parameters, "diameter", operation_type, errors)
        _positive(parameters, "depth", operation_type, errors)

    if operation_type == "create_counterbore_hole":
        _host(parameters, operation_type, errors)
        _plane(parameters, operation_type, errors)
        _center(parameters, operation_type, errors)
        hole_diameter = _positive(parameters, "hole_diameter", operation_type, errors)
        counterbore_diameter = _positive(parameters, "counterbore_diameter", operation_type, errors)
        _positive(parameters, "counterbore_depth", operation_type, errors)
        if parameters.get("through_all", True) is False:
            _positive(parameters, "depth", operation_type, errors)
        if counterbore_diameter <= hole_diameter:
            errors.append("create_counterbore_hole counterbore_diameter must be greater than hole_diameter")

    if operation_type == "create_countersink_hole":
        _host(parameters, operation_type, errors)
        _plane(parameters, operation_type, errors)
        _center(parameters, operation_type, errors)
        hole_diameter = _positive(parameters, "hole_diameter", operation_type, errors)
        countersink_diameter = _positive(parameters, "countersink_diameter", operation_type, errors)
        angle = _positive(parameters, "angle", operation_type, errors)
        if parameters.get("through_all", True) is False:
            _positive(parameters, "depth", operation_type, errors)
        if countersink_diameter <= hole_diameter:
            errors.append("create_countersink_hole countersink_diameter must be greater than hole_diameter")
        if not (0 < angle <= 180):
            errors.append("create_countersink_hole angle 必须大于 0 and not exceed 180")

    if operation_type == "create_base_plate":
        _positive(parameters, "length", "底板", errors)
        _positive(parameters, "width", "底板", errors)
        _positive(parameters, "thickness", "底板", errors)
        if parameters.get("plane", "Top") not in {"Top", "Front", "Right"}:
            errors.append("底板 plane 只能是 Top/Front/Right")

    if operation_type == "cut_corner_holes":
        _positive(parameters, "diameter", "四角孔", errors)
        has_offsets = "offset_x" in parameters and "offset_y" in parameters
        has_edge_margin = "edge_margin" in parameters
        if not has_offsets and not has_edge_margin:
            errors.append("cut_corner_holes must include offset_x/offset_y or edge_margin")
        if has_offsets:
            _positive(parameters, "offset_x", "四角孔", errors)
            _positive(parameters, "offset_y", "四角孔", errors)
        elif "offset_x" in parameters or "offset_y" in parameters:
            errors.append("cut_corner_holes offset_x and offset_y must be provided together")
        if has_edge_margin:
            _positive(parameters, "edge_margin", operation_type, errors)

    if operation_type == "cut_slot":
        _host(parameters, operation_type, errors)
        _plane(parameters, operation_type, errors)
        _center(parameters, operation_type, errors)
        length = _positive(parameters, "length", operation_type, errors)
        width = _positive(parameters, "width", operation_type, errors)
        if "through_all" not in parameters and "depth" not in parameters:
            errors.append("cut_slot must include depth or through_all")
        elif parameters.get("through_all", False) is False:
            _positive(parameters, "depth", operation_type, errors)
        if length <= width:
            errors.append("cut_slot length must be greater than width")
        if parameters.get("direction", "x") not in ALLOWED_SLOT_DIRECTIONS:
            errors.append("cut_slot direction must be x or y")

    if operation_type == "cut_rectangle_pocket":
        _host(parameters, operation_type, errors)
        _plane(parameters, operation_type, errors)
        _center(parameters, operation_type, errors)
        _positive(parameters, "length", operation_type, errors)
        _positive(parameters, "width", operation_type, errors)
        _positive(parameters, "depth", operation_type, errors)

    if operation_type == "create_center_boss":
        _host(parameters, operation_type, errors)
        _positive(parameters, "diameter", "中心凸台", errors)
        _positive(parameters, "height", "中心凸台", errors)

    if operation_type == "cut_center_hole":
        _positive(parameters, "diameter", "中心孔", errors)
        if parameters.get("target", "boss") not in {"boss", "base"}:
            errors.append("cut_center_hole target must be boss or base")
        if "depth" in parameters:
            _positive(parameters, "depth", operation_type, errors)

    if operation_type == "add_fillet":
        if parameters.get("target", "outer_edges") not in {"outer_edges", "top_edges", "bottom_edges"}:
            errors.append("add_fillet target must be outer_edges/top_edges/bottom_edges")
        _positive(parameters, "radius", operation_type, errors)

    if operation_type == "add_chamfer":
        if parameters.get("target", "outer_edges") not in ALLOWED_CHAMFER_TARGETS:
            errors.append("add_chamfer target must be outer_edges or selected_edges")
        _positive(parameters, "distance", operation_type, errors)
        angle = float(parameters.get("angle", 45))
        if not (0 < angle < 90):
            errors.append("add_chamfer angle 必须大于 0 and less than 90")

    if operation_type == "create_linear_pattern":
        count = int(parameters.get("count", 0))
        if not (1 < count <= MAX_PATTERN_COUNT):
            errors.append(f"create_linear_pattern count must be greater than 1 and not exceed {MAX_PATTERN_COUNT}")
        _positive(parameters, "spacing", operation_type, errors)
        if parameters.get("direction") not in ALLOWED_PATTERN_DIRECTIONS:
            errors.append("create_linear_pattern direction must be x/y/z")
        _explicit_reference(parameters.get("seed_feature"), "seed_feature", operation_type, errors)

    if operation_type == "create_circular_pattern":
        count = int(parameters.get("count", 0))
        if not (1 < count <= MAX_PATTERN_COUNT):
            errors.append(f"create_circular_pattern count must be greater than 1 and not exceed {MAX_PATTERN_COUNT}")
        angle = float(parameters.get("angle", 360))
        if not (0 < angle <= 360):
            errors.append("create_circular_pattern angle 必须大于 0 and not exceed 360")
        _explicit_reference(parameters.get("axis"), "axis", operation_type, errors)
        _explicit_reference(parameters.get("seed_feature"), "seed_feature", operation_type, errors)

    if operation_type == "mirror_feature":
        _explicit_reference(parameters.get("seed_feature"), "seed_feature", operation_type, errors)
        if parameters.get("mirror_plane") not in ALLOWED_MIRROR_PLANES:
            errors.append("mirror_feature mirror_plane must be explicit and allowlisted")

    if operation_type == "set_material":
        material_value = parameters.get("material_id", parameters.get("material"))
        if resolve_material(material_value) is None:
            errors.append("set_material material/material_id 必须来自项目官方 SOLIDWORKS 材料库")

    if operation_type == "set_custom_property":
        if parameters.get("key") not in ALLOWED_CUSTOM_PROPERTIES:
            errors.append("set_custom_property key 必须来自允许字段")
        if not str(parameters.get("value", "")).strip():
            errors.append("set_custom_property value cannot be empty")

    if operation_type == "modify_named_dimension":
        if parameters.get("dimension_name") not in ALLOWED_NAMED_DIMENSIONS:
            errors.append("modify_named_dimension dimension_name 必须来自尺寸白名单")
        _positive(parameters, "value", operation_type, errors)

    if operation_type == "create_offset_plane":
        if parameters.get("base_plane") not in ALLOWED_REFERENCE_PLANES:
            errors.append("create_offset_plane base_plane must be explicit and allowlisted")
        offset = float(parameters.get("offset", 0))
        if offset == 0:
            errors.append("create_offset_plane offset cannot be 0")
        if abs(offset) > MAX_DIMENSION_MM:
            errors.append(f"create_offset_plane offset cannot exceed {MAX_DIMENSION_MM} mm")
        _explicit_reference(parameters.get("name"), "name", operation_type, errors)

    if operation_type == "create_axis":
        _explicit_reference(parameters.get("name"), "name", operation_type, errors)
        if parameters.get("reference_type") != "two_planes":
            errors.append("create_axis reference_type must be two_planes")
        references = parameters.get("references")
        _explicit_reference_list(references, "references", operation_type, errors)
        if isinstance(references, (list, tuple)) and len(references) != 2:
            errors.append("create_axis references must contain exactly two planes in two_planes mode")
        if isinstance(references, (list, tuple)):
            for reference in references:
                if reference not in ALLOWED_REFERENCE_PLANES and reference not in ALLOWED_MIRROR_PLANES:
                    errors.append("create_axis references must be explicit and controlled reference planes")

    return errors

