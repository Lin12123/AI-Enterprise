"""Stable execution planning for FeaturePlan operations."""

from __future__ import annotations

from collections import defaultdict

from cad_dsl.featureplan import FeatureOperation, FeaturePlan
from cad_dsl.feature_references import build_seed_feature_aliases, resolve_seed_feature_reference


OUTPUT_OPS = {"save_sldprt", "export_step", "capture_png"}
VALIDATION_OPS = {"rebuild_model", "validate_rebuild"}


def plan_operations(plan: FeaturePlan) -> FeaturePlan:
    """Return a FeaturePlan with operations ordered for fixed executor safety.

    This planner keeps FeaturePlan declarative while preventing common geometry
    dependency failures, such as cutting a boss hole before the boss exists.
    """

    operations = list(plan.operations)
    if not operations:
        return plan

    id_to_index = {operation.id: index for index, operation in enumerate(operations)}
    id_to_operation = {operation.id: operation for operation in operations}
    prerequisites: dict[str, set[str]] = {operation.id: set(operation.depends_on) for operation in operations}
    sketch_creators = _sketch_creator_ids(operations)
    sketch_latest_entities = _sketch_latest_entity_ids(operations)

    first_new_part = _first_id(operations, "create_new_part")
    first_base = _first_id(operations, "create_base_plate") or _first_base_extrude_id(operations)
    first_boss = _first_id(operations, "create_center_boss")
    seed_aliases = build_seed_feature_aliases(operations)

    # 增量模式：插件在“当前已打开的 SolidWorks 零件”上继续操作（例如仅在已有安装板
    # 上开槽/开孔）。此时 FeaturePlan 允许不包含创建底板的算子，规划阶段把当前零件视
    # 为隐式的已完成实体，从而放宽 solid-body 依赖算子对 base 的硬性校验（不 raise、
    # 也不为它们添加不存在的 base 依赖）。仅当计划本身没有任何底板算子时才生效。
    assume_existing_base = bool(getattr(plan.metadata, "assume_existing_base", False)) and not first_base

    for operation in operations:
        if operation.op != "create_new_part" and first_new_part:
            prerequisites[operation.id].add(first_new_part)

        if operation.op in {"sketch_center_rectangle", "sketch_circle"}:
            sketch_id = sketch_creators.get(str(operation.params.get("sketch", "")))
            if sketch_id:
                prerequisites[operation.id].add(sketch_id)

        if operation.op in {"extrude_boss", "extrude_cut"}:
            sketch_name = str(operation.params.get("sketch", ""))
            sketch_id = sketch_creators.get(sketch_name)
            entity_id = sketch_latest_entities.get(sketch_name)
            if sketch_id:
                prerequisites[operation.id].add(sketch_id)
            if entity_id:
                prerequisites[operation.id].add(entity_id)

        if operation.op in {"cut_corner_holes", "create_center_boss", "cut_center_hole"} and first_base:
            prerequisites[operation.id].add(first_base)

        if operation.op in _solid_body_dependent_ops() and not first_base:
            if not assume_existing_base:
                raise RuntimeError(f"{operation.op} requires a completed base solid before execution")

        if operation.op in _solid_body_dependent_ops() and first_base:
            prerequisites[operation.id].add(first_base)

        if operation.op == "cut_center_hole" and _center_hole_target(operation, first_boss) == "boss":
            if not first_boss:
                raise RuntimeError("Cannot plan cut_center_hole target=boss before any create_center_boss operation exists")
            prerequisites[operation.id].add(first_boss)

        if operation.op in {"create_linear_pattern", "create_circular_pattern", "mirror_feature"}:
            seed_id = resolve_seed_feature_reference(operation.params.get("seed_feature", ""), seed_aliases)
            if seed_id in id_to_operation:
                prerequisites[operation.id].add(seed_id)

        if operation.op in OUTPUT_OPS:
            for candidate in operations:
                if candidate.id != operation.id and candidate.op not in OUTPUT_OPS:
                    prerequisites[operation.id].add(candidate.id)

        if operation.op in VALIDATION_OPS:
            for candidate in operations:
                if candidate.id != operation.id and candidate.op not in OUTPUT_OPS and candidate.op not in VALIDATION_OPS:
                    prerequisites[operation.id].add(candidate.id)

    ordered = _stable_topological_sort(operations, prerequisites, id_to_index, id_to_operation)
    return FeaturePlan(
        version=plan.version,
        unit=plan.unit,
        document_type=plan.document_type,
        part_name=plan.part_name,
        operations=tuple(ordered),
        outputs=plan.outputs,
        metadata=plan.metadata,
    )


