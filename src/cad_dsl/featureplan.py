"""Typed FeaturePlan v2 structures.

FeaturePlan is a declarative description of CAD intent. LLMs and Codex may
produce this data, but execution must always go through policy validation and a
fixed executor implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


SUPPORTED_PLAN_VERSION = "2.0"
DEFAULT_UNIT = "mm"


@dataclass(frozen=True)
class PlanMetadata:
    name: str = "unnamed_part"
    description: str = ""
    source: str = "local"
    inferred_parameters: tuple[str, ...] = ()
    explicit_parameters: tuple[str, ...] = ()
    # 增量模式标志：当插件在“当前已打开的 SolidWorks 零件”上继续操作（例如仅在
    # 已有安装板上开槽/开孔）时置 True。此时 FeaturePlan 可以不包含创建底板的
    # 算子，规划阶段应把当前零件视为隐式的已完成实体（existing base solid），
    # 从而放宽 cut_slot 等 solid-body 依赖算子对 base 的硬性校验。
    assume_existing_base: bool = False


@dataclass(frozen=True)
class FeatureOperation:
    id: str
    op: str
    params: Mapping[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()

    @property
    def type(self) -> str:
        return self.op

    @property
    def parameters(self) -> Mapping[str, Any]:
        return self.params


@dataclass(frozen=True)
class FeaturePlan:
    version: str
    unit: str
    document_type: str
    part_name: str
    operations: tuple[FeatureOperation, ...]
    outputs: Mapping[str, bool] = field(default_factory=dict)
    metadata: PlanMetadata = field(default_factory=PlanMetadata)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FeaturePlan":
        metadata_data = data.get("metadata") or {}
        operations_data = data.get("operations") or []
        part_name = str(data.get("part_name") or metadata_data.get("name", "unnamed_part"))
        return cls(
            version=str(data.get("version", "")),
            unit=str(data.get("unit", "")),
            document_type=str(data.get("document_type", "part")),
            part_name=part_name,
            metadata=PlanMetadata(
                name=part_name,
                description=str(metadata_data.get("description", "")),
                source=str(metadata_data.get("source", "local")),
                inferred_parameters=tuple(str(value) for value in metadata_data.get("inferred_parameters", ()) or ()),
                explicit_parameters=tuple(str(value) for value in metadata_data.get("explicit_parameters", ()) or ()),
                assume_existing_base=bool(metadata_data.get("assume_existing_base", False)),
            ),
            operations=tuple(
                FeatureOperation(
                    id=str(item.get("id", "")),
                    op=str(item.get("op") or item.get("type", "")),
                    params=item.get("params") or item.get("parameters") or {},
                    depends_on=tuple(str(value) for value in item.get("depends_on", ())),
                )
                for item in operations_data
            ),
            outputs=data.get("outputs") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "unit": self.unit,
            "document_type": self.document_type,
            "part_name": self.part_name,
            "metadata": {
                "name": self.part_name,
                "description": self.metadata.description,
                "source": self.metadata.source,
                "inferred_parameters": list(self.metadata.inferred_parameters),
                "explicit_parameters": list(self.metadata.explicit_parameters),
                "assume_existing_base": self.metadata.assume_existing_base,
            },
            "operations": [
                {
                    "id": operation.id,
                    "op": operation.op,
                    "params": dict(operation.params),
                    "depends_on": list(operation.depends_on),
                }
                for operation in self.operations
            ],
            "outputs": dict(self.outputs),
        }


def minimal_mounting_plate_plan() -> FeaturePlan:
    return FeaturePlan(
        version=SUPPORTED_PLAN_VERSION,
        unit=DEFAULT_UNIT,
        document_type="part",
        part_name="ai_mounting_plate",
        metadata=PlanMetadata(name="ai_mounting_plate"),
        operations=(
            FeatureOperation(
                id="base_001",
                op="create_base_plate",
                params={"length": 120, "width": 80, "thickness": 12, "plane": "Top"},
            ),
        ),
        outputs={"save_sldprt": True, "export_step": True, "capture_png": True},
    )
