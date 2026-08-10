"""CADPlan Lite to FeaturePlan v2 adapter."""

from __future__ import annotations

from typing import Any, Mapping

from cad_dsl.featureplan import DEFAULT_UNIT, SUPPORTED_PLAN_VERSION, FeatureOperation, FeaturePlan


def cadplan_to_featureplan(cadplan: Mapping[str, Any]) -> FeaturePlan:
    if cadplan.get("template") == "blank_part":
        outputs = dict(cadplan.get("outputs", {}))
        operations: list[FeatureOperation] = [
            FeatureOperation(
                id="new_001",
                op="create_new_part",
                params={},
            )
        ]
        if outputs.get("save_sldprt", True):
            operations.append(FeatureOperation(id="save_001", op="save_sldprt", params={}))
        if outputs.get("export_step", False):
            operations.append(FeatureOperation(id="export_001", op="export_step", params={}))
        if outputs.get("capture_png", False):
            operations.append(FeatureOperation(id="capture_001", op="capture_png", params={}))
        return FeaturePlan(
            version=SUPPORTED_PLAN_VERSION,
            unit=DEFAULT_UNIT,
            document_type="part",
            part_name=str(cadplan.get("part_name", "blank_part")),
            operations=tuple(operations),
            outputs=outputs,
        )

    base = cadplan["base"]
    if base.get("shape", "rectangle") != "rectangle":
        raise ValueError("api_executor 当前仅支持矩形底板 FeaturePlan")

    operations: list[FeatureOperation] = [
        FeatureOperation(
            id="base_001",
            op="create_base_plate",
            params={
                "length": base["length"],
                "width": base["width"],
                "thickness": base["thickness"],
                "plane": "Top",
            },
        )
    ]

    corner = cadplan.get("corner_holes", {})
    if corner.get("enabled"):
        operations.append(
            FeatureOperation(
                id="hole_001",
                op="cut_corner_holes",
                params={
                    "diameter": corner["diameter"],
                    "offset_x": corner["offset_x"],
                    "offset_y": corner["offset_y"],
                    "through_all": bool(corner.get("through_all", True)),
                },
            )
        )

    boss = cadplan.get("center_boss", {})
    if boss.get("enabled"):
        operations.append(
            FeatureOperation(
                id="boss_001",
                op="create_center_boss",
                params={"diameter": boss["diameter"], "height": boss["height"], "plane": "top_face"},
            )
        )

    center_hole = cadplan.get("center_hole", {})
    if center_hole.get("enabled"):
        if center_hole.get("target") == "base" or not boss.get("enabled"):
            operations.append(
                FeatureOperation(
                    id="hole_002",
                    op="create_through_hole",
                    params={
                        "plane": "top_face",
                        "center": [0, 0],
                        "diameter": center_hole["diameter"],
                        "through_all": bool(center_hole.get("through_all", True)),
                    },
                )
            )
            center_hole = {}
    if center_hole.get("enabled"):
        operations.append(
            FeatureOperation(
                id="hole_002",
                op="cut_center_hole",
                params={
                    "diameter": center_hole["diameter"],
                    "through_all": bool(center_hole.get("through_all", True)),
                },
            )
        )

    fillet = cadplan.get("fillet", {})
    if fillet.get("enabled"):
        operations.append(
            FeatureOperation(
                id="fillet_001",
                op="add_fillet",
                params={"radius": fillet["radius"], "target": "outer_edges"},
            )
        )

    return FeaturePlan(
        version=SUPPORTED_PLAN_VERSION,
        unit=DEFAULT_UNIT,
        document_type="part",
        part_name=str(cadplan.get("part_name", "ai_mounting_plate")),
        operations=tuple(operations),
        outputs=dict(cadplan.get("outputs", {})),
    )
