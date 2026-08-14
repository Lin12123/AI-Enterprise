"""会话持久化存储(纯标准库, 零第三方依赖)。

职责：把用户与 AI 的多轮对话、每次建模任务的结果，以 JSON 文件形式落盘到
workspace/sessions/ 下，使得：
  - 同一会话的上下文可被记录并在下次生成计划时回放给 LLM;
  - 重开 SolidWorks / 插件后能通过"任务中心"找回历史对话。

设计要点(与项目离线约束一致)：
- 仅使用标准库(json / os / threading / datetime / pathlib), 不引入 sqlite 之外的任何存储。
  评估结论：单机单用户、数据量小(一年至多数千条)、查询仅"最近 N 条 + 按 id 打开",
  JSON 文件足够, 无需数据库。
- 目录结构:
    workspace/sessions/
      index.json                 会话索引(最近列表快速读取, 无需扫描全部文件)
      <session_id>.json          单个会话完整记录(标题/状态/消息列表/上下文)
- 线程安全: 服务端为 ThreadingHTTPServer, 用一把进程内锁串行化读写, 避免并发写坏文件。
- 原子写盘: 先写临时文件再 os.replace, 防止写入中途崩溃导致文件损坏。

会话文件结构(<session_id>.json):
{
  "id": "20260814_225352_a1b2",
  "title": "SolidWorks AI 3D 几何建树写入",
  "status": "active",              # active / done / failed
  "started_at": "2026-08-14T22:53:52",
  "updated_at": "2026-08-14T22:55:10",
  "messages": [
    {"role": "user", "text": "画一个120mm*80mm...", "ts": "..."},
    {"role": "ai",   "text": "已生成计划...",      "ts": "..."},
    {"role": "ai",   "type": "result_board", "text": "建树完成", "ts": "..."}
  ],
  "context": {"last_plan": {...}}   # 供"修改当前零件"等场景复用
}

index.json 结构:
{
  "sessions": [
    {"id": "...", "title": "...", "status": "done",
     "started_at": "...", "updated_at": "..."}
  ]
}
索引按 updated_at 倒序维护, list_recent() 直接切片返回。
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---- 常量与路径 ----------------------------------------------------------------

_INDEX_FILENAME = "index.json"
_VALID_ROLES = {"user", "ai"}
_VALID_STATUS = {"active", "done", "failed"}


def _now_iso() -> str:
    """当前本地时间的 ISO 字符串(不含微秒, 便于展示)。"""
    return datetime.now().replace(microsecond=0).isoformat()


def _default_sessions_dir() -> Path:
    """默认会话目录: <project_root>/workspace/sessions。

    本文件位于 <root>/service/ 下, 因此项目根为 parents[1]。
    """
    root = Path(__file__).resolve().parents[1]
    return root / "workspace" / "sessions"


# ---- 会话存储 ------------------------------------------------------------------

class SessionStore:
    """基于 JSON 文件的会话存储。线程安全, 原子写盘。"""

    def __init__(self, base_dir: Optional[os.PathLike] = None) -> None:
        self._dir = Path(base_dir) if base_dir is not None else _default_sessions_dir()
        self._lock = threading.RLock()
        self._dir.mkdir(parents=True, exist_ok=True)
        # 进程内单调递增序号: updated_at 只精确到秒, 同一秒内多次更新时用它
        # 作为次级排序键, 保证"后更新的排在前面", 让任务中心顺序稳定可预期。
        self._seq = 0

    # ---- 对外 API ----

    def create_session(self, title: str = "", first_message: Optional[dict] = None) -> str:
        """新建会话, 返回 session_id。可选携带首条消息(通常为用户输入)。"""
        with self._lock:
            sid = self._new_id()
            now = _now_iso()
            session = {
                "id": sid,
                "title": (title or "").strip() or "未命名会话",
                "status": "active",
                "started_at": now,
                "updated_at": now,
                "messages": [],
                "context": {},
            }
            if first_message:
                session["messages"].append(self._normalize_message(first_message))
            self._write_session(session)
            self._upsert_index(session)
            return sid

    def append_message(self, session_id: str, message: dict) -> bool:
        """向指定会话追加一条消息并刷新 updated_at。会话不存在返回 False。"""
        with self._lock:
            session = self._read_session(session_id)
            if session is None:
                return False
            session["messages"].append(self._normalize_message(message))
            session["updated_at"] = _now_iso()
            # 若首条消息即为用户输入且标题仍为默认, 用其文本生成标题
            if session.get("title", "") in ("", "未命名会话"):
                text = str(message.get("text", "")).strip()
                if text:
                    session["title"] = text[:24]
            self._write_session(session)
            self._upsert_index(session)
            return True

    def set_status(self, session_id: str, status: str) -> bool:
        """更新会话状态(active/done/failed)。"""
        if status not in _VALID_STATUS:
            status = "active"
        with self._lock:
            session = self._read_session(session_id)
            if session is None:
                return False
            session["status"] = status
            session["updated_at"] = _now_iso()
            self._write_session(session)
            self._upsert_index(session)
            return True

    def set_context(self, session_id: str, key: str, value: Any) -> bool:
        """写入/更新会话上下文中的一个键(如 last_plan)。"""
        with self._lock:
            session = self._read_session(session_id)
            if session is None:
                return False
            ctx = session.setdefault("context", {})
            ctx[str(key)] = value
            session["updated_at"] = _now_iso()
            self._write_session(session)
            return True

    def load(self, session_id: str) -> Optional[dict]:
        """读取完整会话记录(含全部消息)。不存在返回 None。"""
        with self._lock:
            return self._read_session(session_id)

    def list_recent(self, limit: int = 3) -> List[dict]:
        """返回最近的 limit 条会话摘要(按 updated_at 倒序)。"""
        if limit <= 0:
            return []
        with self._lock:
            index = self._read_index()
            items = list(index.get("sessions", []))[:limit]
            # 剔除内部排序字段 _seq, 不对外暴露
            return [{k: v for k, v in item.items() if k != "_seq"} for item in items]

    def get_messages(self, session_id: str) -> List[dict]:
        """返回会话的消息列表(不存在则空列表)。"""
        session = self.load(session_id)
        return list(session.get("messages", [])) if session else []

    # ---- 内部实现 ----

    def _new_id(self) -> str:
        """生成可读且唯一的会话 id: 时间戳 + 短随机后缀。"""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = uuid.uuid4().hex[:4]
        return f"{stamp}_{suffix}"

    def _normalize_message(self, message: dict) -> dict:
        """规范化一条消息: 校验 role, 补 ts, 保留可选 type。"""
        role = str(message.get("role", "ai")).strip().lower()
        if role not in _VALID_ROLES:
            role = "ai"
        item = {
            "role": role,
            "text": str(message.get("text", "")),
            "ts": str(message.get("ts", "")).strip() or _now_iso(),
        }
        msg_type = message.get("type")
        if msg_type:
            item["type"] = str(msg_type)
        return item

    def _session_path(self, session_id: str) -> Path:
        # 防路径穿越: 只保留安全字符
        safe = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in ("_", "-"))
        return self._dir / f"{safe}.json"

    def _index_path(self) -> Path:
        return self._dir / _INDEX_FILENAME

    def _read_session(self, session_id: str) -> Optional[dict]:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as fp:
                return json.load(fp)
        except (OSError, ValueError):
            return None

    def _write_session(self, session: dict) -> None:
        self._atomic_write(self._session_path(session["id"]), session)

    def _read_index(self) -> dict:
        path = self._index_path()
        if not path.exists():
            return {"sessions": []}
        try:
            with path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
                if isinstance(data, dict) and isinstance(data.get("sessions"), list):
                    return data
        except (OSError, ValueError):
            pass
        return {"sessions": []}

    def _upsert_index(self, session: dict) -> None:
        """把会话摘要更新进索引, 并按 updated_at 倒序排列。

        updated_at 仅精确到秒, 故用进程内单调序号 _seq 作次级键,
        保证同一秒内后更新的会话排在前面(任务中心顺序稳定)。
        """
        index = self._read_index()
        self._seq += 1
        summary = {
            "id": session["id"],
            "title": session.get("title", ""),
            "status": session.get("status", "active"),
            "started_at": session.get("started_at", ""),
            "updated_at": session.get("updated_at", ""),
            "_seq": self._seq,
        }
        sessions = [s for s in index.get("sessions", []) if s.get("id") != session["id"]]
        sessions.append(summary)
        sessions.sort(
            key=lambda s: (s.get("updated_at", ""), s.get("_seq", 0)), reverse=True)
        index["sessions"] = sessions
        self._atomic_write(self._index_path(), index)

    def _atomic_write(self, path: Path, data: dict) -> None:
        """原子写: 先写 .tmp 再 os.replace, 避免中途崩溃损坏文件。"""
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        os.replace(str(tmp), str(path))


# ---- 进程内单例(供 http_service 复用) ----------------------------------------

_STORE: Optional[SessionStore] = None
_STORE_LOCK = threading.Lock()


def get_session_store() -> SessionStore:
    """返回服务进程内唯一的 SessionStore 实例。"""
    global _STORE
    if _STORE is None:
        with _STORE_LOCK:
            if _STORE is None:
                _STORE = SessionStore()
    return _STORE