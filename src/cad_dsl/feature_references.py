"""Canonical handling for inter-operation feature references."""

from __future__ import annotations

from cad_dsl.featureplan import FeatureOperation


HOLE_OPS = {
    "create_through_hole",
    "create_blind_hole",
    "create_counterbore_hole",
    "create_countersink_hole",
}

PATTERNED_OPS = {
    "create_linear_pattern",
    "create_circular_pattern",
    "mirror_feature",
}


def normalize_feature_reference(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.endswith(".feature_id"):
        return text[: -len(".feature_id")]
    return text


def build_seed_feature_aliases(operations: list[FeatureOperation]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    hole_count = 0
    for operation in operations:
        aliases[operation.id] = operation.id
        aliases[normalize_feature_reference(operation.id)] = operation.id
        if operation.op in HOLE_OPS:
            hole_count += 1
            aliases[f"Hole{hole_count}"] = operation.id
    return aliases


def build_seed_feature_aliases_from_dicts(operations: list[dict]) -> dict[str, str]:
    adapted = [
        FeatureOperation(
            id=str(operation.get("id", "")),
            op=str(operation.get("op", "")),
            params=dict(operation.get("params") or {}),
            depends_on=tuple(str(dep) for dep in operation.get("depends_on", []) or []),
        )
        for operation in operations
        if isinstance(operation, dict)
    ]
    return build_seed_feature_aliases(adapted)


def resolve_seed_feature_reference(value: object, aliases: dict[str, str]) -> str:
    normalized = normalize_feature_reference(value)
    if not normalized:
        return ""
    return aliases.get(normalized, normalized)