def _first_id(operations: list[FeatureOperation], operation_type: str) -> str:
    for operation in operations:
        if operation.op == operation_type:
            return operation.id
    return ""


def _first_base_extrude_id(operations: list[FeatureOperation]) -> str:
    sketch_rectangles: set[str] = set()
    for operation in operations:
        if operation.op == "sketch_center_rectangle":
            sketch_rectangles.add(str(operation.params.get("sketch", "")))
        if operation.op == "extrude_boss" and str(operation.params.get("sketch", "")) in sketch_rectangles:
            return operation.id
    return ""


def _sketch_creator_ids(operations: list[FeatureOperation]) -> dict[str, str]:
    creators: dict[str, str] = {}
    for operation in operations:
        if operation.op == "create_sketch":
            name = str(operation.params.get("name", ""))
            if name and name not in creators:
                creators[name] = operation.id
    return creators


def _sketch_latest_entity_ids(operations: list[FeatureOperation]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for operation in operations:
        if operation.op in {"sketch_center_rectangle", "sketch_circle"}:
            sketch = str(operation.params.get("sketch", ""))
            if sketch:
                latest[sketch] = operation.id
    return latest


def _center_hole_target(operation: FeatureOperation, first_boss: str) -> str:
    if "target" in operation.params:
        return str(operation.params.get("target", ""))
    return "boss" if first_boss else "base"


def _solid_body_dependent_ops() -> set[str]:
    return {
        "create_through_hole",
        "create_blind_hole",
        "create_counterbore_hole",
        "create_countersink_hole",
        "cut_corner_holes",
        "cut_center_hole",
        "cut_slot",
        "cut_rectangle_pocket",
        "extrude_cut",
        "add_fillet",
        "add_chamfer",
        "create_linear_pattern",
        "create_circular_pattern",
        "mirror_feature",
    }


def _stable_topological_sort(
    operations: list[FeatureOperation],
    prerequisites: dict[str, set[str]],
    id_to_index: dict[str, int],
    id_to_operation: dict[str, FeatureOperation],
) -> list[FeatureOperation]:
    remaining = {operation.id for operation in operations}
    dependents: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = {}

    for operation in operations:
        incoming[operation.id] = {item for item in prerequisites.get(operation.id, set()) if item in id_to_operation and item != operation.id}
        for prerequisite in incoming[operation.id]:
            dependents[prerequisite].add(operation.id)

    ready = sorted((operation_id for operation_id in remaining if not incoming[operation_id]), key=id_to_index.__getitem__)
    ordered_ids: list[str] = []

    while ready:
        operation_id = ready.pop(0)
        if operation_id not in remaining:
            continue
        remaining.remove(operation_id)
        ordered_ids.append(operation_id)

        for dependent_id in sorted(dependents.get(operation_id, set()), key=id_to_index.__getitem__):
            incoming[dependent_id].discard(operation_id)
            if not incoming[dependent_id] and dependent_id in remaining and dependent_id not in ready:
                ready.append(dependent_id)
        ready.sort(key=id_to_index.__getitem__)

    if remaining:
        unresolved = ", ".join(sorted(remaining, key=id_to_index.__getitem__))
        raise RuntimeError(f"Cannot plan FeaturePlan operation order due to cyclic or unresolved dependencies: {unresolved}")

    return [id_to_operation[operation_id] for operation_id in ordered_ids]
