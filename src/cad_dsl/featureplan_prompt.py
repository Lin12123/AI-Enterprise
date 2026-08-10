"""Build registry-driven instructions for natural language -> FeaturePlan v2."""

from __future__ import annotations

from functools import lru_cache

from cad_dsl.feature_registry import FeatureRegistry, default_registry
from cad_dsl.material_catalog import prompt_material_lines
from policy.policy_prompt import build_policy_prompt_summary


FOUNDATION_OPS = {
    "create_new_part",
    "create_sketch",
    "sketch_center_rectangle",
    "extrude_boss",
    "create_base_plate",
    "save_sldprt",
    "export_step",
    "capture_png",
    "rebuild_model",
    "validate_rebuild",
}

PROMPT_OPERATION_HINTS = {
    "create_base_plate": ("板", "底板", "plate", "base plate", "安装板"),
    "create_through_hole": ("孔", "通孔", "hole"),
    "create_blind_hole": ("盲孔", "blind hole"),
    "cut_corner_holes": ("四角", "角孔", "螺栓孔", "螺丝孔", "corner hole", "bolt hole"),
    "create_center_boss": ("凸台", "boss", "平台", "圆形凸起"),
    "cut_center_hole": ("中心孔", "通孔", "boss center hole", "凸台中心"),
    "add_fillet": ("圆角", "倒圆", "fillet", "round", "r角", "r2", "r3"),
    "add_chamfer": ("倒角", "chamfer", "c1", "c2", "c3"),
    "cut_slot": ("槽", "slot", "通槽"),
    "cut_rectangle_pocket": ("口袋", "pocket", "凹槽"),
    "create_linear_pattern": ("阵列", "线性阵列", "linear pattern"),
    "create_circular_pattern": ("圆周阵列", "circular pattern"),
    "mirror_feature": ("镜像", "mirror"),
    "set_material": ("材料", "material", "6061", "304", "steel", "aluminum", "aluminium"),
    "set_custom_property": ("零件编号", "零件号", "料号", "part number", "description", "描述", "说明"),
    "modify_named_dimension": ("修改尺寸", "改尺寸", "dimension"),
    "create_offset_plane": ("基准面", "offset plane"),
    "create_axis": ("基准轴", "axis"),
}

OUTPUT_HINTS = ("保存", "导出", "截图", "step", "sldprt", "png", "save", "export", "capture")
MATERIAL_HINTS = PROMPT_OPERATION_HINTS["set_material"]


def build_featureplan_prompt(
    registry: FeatureRegistry | None = None,
    compact: bool = False,
    include_blocked: bool = True,
    include_materials: bool = True,
) -> str:
    """Return LLM instructions generated from the current Feature Registry.

    Adding a new implemented operation to the registry automatically exposes it
    to the natural-language FeaturePlan parser prompt.
    """

    if registry is None and compact and include_blocked:
        return _build_default_compact_featureplan_prompt()
    if registry is None and include_blocked:
        return _build_default_featureplan_prompt()
    return _build_featureplan_prompt(
        registry or default_registry(),
        compact=compact,
        include_blocked=include_blocked,
        include_materials=include_materials,
        op_filter=None,
    )


def build_featureplan_prompt_for_request(
    prompt: str,
    registry: FeatureRegistry | None = None,
    compact: bool = True,
    include_blocked: bool = False,
) -> str:
    registry = registry or default_registry()
    relevant_ops = select_relevant_operations(prompt, registry)
    include_materials = prompt_mentions_any(prompt, MATERIAL_HINTS)
    return _build_featureplan_prompt(
        registry,
        compact=compact,
        include_blocked=include_blocked,
        include_materials=include_materials,
        op_filter=relevant_ops,
    )


@lru_cache(maxsize=1)
def _build_default_featureplan_prompt() -> str:
    return _build_featureplan_prompt(default_registry())


@lru_cache(maxsize=1)
def _build_default_compact_featureplan_prompt() -> str:
    return _build_featureplan_prompt(default_registry(), compact=True)


def select_relevant_operations(prompt: str, registry: FeatureRegistry | None = None) -> frozenset[str] | None:
    registry = registry or default_registry()
    lowered = str(prompt).lower()
    selected = set(FOUNDATION_OPS)
    matched_any = False

    for op, hints in PROMPT_OPERATION_HINTS.items():
        if prompt_mentions_any(prompt, hints, lowered=lowered):
            selected.add(op)
            matched_any = True

    if prompt_mentions_any(prompt, OUTPUT_HINTS, lowered=lowered):
        selected.update({"save_sldprt", "export_step", "capture_png"})
        matched_any = True

    if "create_linear_pattern" in selected or "create_circular_pattern" in selected or "mirror_feature" in selected:
        selected.update({"create_through_hole", "create_blind_hole", "cut_slot", "cut_rectangle_pocket"})

    if "cut_center_hole" in selected:
        selected.add("create_center_boss")

    selected = {op for op in selected if registry.get(op) is not None and registry.require(op).status == "implemented"}
    return frozenset(selected) if matched_any else None


