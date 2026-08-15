"""离线单测：cloud_upload 的 multipart 编码与上传流程。

不依赖真实云平台，用 monkeypatch 拦截 urllib 请求，验证:
- _encode_multipart 生成合法 multipart/form-data(含字段与文件)
- _base_url 复用 AI_SW_CLOUD_URL 约定
- upload_session_outputs 全流程(建任务 + 逐文件上传)结果聚合正确
- 缺参数 / 无产物 / 建任务失败 等边界

运行(无 pytest 环境时)::
    from tests import test_cloud_upload as t
    [getattr(t, n)() for n in dir(t) if n.startswith("test_")]
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from service import cloud_upload as cu


# ---- multipart 编码 ------------------------------------------------------------

def test_encode_multipart_contains_fields_and_file():
    body, ctype = cu._encode_multipart(
        fields={"task_id": "7", "file_type": "part"},
        file_field="file", file_name="demo.SLDPRT", file_bytes=b"BINARY",
    )
    assert ctype.startswith("multipart/form-data; boundary=")
    boundary = ctype.split("boundary=")[1]
    text = body.decode("utf-8", errors="ignore")
    # 表单字段
    assert 'name="task_id"' in text and "7" in text
    assert 'name="file_type"' in text and "part" in text
    # 文件部分
    assert 'name="file"; filename="demo.SLDPRT"' in text
    assert "BINARY" in text
    # 结束 boundary
    assert text.rstrip().endswith(f"--{boundary}--")


def test_encode_multipart_binary_preserved():
    raw = bytes(range(256))
    body, _ = cu._encode_multipart(
        fields={}, file_field="file", file_name="a.bin", file_bytes=raw,
    )
    assert raw in body  # 原始字节不被破坏


# ---- base_url 约定 -------------------------------------------------------------

def test_base_url_default_and_override():
    old = os.environ.pop("AI_SW_CLOUD_URL", None)
    try:
        assert cu._base_url() == "http://127.0.0.1:8800"
        os.environ["AI_SW_CLOUD_URL"] = "http://10.0.0.9:8800/"
        assert cu._base_url() == "http://10.0.0.9:8800"
    finally:
        os.environ.pop("AI_SW_CLOUD_URL", None)
        if old is not None:
            os.environ["AI_SW_CLOUD_URL"] = old


# ---- 上传全流程(拦截 urllib) ---------------------------------------------------

class _FakeResp:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _install_fake_urlopen(monkeypatched_calls: list):
    """返回一个假 urlopen: /tasks/upsert 返回 task_id=42, /files/upload 返回自增 id。"""
    counter = {"fid": 100}

    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req.get_full_url()
        monkeypatched_calls.append(url)
        if url.endswith("/api/tasks/upsert"):
            return _FakeResp({"ok": True, "data": {"id": 42, "created": True}})
        if url.endswith("/api/files/upload"):
            counter["fid"] += 1
            return _FakeResp({"ok": True, "data": {"id": counter["fid"]}, "message": "上传成功"})
        return _FakeResp({"ok": False, "message": "未知路由"})

    return fake_urlopen


def test_upload_session_outputs_happy_path():
    calls: list = []
    orig = cu.urllib.request.urlopen
    cu.urllib.request.urlopen = _install_fake_urlopen(calls)
    try:
        with tempfile.TemporaryDirectory() as d:
            p3d = os.path.join(d, "demo.SLDPRT")
            p2d = os.path.join(d, "demo.SLDDRW")
            open(p3d, "wb").write(b"3D")
            open(p2d, "wb").write(b"2D")
            res = cu.upload_session_outputs(
                "sess-1",
                [{"file_type": "part", "path": p3d},
                 {"file_type": "drawing", "path": p2d}],
                title="测试零件",
            )
    finally:
        cu.urllib.request.urlopen = orig
    assert res["ok"] is True
    assert res["task_id"] == 42
    assert res["uploaded"] == 2 and res["total"] == 2
    assert all(it["ok"] for it in res["items"])
    # 先建任务，再上传两个文件
    assert calls[0].endswith("/api/tasks/upsert")
    assert sum(1 for c in calls if c.endswith("/api/files/upload")) == 2


def test_upload_missing_session_id():
    res = cu.upload_session_outputs("", [{"file_type": "part", "path": "x"}])
    assert res["ok"] is False and "session_id" in res["message"]


def test_upload_no_files():
    res = cu.upload_session_outputs("sess-2", [])
    assert res["ok"] is False and res["total"] == 0


def test_upload_local_file_missing_is_reported():
    calls: list = []
    orig = cu.urllib.request.urlopen
    cu.urllib.request.urlopen = _install_fake_urlopen(calls)
    try:
        res = cu.upload_session_outputs(
            "sess-3", [{"file_type": "part", "path": "/no/such/file.SLDPRT"}]
        )
    finally:
        cu.urllib.request.urlopen = orig
    # 任务建了，但唯一文件本地不存在 → 上传数为 0
    assert res["task_id"] == 42
    assert res["uploaded"] == 0
    assert res["items"][0]["ok"] is False
    assert "不存在" in res["items"][0]["message"]