"""Policy Engine for FeaturePlan v2."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from cad_dsl.feature_registry import FeatureRegistry, default_registry
from cad_dsl.feature_references import build_seed_feature_aliases, normalize_feature_reference, resolve_seed_feature_reference
from cad_dsl.featureplan import DEFAULT_UNIT, SUPPORTED_PLAN_VERSION, FeaturePlan
from cad_dsl.semantic_binding import canonicalize_featureplan_structure
from policy.file_safety_rules import validate_no_dangerous_fields, validate_outputs
from policy.geometry_rules import validate_feature_geometry


# 圆孔外缘与底板边界之间必须保留的最小材料余量(mm)。
# 当孔缘与底板边界相切(|coord|+radius == half)时，SOLIDWORKS FeatureCut3
# 会因退化/共边几何切除失败并返回 None(表现为 create_through_hole ... API returned None)。
# 因此边界校验必须比"严格超出"更保守：要求孔缘距边界至少留出该余量。
_EDGE_SAFETY_MARGIN_MM = 0.5


@dataclass(frozen=True)
class PolicyViolation:
    code: str
    message: str
    operation_id: str = ""


@dataclass(frozen=True)
class PolicyResult:
    allowed: bool
    violations: tuple[PolicyViolation, ...] = ()


class PolicyEngine:
    def __init__(self, registry: FeatureRegistry | None = None, allow_non_implemented: bool = False) -> None:
        self.registry = registry or default_registry()
        self.allow_non_implemented = allow_non_implemented

    def validate(self, plan_data: Mapping[str, Any] | FeaturePlan) -> PolicyResult:
        raw_source: Mapping[str, Any] | None = plan_data if isinstance(plan_data, Mapping) else None
        canonical_source = canonicalize_featureplan_structure(dict(plan_data)) if isinstance(plan_data, Mapping) else None
        plan = plan_data if isinstance(plan_data, FeaturePlan) else FeaturePlan.from_dict(canonical_source or plan_data)
        if canonical_source is not None:
            raw_source = canonical_source
        violations: list[PolicyViolation] = []

        if plan.version != SUPPORTED_PLAN_VERSION:
            violations.append(PolicyViolation("version", "FeaturePlan version 必须是 2.0"))
        if plan.unit != DEFAULT_UNIT:
            violations.append(PolicyViolation("unit", "FeaturePlan unit 只能是 mm"))
        if plan.document_type != "part":
            violations.append(PolicyViolation("document_type", "document_type 只能是 part"))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", plan.part_name):
            violations.append(PolicyViolation("part_name", "part_name 只能包含字母、数字、下划线和短横线，长度 1-80"))
        if not plan.operations:
            violations.append(PolicyViolation("operations", "FeaturePlan 至少需要一个 operation"))

        for message in validate_no_dangerous_fields(raw_source or plan.to_dict()):
            violations.append(PolicyViolation("file_safety", message))
        for message in validate_outputs(plan.outputs):
            violations.append(PolicyViolation("outputs", message))

        for message in _validate_pattern_seed_capabilities(plan):
            violations.append(PolicyViolation("geometry", message))

        seen_ids: set[str] = set()
        seen_reference_names: set[str] = set()
        sketch_rectangles: dict[str, tuple[float, float]] = {}
        base_size: tuple[float, float] | None = None
        metadata = raw_source.get("metadata", {}) if raw_source else {}
        inferred_parameters = set(_metadata_parameter_paths(metadata, "inferred_parameters", plan.metadata.inferred_parameters))
        explicit_parameters = set(_metadata_parameter_paths(metadata, "explicit_parameters", plan.metadata.explicit_parameters))
        for operation in plan.operations:
            if not operation.id:
                violations.append(PolicyViolation("operation_id", "每个 operation 必须有 id"))
            if operation.id in seen_ids:
                violations.append(PolicyViolation("operation_id", "operation id 必须唯一", operation.id))
            seen_ids.add(operation.id)

            definition = self.registry.get(operation.op)
            if definition is None:
                violations.append(PolicyViolation("registry", f"未知 op，Feature Registry 未登记: {operation.op}", operation.id))
                continue
            if definition.status != "implemented" and not self.allow_non_implemented:
                violations.append(
                    PolicyViolation(
                        "capability",
                        f"op 当前状态为 {definition.status}，未实现，不能执行: {operation.op}",
                        operation.id,
                    )
                )

            parameters = dict(operation.params)
            missing = [name for name in definition.required_parameters if name not in parameters]
            if operation.op == "set_material" and "material" in missing and "material_id" in parameters:
                missing.remove("material")
            for name in missing:
                violations.append(PolicyViolation("parameters", f"缺少必需参数: {name}", operation.id))

            extra = set(parameters) - definition.allowed_parameters
            for name in sorted(extra):
                violations.append(PolicyViolation("parameters", f"参数未在白名单中: {name}", operation.id))

            for message in validate_feature_geometry(operation.op, parameters):
                violations.append(PolicyViolation("geometry", message, operation.id))

            if operation.op == "sketch_center_rectangle":
                sketch_name = str(parameters.get("sketch", "")).strip()
                try:
                    length = float(parameters.get("length", 0))
                    width = float(parameters.get("width", 0))
                except (TypeError, ValueError):
                    length = 0
                    width = 0
                if sketch_name and length > 0 and width > 0:
                    sketch_rectangles[sketch_name] = (length, width)

            if operation.op == "create_base_plate":
                try:
                    base_size = (float(parameters.get("length", 0)), float(parameters.get("width", 0)))
                except (TypeError, ValueError):
                    base_size = None

            if operation.op == "extrude_boss" and base_size is None:
                sketch_name = str(parameters.get("sketch", "")).strip()
                if sketch_name in sketch_rectangles:
                    base_size = sketch_rectangles[sketch_name]

            for message in _validate_base_bounds(operation.op, operation.id, parameters, base_size, inferred_parameters, explicit_parameters):
                violations.append(PolicyViolation("geometry", message, operation.id))

            if operation.op in {"create_offset_plane", "create_axis"}:
                name = str(parameters.get("name", "")).strip()
                if name:
                    if name in seen_reference_names:
                        violations.append(PolicyViolation("geometry", f"{operation.op} name 必须唯一: {name}", operation.id))
                    seen_reference_names.add(name)

        for message in _validate_metadata_parameter_paths(plan, inferred_parameters, "inferred_parameters"):
            violations.append(PolicyViolation("metadata", message))
        for message in _validate_metadata_parameter_paths(plan, explicit_parameters, "explicit_parameters"):
            violations.append(PolicyViolation("metadata", message))

        return PolicyResult(allowed=not violations, violations=tuple(violations))


def _metadata_parameter_paths(metadata: Any, key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(metadata, Mapping):
        value = metadata.get(key)
        if isinstance(value, (list, tuple)):
            return tuple(str(item) for item in value)
    return fallback


def _validate_metadata_parameter_paths(plan: FeaturePlan, paths: set[str], field_name: str) -> list[str]:
    errors: list[str] = []
    operations = {operation.id: operation for operation in plan.operations}
    for path in sorted(paths):
        # Parameter paths have the form ``<operation_id>.params.<parameter>``.
        # The operation id itself may legitimately contain dots (local models
        # emit ids such as ``create_base_plate.001``), so a naive
        # ``split(".")`` would incorrectly count 4+ segments and reject valid
        # paths. Split on the ``.params.`` separator instead, keeping the
        # operation id (which may contain dots) intact.
        separator = ".params."
        marker = path.find(separator)
        if marker < 0:
            errors.append(f"metadata.{field_name} contains invalid parameter path: {path}")
            continue
        operation_id = path[:marker]
        parameter_name = path[marker + len(separator) :]
        if not operation_id or not parameter_name or "." in parameter_name:
            errors.append(f"metadata.{field_name} contains invalid parameter path: {path}")
            continue
        operation = operations.get(operation_id)
        if operation is None:
            errors.append(f"metadata.{field_name} references unknown operation id: {path}")
            continue
        if parameter_name not in operation.params:
            errors.append(f"metadata.{field_name} references missing operation parameter: {path}")
    return errors


def _validate_base_bounds(
    operation_type: str,
    operation_id: str,
    parameters: Mapping[str, Any],
    base_size: tuple[float, float] | None,
    inferred_parameters: set[str],
    explicit_parameters: set[str],
) -> list[str]:
    if base_size is None:
        return []

    errors: list[str] = []
    if operation_type in {"create_through_hole", "create_blind_hole"}:
        _validate_circular_center_inside_base(operation_type, operation_id, parameters, base_size, "diameter", inferred_parameters, explicit_parameters, errors)
    elif operation_type in {"create_counterbore_hole", "create_countersink_hole"}:
        _validate_circular_center_inside_base(operation_type, operation_id, parameters, base_size, "hole_diameter", inferred_parameters, explicit_parameters, errors)
    elif operation_type == "cut_corner_holes":
        _validate_corner_holes_inside_base(operation_id, parameters, base_size, inferred_parameters, explicit_parameters, errors)
    elif operation_type == "cut_slot":
        _validate_rectangular_cut_inside_base(operation_type, operation_id, parameters, base_size, inferred_parameters, explicit_parameters, errors)
    elif operation_type == "cut_rectangle_pocket":
        _validate_rectangular_cut_inside_base(operation_type, operation_id, parameters, base_size, inferred_parameters, explicit_parameters, errors)
    return errors


def _validate_circular_center_inside_base(
    operation_type: str,
    operation_id: str,
    parameters: Mapping[str, Any],
    base_size: tuple[float, float],
    diameter_name: str,
    inferred_parameters: set[str],
    explicit_parameters: set[str],
    errors: list[str],
) -> None:
    center = parameters.get("center")
    if not isinstance(center, (list, tuple)) or len(center) != 2:
        return
    try:
        x = float(center[0])
        y = float(center[1])
        diameter = float(parameters.get(diameter_name, 0))
    except (TypeError, ValueError):
        return
    if diameter <= 0:
        return
    half_length = base_size[0] / 2
    half_width = base_size[1] / 2
    radius = diameter / 2
    # 使用 >= 并预留安全余量：孔缘与底板边界相切(|coord|+radius == half)时
    # SOLIDWORKS 会切除失败返回 None，因此相切或几乎相切都必须拦下要求 re-recommend。
    if (
        abs(x) + radius >= half_length - _EDGE_SAFETY_MARGIN_MM
        or abs(y) + radius >= half_width - _EDGE_SAFETY_MARGIN_MM
    ):
        errors.append(_boundary_message(operation_type, operation_id, "center", inferred_parameters, explicit_parameters))



def _validate_corner_holes_inside_base(
    operation_id: str,
    parameters: Mapping[str, Any],
    base_size: tuple[float, float],
    inferred_parameters: set[str],
    explicit_parameters: set[str],
    errors: list[str],
) -> None:
    try:
        diameter = float(parameters.get("diameter", 0))
    except (TypeError, ValueError):
        return
    if diameter <= 0:
        return

    half_length = base_size[0] / 2
    half_width = base_size[1] / 2
    radius = diameter / 2

    if "edge_margin" in parameters:
        try:
            margin = float(parameters.get("edge_margin", 0))
        except (TypeError, ValueError):
            return
        if margin <= radius or margin >= half_length or margin >= half_width:
            errors.append(_boundary_message("cut_corner_holes", operation_id, "edge_margin", inferred_parameters, explicit_parameters))
        return

    if "offset_x" not in parameters or "offset_y" not in parameters:
        return

    try:
        offset_x = float(parameters.get("offset_x", 0))
        offset_y = float(parameters.get("offset_y", 0))
    except (TypeError, ValueError):
        return

    if offset_x <= 0 or offset_y <= 0:
        return

    if offset_x + radius > half_length:
        errors.append(_boundary_message("cut_corner_holes", operation_id, "offset_x", inferred_parameters, explicit_parameters))
    if offset_y + radius > half_width:
        errors.append(_boundary_message("cut_corner_holes", operation_id, "offset_y", inferred_parameters, explicit_parameters))
def _validate_rectangular_cut_inside_base(
    operation_type: str,
    operation_id: str,
    parameters: Mapping[str, Any],
    base_size: tuple[float, float],
    inferred_parameters: set[str],
    explicit_parameters: set[str],
    errors: list[str],
) -> None:
    center = parameters.get("center")
    if not isinstance(center, (list, tuple)) or len(center) != 2:
        return
    try:
        x = float(center[0])
        y = float(center[1])
        length = float(parameters.get("length", 0))
        width = float(parameters.get("width", 0))
    except (TypeError, ValueError):
        return
    if length <= 0 or width <= 0:
        return
    direction = str(parameters.get("direction", "x")).strip().lower()
    if operation_type == "cut_slot" and direction == "y":
        extent_x = width
        extent_y = length
    else:
        extent_x = length
        extent_y = width
    half_length = base_size[0] / 2
    half_width = base_size[1] / 2
    exceeds_x = abs(x) + extent_x / 2 > half_length
    exceeds_y = abs(y) + extent_y / 2 > half_width
    if not exceeds_x and not exceeds_y:
        return

    if extent_x > base_size[0]:
        errors.append(_boundary_message(operation_type, operation_id, "length", inferred_parameters, explicit_parameters))
        return
    if extent_y > base_size[1]:
        errors.append(_boundary_message(operation_type, operation_id, "width", inferred_parameters, explicit_parameters))
        return

    errors.append(_boundary_message(operation_type, operation_id, "center", inferred_parameters, explicit_parameters))


def _boundary_message(
    operation_type: str,
    operation_id: str,
    parameter: str,
    inferred_parameters: set[str],
    explicit_parameters: set[str],
) -> str:
    path = f"{operation_id}.params.{parameter}"
    base = (
        f"{operation_type} {parameter} is outside the current base boundary. "
        "For edge-distance intent, center must include the inward offset from the edge."
    )
    if path in inferred_parameters:
        return base + f" Inferred parameter {path} must be re-recommended by the LLM."
    if path in explicit_parameters:
        return base + f" Explicit user parameter {path} exceeds the model boundary and requires user confirmation."
    return base + f" Parameter {path} is missing source provenance; mark it as inferred or explicit before execution."



def _validate_pattern_seed_capabilities(plan: FeaturePlan) -> list[str]:
    operations = list(plan.operations)
    aliases = build_seed_feature_aliases(operations)
    by_id = {operation.id: operation for operation in operations}
    errors: list[str] = []

    for operation in operations:
        if operation.op not in {"create_linear_pattern", "create_circular_pattern"}:
            continue
        raw_seed = operation.params.get("seed_feature", "")
        normalized_seed = normalize_feature_reference(raw_seed)
        resolved_seed = resolve_seed_feature_reference(normalized_seed, aliases)
        seed_operation = by_id.get(resolved_seed)
        if seed_operation is None:
            continue
        if seed_operation.op == "cut_center_hole":
            errors.append(
                f"{operation.op} seed_feature 引用了 cut_center_hole: {raw_seed}。"
                "cut_center_hole 只能表达受控的中心孔能力；"
                "请改为 create_through_hole/create_blind_hole，并提供明确的 center。"
            )
    return errors