def prompt_mentions_any(prompt: str, hints: tuple[str, ...], lowered: str | None = None) -> bool:
    lowered = lowered if lowered is not None else str(prompt).lower()
    return any(hint in prompt for hint in hints if not hint.isascii()) or any(
        hint in lowered for hint in hints if hint.isascii()
    )


def _build_featureplan_prompt(
    registry: FeatureRegistry,
    compact: bool = False,
    include_blocked: bool = True,
    include_materials: bool = True,
    op_filter: frozenset[str] | None = None,
) -> str:
    implemented = []
    blocked = []
    for op in sorted(registry.allowed_types()):
        if op_filter is not None and op not in op_filter:
            continue
        definition = registry.require(op)
        required = ", ".join(definition.required_parameters) or "none"
        optional = ", ".join(sorted(definition.allowed_parameters - set(definition.required_parameters))) or "none"
        if compact:
            line = f"- {definition.op}: status={definition.status}; required=[{required}]; optional=[{optional}]"
        else:
            limitations = "; ".join(definition.limitations) or "none"
            line = (
                f"- {definition.op}: status={definition.status}; "
                f"required=[{required}]; optional=[{optional}]; "
                f"executor={definition.executor_function or 'TODO'}; limitations={limitations}"
            )
        if definition.status == "implemented":
            implemented.append(line)
        elif include_blocked:
            blocked.append(line)

    return "\n".join(
        [
            "You convert natural-language part modeling requests into FeaturePlan v2 JSON only.",
            "Return one JSON object. Do not include markdown, comments, code, scripts, macros, commands, or paths.",
            "The LLM may only output FeaturePlan data. It must not directly operate SOLIDWORKS.",
            "Use the Feature Registry as the source of truth for matching user intent to operations.",
            "Do not invent local fallback behavior, partial plans, or unsupported operations when the request cannot be represented.",
            "If the request cannot be represented with implemented operations, produce no executable workaround; the caller must reject or ask for clarification.",
            "All units are mm. Use version='2.0' and document_type='part'.",
            build_policy_prompt_summary(),
            "Use metadata.inferred_parameters and metadata.explicit_parameters to mark parameter provenance.",
            "For every coordinate, dimension, count, spacing, angle, target, or material value copied directly from the user request, add '<operation_id>.params.<parameter>' to metadata.explicit_parameters.",
            "For every coordinate, dimension, count, spacing, angle, target, or material value recommended or completed by the LLM, add '<operation_id>.params.<parameter>' to metadata.inferred_parameters.",
            "When converting edge distance into a center coordinate, mark the resulting center as inferred unless the user explicitly gave that exact coordinate.",
            "Every operation must have id, op, and params.",
            "Use only implemented operations from the Feature Registry.",
            "Do not output scaffolded, planned, unsupported, or unknown operations.",
            "Do not output output_dir, path, file_path, save_path, script, macro, command, python_code, vba_code, powershell, shell, subprocess, delete, remove, or overwrite.",
            "If the user asks for save/export/capture, prefer explicit operations save_sldprt/export_step/capture_png and keep outputs booleans false to avoid duplicate default outputs.",
            "If the user asks for a blank/new/empty part only, create no geometry: use create_new_part plus requested output operations such as save_sldprt.",
            "Default mm template means use the configured SOLIDWORKS default Part template; do not output template paths or user paths.",
            "For a simple rectangular base plate with four corner holes, prefer create_base_plate followed by cut_corner_holes.",
            "For basic rectangular solids, use create_new_part -> create_sketch -> sketch_center_rectangle -> extrude_boss.",
            "All top-face cuts, holes, fillets, chamfers, patterns, and mirrors require a completed base solid first; do not cut after only creating a sketch.",
            "Distinguish chamfer from fillet: C2, C 2, chamfer, and Chinese 倒角 mean add_chamfer with distance=2, not add_fillet.",
            "Distinguish fillet from chamfer: R2, R 2, fillet, round, Chinese 倒圆, and Chinese 圆角 mean add_fillet with radius=2.",
            "For outer contour C-size chamfers, use add_chamfer target='outer_edges' and angle=45 unless the user gives another chamfer angle.",
            "For outer contour R-size rounds, use add_fillet target='outer_edges'.",
            "For top-face holes created with create_through_hole/create_blind_hole, use plane='top_face' and center=[0,0] when the request says top surface center.",
            "For a plain rectangular box/block center through hole with no boss/platform, use create_through_hole or cut_center_hole target='base'.",
            "Do not use cut_center_hole for off-center holes, edge-distance holes, or holes intended as pattern seeds. Those must use create_through_hole/create_blind_hole with an explicit center coordinate.",
            "For an off-center positioned hole on a rectangular plate, use create_through_hole with explicit center coordinates; do not use cut_center_hole.",
            "For distance from the left edge of a centered rectangle, compute x = -length/2 + distance; if no front/back distance is given, use y=0.",
            "For distance from the right edge, compute x = length/2 - distance; from the lower/front edge compute y = -width/2 + distance; from the upper/back edge compute y = width/2 - distance.",
            "For slot cuts, use cut_slot directly with plane, center, length, width, optional direction, and through_all/depth; do not create an extra slot sketch first.",
            "For cut_slot, use direction='x' when the slot span follows the base length/X direction, and direction='y' when the slot span follows the base width/Y direction.",
            "For create_linear_pattern, create_circular_pattern, and mirror_feature, params.seed_feature must reference the producing operation id directly, such as hole_001, blind_001, pocket_001, or 4. Do not output suffixes like .feature_id. Legacy HoleN aliases are accepted only for compatibility.",
            "For create_linear_pattern, use params.direction=x/y/z directly. Do not add create_axis or other reference geometry unless the user explicitly requests it or the operation intrinsically requires it.",
            "create_circular_pattern may require an explicit axis, but create_linear_pattern does not require create_axis.",
            "If a hole will be patterned, mirrored, or reused as a seed feature, prefer create_through_hole or create_blind_hole. Do not use cut_center_hole as a pattern or mirror seed.",
            "For rectangular pockets, use cut_rectangle_pocket directly with plane, center, length, width, and depth; do not create an extra pocket sketch first.",
            "For four corner holes where the user gives hole-center distance from base edges, use cut_corner_holes edge_margin=<that distance in mm>.",
            "For cut_corner_holes, edge_margin, offset_x, and offset_y are positive distances from the base edges or centerline extents. Never output negative values for cut_corner_holes.",
            "For four corner holes where the user gives no edge distance, infer conservative offsets or edge_margin from the base dimensions and bolt size.",
            "Interpret M6 clearance/corner bolt holes as cut_corner_holes diameter=6.6 mm unless the user explicitly gives another diameter. Never leave M6 as a string or omit the numeric diameter.",
            "For center holes where the user gives hole depth/height, use cut_center_hole depth=<that value in mm> and set through_all=false unless the user explicitly asks for a through hole.",
            "For a hole in the center raised boss/platform, use cut_center_hole target='boss' after create_center_boss.",
            "For cut_center_hole, use only diameter plus optional depth/through_all/target. Never output plane or center for cut_center_hole; the center is implied by the target geometry.",
            "For a center hole in only the rectangular base with no boss/platform, use create_through_hole or cut_center_hole target='base'.",
            "If the request is specifically a centered hole in a boss or centered hole in the base, prefer cut_center_hole with target='boss' or target='base' instead of adding plane/center fields.",
            "For center holes where the user explicitly asks for through/all-through, use through_all=true and omit depth unless it is needed as traceability.",
            *(
                [
                    "For material requests, use set_material only when the material exists in the project-local official SOLIDWORKS material catalog below.",
                    "Map the user's material wording to the closest official SOLIDWORKS catalog entry.",
                    "Prefer the official SOLIDWORKS material name as set_material.params.material, for example '6061 Alloy' instead of the search term 'Aluminum_6061'. material_id is accepted only for backward compatibility.",
                ]
                if include_materials
                else []
            ),
            "For custom properties, use only allowlisted keys: PartNumber, Description, Designer, ProjectNo, Revision, MaterialSpec.",
            "Map Chinese 零件编号/零件号/料号 and English part number/part no to set_custom_property key='PartNumber'.",
            "Map Chinese 描述/说明 and English description to set_custom_property key='Description'.",
            "Never use dangerous words such as script, macro, command, shell, powershell, python, delete, remove, or overwrite as custom property keys or values.",
            *(["", "Official SOLIDWORKS material catalog:", *prompt_material_lines()] if include_materials else []),
            "",
            "Implemented operations:",
            *implemented,
            *(["", "Blocked non-implemented operations:", *blocked] if include_blocked else []),
        ]
    )
