"""Semantic binding helpers for near-valid FeaturePlan normalization.

This layer is intentionally narrow:
- it does not invent unsupported operations
- it does not bypass Policy Engine
- it only canonicalizes near-miss parameterizations into the current
  Feature Registry / executor contract
"""

from __future__ import annotations

import re
from typing import Any

from cad_dsl.feature_references import build_seed_feature_aliases_from_dicts, resolve_seed_feature_reference
from cad_dsl.feature_registry import FeatureRegistry, default_registry


METRIC_CLEARANCE_MM = {
    3.0: 3.4,
    4.0: 4.5,
    5.0: 5.5,
    6.0: 6.6,
    8.0: 9.0,
    10.0: 11.0,
    12.0: 13.5,
}

FILLET_TARGET_HINTS = (
    "外轮廓",
    "外边缘",
    "外围边",
    "周边",
    "outer contour",
    "outer edge",
    "outer edges",
    "perimeter",
)

OPTIONAL_FEATURE_KEYWORDS = {
    "create_center_boss": ("凸台", "中心凸台", "圆柱凸台", "boss"),
    "cut_center_hole": ("中心孔", "中心通孔", "凸台中心孔", "hole"),
    "create_through_hole": ("通孔", "贯穿孔", "hole"),
    "create_blind_hole": ("盲孔", "blind hole"),
    "cut_corner_holes": (
        "四角孔",
        "四角通孔",
        "角孔",
        "角上通孔",
        "螺栓孔",
        "螺丝孔",
        "corner hole",
        "corner holes",
        "corner through hole",
        "corner through holes",
        "bolt hole",
    ),
    "add_fillet": ("圆角", "倒圆", "fillet", "r角", "r3", "r2"),
    "add_chamfer": ("倒角", "chamfer", "c2", "c1"),
    "cut_slot": ("通槽", "槽", "slot"),
    "cut_rectangle_pocket": ("口袋", "矩形口袋", "pocket"),
    "create_linear_pattern": ("线性阵列", "阵列", "linear pattern"),
    "create_circular_pattern": ("圆周阵列", "circular pattern"),
    "mirror_feature": ("镜像", "mirror"),
    "create_offset_plane": ("偏移基准面", "offset plane"),
    "create_axis": ("基准轴", "axis"),
}

SLOT_DIRECTION_HINTS_Y = (
    "沿宽度方向",
    "宽度方向",
    "沿Y方向",
    "沿 y 方向",
    "宽轴方向",
    "across width",
    "along width direction",
    "along the width direction",
    "along y",
)

SLOT_DIRECTION_HINTS_X = (
    "沿长度方向",
    "长度方向",
    "沿X方向",
    "沿 x 方向",
    "长轴方向",
    "along x",
    "along length direction",
    "along the length direction",
)

MATERIAL_PROPERTY_ONLY_HINTS = (
    "材料",
    "material",
    "part number",
    "description",
    "零件编号",
    "物料编号",
    "描述",
    "材质",
)

PLANE_ALIASES = {
    "top": "Top",
    "top plane": "Top",
    "topplane": "Top",
    "top_face": "top_face",
    "top face": "top_face",
    "upper_face": "top_face",
    "upper face": "top_face",
    "上视基准面": "Top",
    "上基准面": "Top",
    "front": "Front",
    "front plane": "Front",
    "前视基准面": "Front",
    "right": "Right",
    "right plane": "Right",
    "右视基准面": "Right",
}

EXTRUDE_BOSS_DIRECTION_ALIASES = {
    "normal": "one_side",
    "default": "one_side",
    "one_side": "one_side",
    "oneside": "one_side",
    "one side": "one_side",
    "blind": "one_side",
    "midplane": "midplane",
    "mid_plane": "midplane",
    "mid plane": "midplane",
    "symmetric": "midplane",
    "symmetric about sketch": "midplane",
}

def _prompt_mentions_any(prompt: str, lowered: str, hints: tuple[str, ...]) -> bool:
    for hint in hints:
        if not isinstance(hint, str) or not hint:
            continue
        if hint.isascii():
            if hint.lower() in lowered:
                return True
        elif hint in prompt:
            return True
    return False



