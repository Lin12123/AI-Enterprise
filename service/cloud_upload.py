"""把本次会话生成的产物(3D 零件 / 2D 工程图)上传到云平台。

职责：出图成功后，用户点击"上传云平台"时，把本次会话关联的 3D(.SLDPRT)
和 2D(.SLDDRW)文件上传到云平台的项目图纸管理模块，按会话(task_uid)聚合归集。

数据流:
    session_id(会话标识) → 云平台 /api/tasks/upsert 得到稳定 task_id
    → 逐个文件 /api/files/upload(multipart, 带 task_id + file_type)
    → 返回每个文件的登记结果

设计要点:
- 仅使用标准库 urllib，零第三方依赖，符合内网离线约束(禁装第三方包)。
- 复用 knowledge_cache 的 base_url 约定(默认 http://127.0.0.1:8800，
  可用环境变量 AI_SW_CLOUD_URL 覆盖)。
- 云平台不可达/单文件失败不静默吞掉：以结构化结果返回，供插件如实展示。
"""

from __future__ import annotations

import json
import mimetypes
import os
import uuid
import urllib.request
from datetime import datetime


DEFAULT_TIMEOUT = 30  # 上传单文件超时(秒)：文件较大，给宽松值


def _base_url() -> str:
    """云平台后端地址，与 knowledge_cache 保持同一约定。"""
    default = "http://127.0.0.1:8800"
    return os.environ.get("AI_SW_CLOUD_URL", default).rstrip("/")


def _log(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] [上传云平台] {message}", flush=True)


def _encode_multipart(fields: dict[str, str], file_field: str,
                      file_name: str, file_bytes: bytes) -> tuple[bytes, str]:
    """把普通表单字段 + 单个文件编码为 multipart/form-data 请求体。

    仅用标准库拼装(不依赖 requests)。返回(body_bytes, content_type)。
    """
    boundary = f"----AISWBoundary{uuid.uuid4().hex}"
    crlf = b"\r\n"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f"--{boundary}".encode("utf-8"))
        parts.append(
            f'Content-Disposition: form-data; name="{name}"'.encode("utf-8")
        )
        parts.append(b"")
        parts.append(str(value).encode("utf-8"))
    # 文件部分
    ctype = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    parts.append(f"--{boundary}".encode("utf-8"))
    parts.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{file_name}"'
        ).encode("utf-8")
    )
    parts.append(f"Content-Type: {ctype}".encode("utf-8"))
    parts.append(b"")
    parts.append(file_bytes)
    parts.append(f"--{boundary}--".encode("utf-8"))
    parts.append(b"")
    body = crlf.join(parts)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def _post_json(url: str, payload: dict, timeout: int = 10) -> dict:
    """向云平台 POST 一个 JSON 请求，返回解析后的 dict。失败抛异常。"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _upsert_task(base_url: str, task_uid: str, title: str | None,
                 part_name: str | None, material: str | None) -> int:
    """按会话标识在云平台幂等建任务，返回稳定 task_id。失败抛异常。"""
    url = f"{base_url}/api/tasks/upsert"
    body = {
        "task_uid": task_uid,
        "title": title,
        "part_name": part_name,
        "material": material,
        "status": "done",
    }
    resp = _post_json(url, body, timeout=10)
    if not (isinstance(resp, dict) and resp.get("ok")):
        raise RuntimeError(f"建任务失败: {resp.get('message') if isinstance(resp, dict) else resp}")
    data = resp.get("data") or {}
    tid = data.get("id")
    if not tid:
        raise RuntimeError("云平台未返回 task_id")
    return int(tid)


def _upload_one(base_url: str, task_id: int, file_type: str, file_path: str) -> dict:
    """上传单个文件到 /api/files/upload。返回单文件结果 dict(不抛异常)。"""
    name = os.path.basename(file_path)
    result: dict = {"file_type": file_type, "file_name": name, "path": file_path}
    if not file_path or not os.path.isfile(file_path):
        result.update({"ok": False, "message": "本地文件不存在"})
        return result
    try:
        with open(file_path, "rb") as fh:
            file_bytes = fh.read()
        body, content_type = _encode_multipart(
            fields={"task_id": str(task_id), "file_type": file_type},
            file_field="file", file_name=name, file_bytes=file_bytes,
        )
        url = f"{base_url}/api/files/upload"
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": content_type, "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
        resp_json = json.loads(raw)
        if isinstance(resp_json, dict) and resp_json.get("ok"):
            fid = (resp_json.get("data") or {}).get("id")
            result.update({"ok": True, "file_id": fid, "size": len(file_bytes)})
        else:
            msg = resp_json.get("message") if isinstance(resp_json, dict) else str(resp_json)
            result.update({"ok": False, "message": f"云平台登记失败: {msg}"})
    except Exception as exc:  # noqa: BLE001 - 单文件失败不影响其他文件
        result.update({"ok": False, "message": f"上传异常: {exc}"})
    return result


def upload_session_outputs(session_id: str, files: list[dict],
                           title: str | None = None,
                           part_name: str | None = None,
                           material: str | None = None) -> dict:
    """把一批会话产物文件上传到云平台，按 session_id 聚合到同一任务。

    参数:
        session_id: 会话标识，作为云平台 task_uid(项目图纸按此聚合)。
        files: [{"file_type": "part"|"drawing", "path": "本地绝对路径"}, ...]
        title/part_name/material: 任务元信息(用于云平台列表展示)。
    返回:
        {"ok": bool, "task_id": int|None, "uploaded": int, "total": int,
         "items": [单文件结果...], "message": str}
    """
    if not session_id:
        return {"ok": False, "message": "缺少 session_id", "items": [], "uploaded": 0, "total": 0}
    valid = [f for f in (files or []) if f.get("path")]
    if not valid:
        return {"ok": False, "message": "没有可上传的产物文件", "items": [], "uploaded": 0, "total": 0}

    base_url = _base_url()
    _log(f"开始上传会话 {session_id} 的 {len(valid)} 个产物到 {base_url}")

    try:
        task_id = _upsert_task(base_url, session_id, title, part_name, material)
    except Exception as exc:  # noqa: BLE001
        _log(f"建任务失败: {exc}")
        return {"ok": False, "message": f"云平台建任务失败: {exc}",
                "items": [], "uploaded": 0, "total": len(valid), "task_id": None}

    items = [_upload_one(base_url, task_id, f.get("file_type", ""), f["path"]) for f in valid]
    uploaded = sum(1 for it in items if it.get("ok"))
    all_ok = uploaded == len(valid)
    if all_ok:
        message = f"已上传 {uploaded} 个文件到云平台项目图纸管理"
    elif uploaded > 0:
        message = f"部分成功: {uploaded}/{len(valid)} 个文件已上传，其余见明细"
    else:
        message = "全部文件上传失败，请检查云平台是否可达"
    _log(message)
    return {"ok": all_ok or uploaded > 0, "task_id": task_id,
            "uploaded": uploaded, "total": len(valid), "items": items, "message": message}