"""统一响应结构与请求体模型(Pydantic)。

统一响应：{ok, data, message}，对齐 docs/cloud_platform_design.md §5。
"""
from typing import Any, Optional

from pydantic import BaseModel


def ok(data: Any = None, message: str = "") -> dict[str, Any]:
    return {"ok": True, "data": data, "message": message}


def fail(message: str, data: Any = None) -> dict[str, Any]:
    return {"ok": False, "data": data, "message": message}


# ---------- 知识库 ----------
class StandardIn(BaseModel):
    standard_no: str
    standard_type: Optional[str] = None
    title: Optional[str] = None
    version: Optional[str] = None
    source: Optional[str] = None
    status: str = "published"


class RuleIn(BaseModel):
    standard_id: int
    scope_material: Optional[str] = None
    scope_feature: Optional[str] = None
    clause: Optional[str] = None
    params_json: Optional[dict[str, Any]] = None
    status: str = "published"


# ---------- 基础数据 ----------
class MaterialIn(BaseModel):
    name: str
    density: Optional[float] = None
    remark: Optional[str] = None


class TemplateIn(BaseModel):
    name: str
    category: Optional[str] = None
    file_path: Optional[str] = None
    remark: Optional[str] = None


# ---------- 产物 ----------
class TaskIn(BaseModel):
    task_uid: Optional[str] = None
    title: Optional[str] = None
    part_name: Optional[str] = None
    material: Optional[str] = None
    status: Optional[str] = None
    payload_json: Optional[dict[str, Any]] = None


class FileIn(BaseModel):
    task_id: Optional[int] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None
    stored_path: Optional[str] = None
    size_bytes: Optional[int] = None