def _sanitize_metadata_parameter_paths(
    metadata: Any,
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Repair or drop invalid provenance paths so Policy validation cannot 500.

    Local 7B models frequently emit malformed provenance entries such as
    ``create_base_plate.001.params.plane`` where the operation *name* and *id*
    are joined with a dot, producing a 4-segment path the Policy Engine rejects
    (it requires exactly ``<operation_id>.params.<parameter>``). They also emit
    paths pointing at operations or parameters that do not exist. Rather than
    letting these bubble up as fatal metadata violations, we deterministically
    repair the ones we can map back to a real operation/parameter and silently
    drop the rest.
    """

    if not isinstance(metadata, dict):
        return metadata if isinstance(metadata, dict) else {}

    # Build lookup of valid operation ids and their parameter names.
    op_params: dict[str, set[str]] = {}
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op_id = str(operation.get("id", "")).strip()
        if not op_id:
            continue
        params = operation.get("params")
        op_params[op_id] = set(params.keys()) if isinstance(params, dict) else set()

    def _repair_path(path: str) -> str | None:
        text = str(path)
        parts = text.split(".")
        if "params" not in parts:
            return None
        p_index = parts.index("params")
        # Parameter name is everything after the ``params`` segment joined back.
        param_name = ".".join(parts[p_index + 1 :]).strip()
        if not param_name:
            return None
        # The operation id is the segment immediately before ``params``; the LLM
        # sometimes prefixes the op name, so also try the last pre-``params``
        # segment and progressively shorter suffixes until one matches a real id.
        head = parts[:p_index]
        for start in range(len(head)):
            candidate_id = ".".join(head[start:]).strip()
            if candidate_id in op_params and param_name in op_params[candidate_id]:
                return f"{candidate_id}.params.{param_name}"
        return None

    sanitized = dict(metadata)
    for field in ("inferred_parameters", "explicit_parameters"):
        value = sanitized.get(field)
        if not isinstance(value, (list, tuple)):
            continue
        repaired: list[str] = []
        for path in value:
            fixed = _repair_path(path)
            if fixed is not None and fixed not in repaired:
                repaired.append(fixed)
        sanitized[field] = repaired
    return sanitized


def _merge_inferred_parameters(metadata: Any, new_paths: list[str]) -> dict[str, Any]:
    """Add newly inferred parameter provenance paths into metadata.inferred_parameters.

    Deterministic center repairs are LLM-inferred (not user-provided), so their
    provenance must be recorded as inferred to satisfy the Policy Engine and to
    keep the execution layer honest about what was computed vs. user-specified.
    """

    merged = dict(metadata) if isinstance(metadata, dict) else {}
    existing = merged.get("inferred_parameters")
    paths: list[str] = [str(item) for item in existing] if isinstance(existing, (list, tuple)) else []
    for path in new_paths:
        if path not in paths:
            paths.append(path)
    merged["inferred_parameters"] = paths
    return merged


def bind_featureplan_semantics(
    prompt: str,
    plan_data: dict[str, Any],
    registry: FeatureRegistry | None = None,
) -> dict[str, Any]:
    if not isinstance(plan_data, dict):
        return plan_data

    registry = registry or default_registry()
    normalized = dict(plan_data)
    operations = normalized.get("operations")
    if not isinstance(operations, list):
        return normalized

    operations = _prune_material_property_only_hallucinations(prompt, operations)
    base_size = _infer_base_size_from_operations(operations)
    base_thickness = _infer_base_thickness_from_operations(operations)
    has_center_boss = any(
        isinstance(operation, dict) and operation.get("op") == "create_center_boss"
        for operation in operations
    )
    slot_operations = [operation for operation in operations if isinstance(operation, dict) and str(operation.get("op", "")).strip() == "cut_slot"]
    slot_ids = [str(operation.get("id", "")).strip() for operation in slot_operations]
    slot_total = len(slot_ids)
    slot_index_map = {op_id: index for index, op_id in enumerate(slot_ids)}
    pocket_operations = [operation for operation in operations if isinstance(operation, dict) and str(operation.get("op", "")).strip() == "cut_rectangle_pocket"]
    pocket_ids = [str(operation.get("id", "")).strip() for operation in pocket_operations]
    pocket_total = len(pocket_ids)
    pocket_index_map = {op_id: index for index, op_id in enumerate(pocket_ids)}

    # Centers the user explicitly requested must never be silently rewritten by
    # deterministic binding: an out-of-bounds explicit center has to bubble up as
    # a confirmation-required violation instead of being clamped away.
    explicit_center_ids: set[str] = set()
    metadata = normalized.get("metadata")
    if isinstance(metadata, dict):
        explicit_list = metadata.get("explicit_parameters")
        if isinstance(explicit_list, list):
            for path in explicit_list:
                match = re.match(r"^(?P<op>.+)\.params\.center$", str(path))
                if match:
                    explicit_center_ids.add(match.group("op"))

    bound_operations: list[dict[str, Any]] = []
    inferred_center_paths: list[str] = []
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op_name = str(operation.get("op", "")).strip()
        operation_id = str(operation.get("id", "")).strip()
        params = dict(operation.get("params") or {})
        original_center = _coerce_xy(params.get("center")) if isinstance(params.get("center"), (list, tuple)) else None
        params = _bind_operation_params(
            prompt,
            operation_id,
            op_name,
            params,
            has_center_boss,
            base_size,
            base_thickness,
            slot_index=slot_index_map.get(operation_id),
            slot_total=slot_total,
            pocket_index=pocket_index_map.get(operation_id),
            pocket_total=pocket_total,
        )
        if op_name in {"create_through_hole", "create_blind_hole"} and operation_id:
            if operation_id in explicit_center_ids:
                # User explicitly specified this center; do not rewrite it. Restore
                # the original value so an out-of-bounds explicit center still fails
                # Policy validation and prompts the user for confirmation.
                if original_center is not None:
                    params["center"] = [original_center[0], original_center[1]]
            else:
                bound_center = _coerce_xy(params.get("center")) if isinstance(params.get("center"), (list, tuple)) else None
                if bound_center is not None and (
                    original_center is None
                    or abs(bound_center[0] - original_center[0]) > 1e-9
                    or abs(bound_center[1] - original_center[1]) > 1e-9
                ):
                    inferred_center_paths.append(f"{operation_id}.params.center")
        definition = registry.get(op_name)
        if definition is not None:
            allowed = definition.allowed_parameters
            if allowed:
                params = {key: value for key, value in params.items() if key in allowed}
        bound_operations.append({**operation, "params": params})

    bound_operations = _bind_pattern_seed_references(bound_operations)
    bound_operations = _expand_symmetric_pockets(prompt, bound_operations, base_size)
    normalized["operations"] = bound_operations
    if inferred_center_paths:
        normalized["metadata"] = _merge_inferred_parameters(normalized.get("metadata"), inferred_center_paths)
    # Repair/drop malformed provenance paths (e.g. op-name+id joined with a dot,
    # or references to non-existent operations/params) so Policy validation does
    # not reject an otherwise-valid plan with a fatal metadata violation.
    if isinstance(normalized.get("metadata"), dict):
        normalized["metadata"] = _sanitize_metadata_parameter_paths(
            normalized.get("metadata"), bound_operations
        )
    return canonicalize_featureplan_structure(normalized)



def _bind_pattern_seed_references(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aliases = build_seed_feature_aliases_from_dicts(operations)
    reusable_seed_ops = {
        "create_through_hole",
        "create_blind_hole",
        "create_counterbore_hole",
        "create_countersink_hole",
        "cut_slot",
        "cut_rectangle_pocket",
    }
    prior_reusable_ids: list[str] = []
    bound: list[dict[str, Any]] = []

    for operation in operations:
        op_name = str(operation.get("op", "")).strip()
        operation_id = str(operation.get("id", "")).strip()
        params = dict(operation.get("params") or {})

        if op_name in {"create_linear_pattern", "create_circular_pattern", "mirror_feature"}:
            raw_seed = params.get("seed_feature")
            normalized_seed = resolve_seed_feature_reference(raw_seed, aliases)
            if normalized_seed:
                params["seed_feature"] = normalized_seed
            elif len(prior_reusable_ids) == 1:
                params["seed_feature"] = prior_reusable_ids[0]

        bound.append({**operation, "params": params})

        if operation_id and op_name in reusable_seed_ops:
            prior_reusable_ids = [operation_id]

    return bound

def _prune_material_property_only_hallucinations(prompt: str, operations: list[Any]) -> list[Any]:
    lowered = str(prompt).lower()
    material_intent = _prompt_mentions_any(prompt, lowered, MATERIAL_PROPERTY_ONLY_HINTS)
    feature_intent = any(_prompt_mentions_any(prompt, lowered, hints) for hints in OPTIONAL_FEATURE_KEYWORDS.values())
    if not material_intent or feature_intent:
        return operations

    pruned: list[Any] = []
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op_name = str(operation.get("op", "")).strip()
        if op_name in OPTIONAL_FEATURE_KEYWORDS:
            continue
        pruned.append(operation)
    return pruned


def _bind_operation_params(
    prompt: str,
    operation_id: str,
    op_name: str,
    params: dict[str, Any],
    has_center_boss: bool,
    base_size: tuple[float, float] | None,
    base_thickness: float | None,
    slot_index: int | None = None,
    slot_total: int = 0,
    pocket_index: int | None = None,
    pocket_total: int = 0,
) -> dict[str, Any]:
    normalized = dict(params)

    if "plane" in normalized:
        normalized_plane = _normalize_plane_alias(normalized.get("plane"), op_name)
        if normalized_plane is not None:
            normalized["plane"] = normalized_plane

    if op_name in {"create_through_hole", "create_blind_hole", "create_counterbore_hole", "create_countersink_hole", "cut_rectangle_pocket", "cut_slot"}:
        plane_text = str(normalized.get("plane", "")).strip()
        if not plane_text and base_size is not None:
            normalized["plane"] = "top_face"

    if op_name in {"create_sketch", "create_through_hole", "create_blind_hole", "create_counterbore_hole", "create_countersink_hole", "cut_rectangle_pocket", "cut_slot", "create_center_boss"}:
        inferred_host = _infer_operation_host(prompt, operation_id, op_name, normalized)
        current_host = str(normalized.get("host", "")).strip()
        # Only ``base``/``boss`` are valid hosts. The local model sometimes emits
        # an invalid value (e.g. ``top_face``, ``plate``, a feature name); replace
        # any missing OR invalid host with the deterministically inferred host so
        # Policy does not reject the plan with "host must be base or boss".
        if not current_host or current_host not in {"base", "boss"}:
            normalized["host"] = inferred_host if inferred_host is not None else "base"

    if op_name == "extrude_boss":
        direction = _normalize_extrude_boss_direction(normalized.get("direction"))
        if direction is not None:
            normalized["direction"] = direction

    if op_name == "cut_corner_holes":
        diameter = _coerce_float(normalized.get("diameter"))
        if diameter is None or diameter <= 0:
            explicit_diameter = _infer_explicit_corner_hole_diameter_from_prompt(prompt)
            if explicit_diameter is not None:
                normalized["diameter"] = explicit_diameter
            else:
                inferred = _infer_metric_clearance_from_prompt(prompt, op_name="cut_corner_holes")
                if inferred is not None:
                    normalized["diameter"] = inferred

        center = normalized.pop("center", None)
        if center is not None and "offset_x" not in normalized and "offset_y" not in normalized:
            xy = _coerce_xy(center)
            if xy is not None:
                normalized["offset_x"] = abs(xy[0])
                normalized["offset_y"] = abs(xy[1])

        inferred_edge_margin = _infer_default_corner_hole_edge_margin(normalized, base_size)
        edge_margin = _coerce_float(normalized.get("edge_margin"))
        diameter = _coerce_float(normalized.get("diameter"))
        radius = diameter / 2 if diameter is not None and diameter > 0 else None
        if edge_margin is None and not ("offset_x" in normalized and "offset_y" in normalized):
            if inferred_edge_margin is not None:
                normalized["edge_margin"] = inferred_edge_margin
        elif edge_margin is not None and inferred_edge_margin is not None and radius is not None:
            if edge_margin <= radius:
                normalized["edge_margin"] = inferred_edge_margin

    elif op_name == "cut_center_hole":
        normalized.pop("plane", None)
        normalized.pop("center", None)
        inferred_diameter = _infer_center_hole_diameter_from_prompt(prompt)
        if inferred_diameter is not None:
            normalized["diameter"] = inferred_diameter
        else:
            diameter = _coerce_float(normalized.get("diameter"))
            if diameter is None or diameter <= 0:
                inferred_diameter = _infer_center_hole_diameter_from_prompt(prompt)
                if inferred_diameter is not None:
                    normalized["diameter"] = inferred_diameter
        if "target" not in normalized:
            normalized["target"] = "boss" if has_center_boss else "base"
        if _prompt_requests_through_center_hole(prompt) and "depth" not in normalized:
            normalized["through_all"] = True

    elif op_name == "create_center_boss":
        normalized.setdefault("host", "base")
        explicit_boss = _infer_center_boss_dimensions_from_prompt(prompt)
        if explicit_boss.get("diameter") is not None:
            normalized["diameter"] = explicit_boss["diameter"]
        if explicit_boss.get("height") is not None:
            normalized["height"] = explicit_boss["height"]

    elif op_name == "cut_slot":
        explicit_slot_width = _infer_explicit_slot_width_from_prompt(prompt)
        if explicit_slot_width is not None:
            normalized["width"] = explicit_slot_width
        length = _coerce_float(normalized.get("length"))
        width = _coerce_float(normalized.get("width"))
        if length is not None and width is not None and length > 0 and width > 0 and length < width:
            normalized["length"], normalized["width"] = width, length
        inferred_direction = _infer_slot_direction_from_prompt(prompt)
        if inferred_direction is None:
            inferred_direction = _infer_slot_direction_from_geometry(normalized, base_size)
        if inferred_direction is not None:
            normalized["direction"] = inferred_direction
        inferred_span = _infer_slot_span_from_prompt(prompt, normalized, base_size)
        if inferred_span is not None:
            normalized["length"] = inferred_span
        if _prompt_requests_slot_through_thickness(prompt) and "depth" not in normalized:
            normalized["through_all"] = True
        elif "depth" not in normalized and "through_all" not in normalized:
            inferred_slot_depth = _infer_default_slot_depth(normalized, base_thickness)
            if inferred_slot_depth is not None:
                normalized["depth"] = inferred_slot_depth
        normalized_center = _normalize_edge_distance_slot_center(
            prompt,
            operation_id,
            normalized,
            base_size,
            slot_index=slot_index,
            slot_total=slot_total,
        )
        if normalized_center is not None:
            normalized["center"] = normalized_center

    elif op_name == "cut_rectangle_pocket":
        explicit_pocket = _infer_explicit_pocket_dimensions_from_prompt(prompt)
        if explicit_pocket.get("length") is not None:
            normalized["length"] = explicit_pocket["length"]
        if explicit_pocket.get("width") is not None:
            normalized["width"] = explicit_pocket["width"]
        if explicit_pocket.get("depth") is not None:
            normalized["depth"] = explicit_pocket["depth"]
        normalized_center = _normalize_pocket_center_from_prompt(
            prompt,
            normalized,
            base_size,
            operation_id=operation_id,
            pocket_index=pocket_index,
            pocket_total=pocket_total,
        )
        if normalized_center is not None:
            normalized["center"] = normalized_center

    elif op_name in {"create_through_hole", "create_blind_hole"}:
        if "plane" not in normalized and base_size is not None:
            normalized["plane"] = "top_face"
        normalized.setdefault("host", "base")
        normalized_center = _normalize_hole_center(prompt, normalized, base_size)
        if normalized_center is not None:
            normalized["center"] = normalized_center

    elif op_name == "create_linear_pattern":
        direction = str(normalized.get("direction", "")).strip().lower()
        if direction in {"x", "y", "z"}:
            normalized["direction"] = direction

    elif op_name == "add_fillet":
        normalized.pop("center", None)
        target = str(normalized.get("target", "")).strip()
        if target not in {"outer_edges", "top_edges", "bottom_edges"}:
            normalized["target"] = "outer_edges"

    return normalized


def _normalize_plane_alias(value: Any, op_name: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    normalized = PLANE_ALIASES.get(lowered)
    if normalized is None:
        return None
    if op_name == "create_base_plate" and normalized == "top_face":
        return "Top"
    return normalized


def _normalize_extrude_boss_direction(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    return EXTRUDE_BOSS_DIRECTION_ALIASES.get(text)



def _prompt_requests_through_center_hole(prompt: str) -> bool:
    if not isinstance(prompt, str):
        return False
    lowered = prompt.lower()
    return (
        "通孔" in prompt
        or "贯穿孔" in prompt
        or "through hole" in lowered
        or "through-hole" in lowered
    )


def _prompt_requests_through_slot(prompt: str) -> bool:
    if not isinstance(prompt, str):
        return False
    lowered = prompt.lower()
    return (
        "通槽" in prompt
        or "贯通槽" in prompt
        or "贯穿槽" in prompt
        or "through slot" in lowered
        or "through-slot" in lowered
    )


def _infer_slot_span_from_prompt(
    prompt: str,
    params: dict[str, Any],
    base_size: tuple[float, float] | None,
) -> float | None:
    if not isinstance(prompt, str) or base_size is None:
        return None

    explicit_span = _infer_explicit_slot_span_from_prompt(prompt)
    if explicit_span is not None:
        return explicit_span

    if not _prompt_requests_through_slot(prompt):
        return None

    direction = str(params.get("direction", "") or "").strip().lower()
    base_length, base_width = base_size
    if direction == "y":
        return base_width
    if direction == "x":
        return base_length
    return None


def _infer_explicit_slot_span_from_prompt(prompt: str) -> float | None:
    if not isinstance(prompt, str):
        return None

    patterns = (
        r"(?:通槽|槽|slot).{0,16}?(?:长度|长|span)\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?",
        r"(?:长度|长|span)\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?.{0,12}?(?:通槽|槽|slot)",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if value > 0:
            return value
    return None


def _infer_explicit_slot_width_from_prompt(prompt: str) -> float | None:
    if not isinstance(prompt, str):
        return None

    patterns = (
        r"(?:通槽|槽|slot).{0,20}?(?:宽度|槽宽|宽)\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?",
        r"(?:宽度|槽宽|宽)\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?.{0,16}?(?:通槽|槽|slot)",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if value > 0:
            return value
    return None


def _infer_center_boss_dimensions_from_prompt(prompt: str) -> dict[str, float]:
    if not isinstance(prompt, str):
        return {}

    result: dict[str, float] = {}
    pair_patterns = (
        r"(?:直径(?:为)?|[ØøΦφ⌀])\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?.{0,12}?(?:中心)?(?:圆柱)?凸台.{0,12}?(?:高|高度|height)\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?",
        r"(?:中心)?(?:圆柱)?凸台.{0,16}?(?:直径(?:为)?|[ØøΦφ⌀])\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?.{0,12}?(?:高|高度|height)\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?",
        r"(?:高|高度|height)\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?.{0,12}?(?:中心)?(?:圆柱)?凸台.{0,12}?(?:直径(?:为)?|[ØøΦφ⌀])\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?",
    )
    for index, pattern in enumerate(pair_patterns):
        match = re.search(pattern, prompt, re.IGNORECASE)
        if not match:
            continue
        try:
            first = float(match.group(1))
            second = float(match.group(2))
        except ValueError:
            continue
        if index == 2:
            result["height"] = first
            result["diameter"] = second
        else:
            result["diameter"] = first
            result["height"] = second
        return result

    diameter_patterns = (
        r"(?:直径(?:为)?|[ØøΦφ⌀])\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?.{0,12}?(?:中心)?(?:圆柱)?凸台",
        r"(?:中心)?(?:圆柱)?凸台.{0,16}?(?:直径(?:为)?|[ØøΦφ⌀])\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?",
    )
    for pattern in diameter_patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if value > 0:
            result["diameter"] = value
            break

    height_patterns = (
        r"(?:中心)?(?:圆柱)?凸台.{0,16}?(?:高|高度|height)\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?",
        r"(?:高|高度|height)\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?.{0,12}?(?:中心)?(?:圆柱)?凸台",
    )
    for pattern in height_patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if value > 0:
            result["height"] = value
            break
    return result


def _infer_center_hole_diameter_from_prompt(prompt: str) -> float | None:
    if not isinstance(prompt, str):
        return None

    patterns = (
        r"(?:凸台中心开|中心开|中心打孔).{0,12}?(?:直径(?:为)?|[ØøΦφ⌀])\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?.{0,12}?(?:通孔|贯穿孔|孔)?",
        r"(?:凸台中心开|中心开|中心打孔).{0,12}?(\d+(?:\.\d+)?)\s*(?:mm|毫米)?.{0,12}?(?:通孔|贯穿孔|孔)",
        r"(?:中心孔|center hole).{0,12}?(?:直径(?:为)?|[ØøΦφ⌀])\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?",
        r"(?:中心孔|center hole).{0,12}?(\d+(?:\.\d+)?)\s*(?:mm|毫米)?",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if value > 0:
            return value
    return None


def _infer_explicit_pocket_dimensions_from_prompt(prompt: str) -> dict[str, float]:
    if not isinstance(prompt, str):
        return {}

    patterns = (
        r"(?:口袋|pocket).{0,20}?(\d+(?:\.\d+)?)\s*(?:mm|毫米)?\s*[*xX×]\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?\s*[*xX×]\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?",
        r"(\d+(?:\.\d+)?)\s*(?:mm|毫米)?\s*[*xX×]\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?\s*[*xX×]\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?.{0,16}?(?:口袋|pocket)",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if not match:
            continue
        try:
            length = float(match.group(1))
            width = float(match.group(2))
            depth = float(match.group(3))
        except ValueError:
            continue
        if length > 0 and width > 0 and depth > 0:
            return {"length": length, "width": width, "depth": depth}
    return {}


def _infer_explicit_corner_hole_diameter_from_prompt(prompt: str) -> float | None:
    if not isinstance(prompt, str):
        return None

    corner_markers = ("四角", "角上", "角孔", "corners", "corner")
    lowered = prompt.lower()
    for marker in corner_markers:
        search_text = lowered if marker.isascii() else prompt
        index = search_text.find(marker)
        if index < 0:
            continue
        window = prompt[index:index + 48]
        match = re.search(r"(\d+(?:\.\d+)?)\s*mm", window, re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if value > 0:
            return value
    return None

def _infer_base_size_from_operations(operations: list[Any]) -> tuple[float, float] | None:
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        if str(operation.get("op", "")).strip() != "create_base_plate":
            continue
        params = operation.get("params") if isinstance(operation.get("params"), dict) else {}
        length = _coerce_float(params.get("length"))
        width = _coerce_float(params.get("width"))
        if length is not None and width is not None and length > 0 and width > 0:
            return length, width

    sketch_names: set[str] = set()
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        if str(operation.get("op", "")).strip() != "create_sketch":
            continue
        params = operation.get("params") if isinstance(operation.get("params"), dict) else {}
        name = str(params.get("name", "")).strip()
        if name:
            sketch_names.add(name)

    for operation in operations:
        if not isinstance(operation, dict):
            continue
        if str(operation.get("op", "")).strip() != "sketch_center_rectangle":
            continue
        params = operation.get("params") if isinstance(operation.get("params"), dict) else {}
        sketch_name = str(params.get("sketch", "")).strip()
        length = _coerce_float(params.get("length"))
        width = _coerce_float(params.get("width"))
        if length is None or width is None or length <= 0 or width <= 0:
            continue
        if not sketch_name or sketch_name in sketch_names:
            return length, width

    return None


def _infer_uniform_side_edge_distance(prompt: str) -> float | None:
    if not isinstance(prompt, str):
        return None

    markers = (
        "距离两边",
        "距两侧",
        "距左右边",
        "距侧边",
        "from both side edges",
        "from both sides",
        "from left and right edges",
        "from side edges",
    )
    for marker in markers:
        index = prompt.find(marker)
        if index < 0:
            continue
        window = prompt[index + len(marker): index + len(marker) + 24]
        match = re.search(r"\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?", window, re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if value > 0:
            return value
    return None



def _infer_operation_host(
    prompt: str,
    operation_id: str,
    op_name: str,
    params: dict[str, Any],
) -> str | None:
    if not isinstance(prompt, str):
        return None

    plane = str(params.get("plane", "") or "").strip()
    if plane and plane != "top_face":
        return None

    lowered = prompt.lower()
    operation_id_lower = str(operation_id or "").lower()
    if op_name == "create_center_boss":
        return "base"

    boss_surface_markers = ("凸台上表面", "boss top face", "boss upper face", "top surface of the boss")
    base_surface_markers = (
        "安装板上表面",
        "底板上表面",
        "基板上表面",
        "plate top face",
        "base top face",
        "top surface of the plate",
        "top surface of the base",
    )

    if op_name in {"cut_slot", "cut_rectangle_pocket"}:
        if any(marker in prompt or marker in lowered for marker in boss_surface_markers):
            return "boss"
        if any(marker in prompt or marker in lowered for marker in base_surface_markers):
            return "base"
        if "上表面" in prompt or "top surface" in lowered or "top face" in lowered:
            return "base"
        return "base"

    if op_name in {"create_through_hole", "create_blind_hole", "create_counterbore_hole", "create_countersink_hole"}:
        if any(marker in prompt or marker in lowered for marker in boss_surface_markers):
            return "boss"
        if any(marker in prompt or marker in lowered for marker in base_surface_markers):
            return "base"
        return "base"

    if op_name == "create_sketch":
        if any(marker in prompt or marker in lowered for marker in boss_surface_markers) and "boss" in operation_id_lower:
            return "boss"
        return "base"

    return None
def _infer_slot_direction_from_prompt(prompt: str) -> str | None:
    if not isinstance(prompt, str):
        return None
    lowered = prompt.lower()
    if any(hint in prompt for hint in SLOT_DIRECTION_HINTS_Y if not hint.isascii()) or any(
        hint in lowered for hint in SLOT_DIRECTION_HINTS_Y if hint.isascii()
    ):
        return "y"
    if any(hint in prompt for hint in SLOT_DIRECTION_HINTS_X if not hint.isascii()) or any(
        hint in lowered for hint in SLOT_DIRECTION_HINTS_X if hint.isascii()
    ):
        return "x"
    return None


def _infer_slot_direction_from_geometry(
    params: dict[str, Any],
    base_size: tuple[float, float] | None,
) -> str | None:
    if base_size is None:
        return None
    length = _coerce_float(params.get("length"))
    width = _coerce_float(params.get("width"))
    if length is None or width is None or length <= 0 or width <= 0:
        return None
    base_length, base_width = base_size
    if abs(length - base_width) <= max(1.0, width) and length < base_length:
        return "y"
    if abs(length - base_length) <= max(1.0, width) and length < base_width:
        return "x"
    return None


def _normalize_edge_distance_slot_center(
    prompt: str,
    operation_id: str,
    params: dict[str, Any],
    base_size: tuple[float, float] | None,
    slot_index: int | None = None,
    slot_total: int = 0,
) -> list[float] | None:
    if base_size is None:
        return None
    side_distance = _infer_uniform_side_edge_distance(prompt)
    if side_distance is None:
        return None

    base_length, base_width = base_size
    direction = str(params.get("direction", "x") or "x").strip().lower()
    operation_id_lower = str(operation_id or "").lower()
    side = None
    if "left" in operation_id_lower:
        side = "left"
    elif "right" in operation_id_lower:
        side = "right"
    elif slot_total == 2:
        side = "left" if slot_index == 0 else "right"

    if side is None:
        return None

    current_center = _coerce_xy(params.get("center"))
    slot_width = _coerce_float(params.get("width"))
    half_slot_width = slot_width / 2 if slot_width is not None and slot_width > 0 else 0.0

    if direction == "y":
        x = -base_length / 2 + side_distance + half_slot_width if side == "left" else base_length / 2 - side_distance - half_slot_width
        # For side-edge slot intent, a current y sitting on the boundary usually means
        # the model used a top-left style absolute coordinate system. Normalize back to
        # the centered base frame unless the user explicitly gave another y coordinate.
        if current_center is not None and abs(float(current_center[1])) < (base_width / 2 - 1e-6):
            y = float(current_center[1])
        else:
            y = 0.0
        return [x, y]

    y = -base_width / 2 + side_distance + half_slot_width if side == "left" else base_width / 2 - side_distance - half_slot_width
    if current_center is not None and abs(float(current_center[0])) < (base_length / 2 - 1e-6):
        x = float(current_center[0])
    else:
        x = 0.0
    return [x, y]


def _infer_edge_distance_after_markers(prompt: str, markers: tuple[str, ...]) -> float | None:
    if not isinstance(prompt, str):
        return None
    lowered = prompt.lower()
    for marker in markers:
        search_text = lowered if marker.isascii() else prompt
        marker_text = marker.lower() if marker.isascii() else marker
        index = search_text.find(marker_text)
        if index < 0:
            continue
        window = prompt[index + len(marker): index + len(marker) + 24]
        match = re.search(r"\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?", window, re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if value >= 0:
            return value
    return None


def _prompt_implies_two_side_slots(prompt: str) -> bool:
    if not isinstance(prompt, str):
        return False
    lowered = prompt.lower()
    return (
        ("两侧各一个" in prompt or "左右各一个" in prompt or "两边各一个" in prompt or "each side" in lowered or "both sides" in lowered)
        and ("通槽" in prompt or "槽" in prompt or "slot" in lowered)
    )


def _normalize_pocket_center_from_prompt(
    prompt: str,
    params: dict[str, Any],
    base_size: tuple[float, float] | None,
    operation_id: str = "",
    pocket_index: int | None = None,
    pocket_total: int = 0,
) -> list[float] | None:
    if base_size is None or not isinstance(prompt, str):
        return None
    center = _coerce_xy(params.get("center"))
    if center is None:
        center = (0.0, 0.0)
    x, y = center
    base_length, base_width = base_size

    if re.search("(\u957f\u8fb9\u65b9\u5411.*\u4e2d\u5fc3\u4f4d\u7f6e|\u6cbf\u957f\u8fb9\u65b9\u5411.*\u4e2d\u5fc3\u4f4d\u7f6e|\u957f\u5ea6\u65b9\u5411.*\u4e2d\u5fc3\u4f4d\u7f6e)", prompt):
        x = 0.0
        if abs(y) < 1e-9:
            y = base_width / 2
    if re.search("(\u77ed\u8fb9\u65b9\u5411.*\u4e2d\u5fc3\u4f4d\u7f6e|\u6cbf\u77ed\u8fb9\u65b9\u5411.*\u4e2d\u5fc3\u4f4d\u7f6e|\u5bbd\u5ea6\u65b9\u5411.*\u4e2d\u5fc3\u4f4d\u7f6e)", prompt):
        y = 0.0

    pocket_length = _coerce_float(params.get("length"))
    pocket_width = _coerce_float(params.get("width"))
    if pocket_length is None or pocket_width is None or pocket_length <= 0 or pocket_width <= 0:
        return [x, y]

    if _prompt_requests_two_side_pockets(prompt):
        edge_distance = _infer_pocket_edge_distance(prompt) or 0.0
        edge_family = _infer_pocket_edge_family(prompt)
        if edge_family == "short" and pocket_total >= 1:
            offset = max(0.0, base_length / 2 - pocket_length / 2 - edge_distance)
            side = _infer_symmetric_side_from_id(operation_id, pocket_index, pocket_total)
            if side == "left":
                x = -offset
                y = 0.0
            elif side == "right":
                x = offset
                y = 0.0
        elif edge_family == "long" and pocket_total >= 1:
            offset = max(0.0, base_width / 2 - pocket_width / 2 - edge_distance)
            side = _infer_symmetric_side_from_id(operation_id, pocket_index, pocket_total)
            if side == "left":
                x = 0.0
                y = -offset
            elif side == "right":
                x = 0.0
                y = offset

    max_x = max(0.0, base_length / 2 - pocket_length / 2)
    max_y = max(0.0, base_width / 2 - pocket_width / 2)
    x = min(max(x, -max_x), max_x)
    y = min(max(y, -max_y), max_y)
    return [x, y]


def _prompt_requests_two_side_pockets(prompt: str) -> bool:
    if not isinstance(prompt, str):
        return False
    lowered = prompt.lower()
    return (
        "两侧各一个" in prompt
        or "左右各一个" in prompt
        or "两边各一个" in prompt
        or "两侧各开一个" in prompt
        or "one on each side" in lowered
        or "one on both sides" in lowered
        or ("two pockets" in lowered and "side" in lowered)
    )


def _infer_pocket_edge_family(prompt: str) -> str | None:
    if not isinstance(prompt, str):
        return None
    lowered = prompt.lower()
    if "短边中心" in prompt or "短边方向" in prompt or "short edge" in lowered:
        return "short"
    if "长边中心" in prompt or "长边方向" in prompt or "long edge" in lowered:
        return "long"
    return None


def _infer_pocket_edge_distance(prompt: str) -> float | None:
    return _infer_edge_distance_after_markers(
        prompt,
        ("距离边", "距边", "from edge", "from the edge"),
    )


def _infer_symmetric_side_from_id(operation_id: str, index: int | None, total: int) -> str | None:
    op_id = str(operation_id or "").lower()
    if "left" in op_id:
        return "left"
    if "right" in op_id:
        return "right"
    if total == 2 and index is not None:
        return "left" if index == 0 else "right"
    return None


def _normalize_hole_center(
    prompt: str,
    params: dict[str, Any],
    base_size: tuple[float, float] | None,
) -> list[float] | None:
    """Normalize a through/blind hole center into the centered base frame.

    Deterministic repair (no LLM): converts an edge-distance intent into a
    concrete center coordinate and clamps any center that would push the hole
    outside the base boundary back to the nearest safe position, so the Policy
    Engine boundary check can pass. Returns the normalized center, or None when
    there is nothing to fix.
    """

    if base_size is None:
        return None
    center = _coerce_xy(params.get("center"))
    if center is None:
        return None

    x, y = float(center[0]), float(center[1])
    base_length, base_width = base_size
    diameter = _coerce_float(params.get("diameter"))
    if diameter is None:
        diameter = _coerce_float(params.get("hole_diameter"))
    radius = diameter / 2 if diameter is not None and diameter > 0 else 0.0

    # Edge-distance intent: convert "<n>mm from the <side> edge" into a concrete
    # inward center coordinate. The distance is measured to the hole center, so no
    # radius offset is added here (radius only matters for the boundary clamp).
    side, edge_distance = _infer_hole_edge_distance(prompt)
    if edge_distance is not None:
        if side == "left":
            x = -base_length / 2 + edge_distance
        elif side == "right":
            x = base_length / 2 - edge_distance
        elif side == "front":
            y = -base_width / 2 + edge_distance
        elif side == "back":
            y = base_width / 2 - edge_distance
        elif abs(abs(x) - base_length / 2) < 1e-6:
            # Unknown side but center sits on a length boundary: pull it inward.
            x = base_length / 2 - edge_distance if x >= 0 else -base_length / 2 + edge_distance
        elif abs(abs(y) - base_width / 2) < 1e-6:
            y = base_width / 2 - edge_distance if y >= 0 else -base_width / 2 + edge_distance

    # Clamp so hole (center +/- radius) stays fully inside the base boundary.
    max_x = max(0.0, base_length / 2 - radius)
    max_y = max(0.0, base_width / 2 - radius)
    x = min(max(x, -max_x), max_x)
    y = min(max(y, -max_y), max_y)
    return [x, y]


def _infer_hole_edge_distance(prompt: str) -> tuple[str | None, float | None]:
    """Parse a "<n>mm from the <side> edge" (or 距/离<side>边<n>) intent.

    Returns (side, distance) where side is one of left/right/front/back or None
    when the side cannot be determined, and distance is the numeric edge offset.
    """

    if not isinstance(prompt, str):
        return (None, None)
    lowered = prompt.lower()

    # English: "20mm from the left edge" / "20 mm from left edge"
    en = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*from\s+(?:the\s+)?(left|right|front|back|top|bottom)\s+edge",
        lowered,
    )
    if en:
        side_map = {"left": "left", "right": "right", "front": "front", "back": "back", "top": "back", "bottom": "front"}
        return (side_map.get(en.group(2)), float(en.group(1)))

    # Chinese: 距左边20 / 离右边15mm / 距边20 (no side)
    zh = re.search(r"(?:距|离)\s*([左右前后])?\s*边\s*(\d+(?:\.\d+)?)", prompt)
    if zh:
        side_map = {"左": "left", "右": "right", "前": "front", "后": "back"}
        side = side_map.get(zh.group(1)) if zh.group(1) else None
        return (side, float(zh.group(2)))

    # Fallback: generic edge-distance marker without side info.
    generic = _infer_edge_distance_after_markers(
        prompt,
        ("from edge", "from the edge", "距离边", "距边", "边距"),
    )
    return (None, generic)


def _expand_symmetric_pockets(
    prompt: str,
    operations: list[dict[str, Any]],
    base_size: tuple[float, float] | None,
) -> list[dict[str, Any]]:
    if base_size is None or not _prompt_requests_two_side_pockets(prompt):
        return operations

    pocket_indices = [
        index
        for index, operation in enumerate(operations)
        if isinstance(operation, dict) and str(operation.get("op", "")).strip() == "cut_rectangle_pocket"
    ]
    if len(pocket_indices) != 1:
        return operations

    pocket_index = pocket_indices[0]
    original = operations[pocket_index]
    params = dict(original.get("params") or {})
    edge_family = _infer_pocket_edge_family(prompt)
    if edge_family not in {"short", "long"}:
        return operations

    center_left = _normalize_pocket_center_from_prompt(
        prompt,
        params,
        base_size,
        operation_id=str(original.get("id", "")),
        pocket_index=0,
        pocket_total=2,
    )
    center_right = _normalize_pocket_center_from_prompt(
        prompt,
        params,
        base_size,
        operation_id=f"{original.get('id', '')}_mirror",
        pocket_index=1,
        pocket_total=2,
    )
    if center_left is None or center_right is None or center_left == center_right:
        return operations

    existing_ids = {
        str(operation.get("id", "")).strip()
        for operation in operations
        if isinstance(operation, dict)
    }
    clone_id_base = f"{str(original.get('id', '')).strip() or 'pocket'}_002"
    clone_id = clone_id_base
    suffix = 2
    while clone_id in existing_ids:
        suffix += 1
        clone_id = f"{clone_id_base}_{suffix}"

    updated_original = {**original, "params": {**params, "center": center_left}}
    cloned_operation = {
        **original,
        "id": clone_id,
        "params": {**params, "center": center_right},
    }
    expanded = list(operations)
    expanded[pocket_index] = updated_original
    expanded.insert(pocket_index + 1, cloned_operation)
    return expanded


def _infer_metric_clearance_from_prompt(prompt: str, op_name: str = "") -> float | None:
    if not isinstance(prompt, str):
        return None
    lowered = prompt.lower()
    metric_hole_context = re.search(r"(通孔|孔|bolt hole|clearance hole|\\bhole\\b|\\bholes\\b)", prompt, re.IGNORECASE) is not None
    corner_hole_context = (
        op_name == "cut_corner_holes"
        and metric_hole_context
        and (
            "四角" in prompt
            or "角孔" in prompt
            or "角上" in prompt
            or "corners" in lowered
            or "corner" in lowered
        )
    )
    if not metric_hole_context and not corner_hole_context:
        return None
    match = re.search(r"(?<![A-Za-z0-9])M\s*(\d+(?:\.\d+)?)", prompt, re.IGNORECASE)
    if not match:
        return None
    try:
        nominal = float(match.group(1))
    except ValueError:
        return None
    return METRIC_CLEARANCE_MM.get(nominal)


def _coerce_xy(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None



def canonicalize_featureplan_structure(plan_data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan_data, dict):
        return plan_data

    normalized = dict(plan_data)
    operations = normalized.get("operations")
    if not isinstance(operations, list):
        return normalized

    normalized["operations"] = _prune_duplicate_base_construction(operations)
    return normalized


def _prune_duplicate_base_construction(operations: list[Any]) -> list[Any]:
    base_plate = None
    by_id: dict[str, dict[str, Any]] = {}
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op_id = str(operation.get("id", "")).strip()
        if op_id:
            by_id[op_id] = operation
        if operation.get("op") == "create_base_plate" and base_plate is None:
            base_plate = operation

    if base_plate is None:
        return operations

    base_params = base_plate.get("params", {}) if isinstance(base_plate.get("params"), dict) else {}
    base_length = _coerce_float(base_params.get("length"))
    base_width = _coerce_float(base_params.get("width"))
    base_thickness = _coerce_float(base_params.get("thickness"))
    if not all(value and value > 0 for value in (base_length, base_width, base_thickness)):
        return operations

    removable_ids: set[str] = set()
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") != "extrude_boss":
            continue
        params = operation.get("params", {}) if isinstance(operation.get("params"), dict) else {}
        direction = str(params.get("direction", "one_side") or "one_side").strip()
        if direction not in {"", "one_side"}:
            continue
        depth = _coerce_float(params.get("depth"))
        sketch_name = str(params.get("sketch", "")).strip()
        if depth is None or sketch_name == "" or abs(depth - base_thickness) > 1e-9:
            continue

        sketch_operation = _find_create_sketch_for_name(operations, sketch_name)
        rectangle_operation = _find_latest_rectangle_for_sketch(operations, sketch_name)
        if sketch_operation is None or rectangle_operation is None:
            continue
        if not _matches_base_rectangle(rectangle_operation, base_length, base_width):
            continue
        if _has_external_dependencies(operations, {str(sketch_operation.get("id", "")), str(rectangle_operation.get("id", "")), str(operation.get("id", ""))}):
            continue

        removable_ids.update(
            op_id
            for op_id in (str(sketch_operation.get("id", "")), str(rectangle_operation.get("id", "")), str(operation.get("id", "")))
            if op_id
        )

    if not removable_ids:
        return operations

    pruned: list[Any] = []
    for operation in operations:
        if not isinstance(operation, dict):
            pruned.append(operation)
            continue
        op_id = str(operation.get("id", "")).strip()
        if op_id in removable_ids:
            continue
        updated = dict(operation)
        depends_on = updated.get("depends_on")
        if isinstance(depends_on, list):
            updated["depends_on"] = [dep for dep in depends_on if str(dep) not in removable_ids]
        pruned.append(updated)
    return pruned


def _find_create_sketch_for_name(operations: list[Any], sketch_name: str) -> dict[str, Any] | None:
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") != "create_sketch":
            continue
        params = operation.get("params", {}) if isinstance(operation.get("params"), dict) else {}
        if str(params.get("name", "")).strip() == sketch_name:
            return operation
    return None


def _find_latest_rectangle_for_sketch(operations: list[Any], sketch_name: str) -> dict[str, Any] | None:
    latest = None
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") != "sketch_center_rectangle":
            continue
        params = operation.get("params", {}) if isinstance(operation.get("params"), dict) else {}
        if str(params.get("sketch", "")).strip() == sketch_name:
            latest = operation
    return latest


def _matches_base_rectangle(operation: dict[str, Any], base_length: float, base_width: float) -> bool:
    params = operation.get("params", {}) if isinstance(operation.get("params"), dict) else {}
    center = params.get("center")
    xy = _coerce_xy(center)
    length = _coerce_float(params.get("length"))
    width = _coerce_float(params.get("width"))
    if xy is None or length is None or width is None:
        return False
    return abs(xy[0]) <= 1e-9 and abs(xy[1]) <= 1e-9 and abs(length - base_length) <= 1e-9 and abs(width - base_width) <= 1e-9


def _has_external_dependencies(operations: list[Any], removable_ids: set[str]) -> bool:
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op_id = str(operation.get("id", "")).strip()
        if op_id in removable_ids:
            continue
        depends_on = operation.get("depends_on")
        if isinstance(depends_on, list) and any(str(dep) in removable_ids for dep in depends_on):
            return True
        params = operation.get("params", {}) if isinstance(operation.get("params"), dict) else {}
        sketch_ref = str(params.get("sketch", "")).strip()
        if sketch_ref and any(
            isinstance(candidate, dict) and candidate.get("op") == "create_sketch" and str(candidate.get("params", {}).get("name", "")).strip() == sketch_ref and str(candidate.get("id", "")).strip() in removable_ids
            for candidate in operations
            if isinstance(candidate, dict)
        ):
            return True
    return False




def _prompt_requests_slot_through_thickness(prompt: str) -> bool:
    if not isinstance(prompt, str):
        return False
    lowered = prompt.lower()
    explicit_through_thickness_markers = (
        "贯穿板厚",
        "贯穿安装板",
        "贯穿底板",
        "切穿板厚",
        "through the plate thickness",
        "through the base thickness",
        "through the plate",
        "cut through the plate",
    )
    return any(marker in prompt or marker in lowered for marker in explicit_through_thickness_markers)


def _infer_base_thickness_from_operations(operations: list[Any]) -> float | None:
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        if str(operation.get("op", "")).strip() != "create_base_plate":
            continue
        params = operation.get("params") if isinstance(operation.get("params"), dict) else {}
        thickness = _coerce_float(params.get("thickness"))
        if thickness is not None and thickness > 0:
            return thickness
    return None


def _infer_default_slot_depth(params: dict[str, Any], base_thickness: float | None) -> float | None:
    if base_thickness is None or base_thickness <= 0:
        return None
    width = _coerce_float(params.get("width"))
    candidates = [base_thickness * 0.5, base_thickness - 1.0]
    if width is not None and width > 0:
        candidates.append(width)
    positive = [value for value in candidates if value > 0]
    if not positive:
        return None
    inferred = min(positive)
    return round(max(1.0, inferred), 3)

def _infer_default_corner_hole_edge_margin(
    params: dict[str, Any],
    base_size: tuple[float, float] | None,
) -> float | None:
    if base_size is None:
        return None
    diameter = _coerce_float(params.get("diameter"))
    if diameter is None or diameter <= 0:
        return None

    radius = diameter / 2
    half_length = base_size[0] / 2
    half_width = base_size[1] / 2
    max_margin = min(half_length, half_width) - radius
    if max_margin <= radius:
        return None

    recommended = max(radius + 5.0, diameter * 1.5)
    recommended = min(recommended, max_margin)
    if recommended <= radius:
        return None
    return round(recommended, 3)


