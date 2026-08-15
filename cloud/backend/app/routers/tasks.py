"""产物：插件任务 CRUD 路由。/api/tasks

插件出图成功后 POST 上报任务，payload_json 存生成上下文(零件/材料/标准等)。
"""
import json

from fastapi import APIRouter

from app import db
from app.schemas import TaskIn, ok, fail

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _row(r) -> dict:
    d = db.row_to_dict(r)
    if d.get("payload_json"):
        try:
            d["payload_json"] = json.loads(d["payload_json"])
        except (ValueError, TypeError):
            pass
    return d


@router.get("")
def list_tasks(keyword: str = "", status: str = ""):
    conn = db.get_conn()
    try:
        sql = "SELECT * FROM task WHERE 1=1"
        args: list = []
        if keyword:
            sql += " AND (title LIKE ? OR part_name LIKE ?)"
            args += [f"%{keyword}%", f"%{keyword}%"]
        if status:
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, args).fetchall()
        return ok([_row(r) for r in rows])
    finally:
        conn.close()


@router.get("/{tid}")
def get_task(tid: int):
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM task WHERE id = ?", (tid,)).fetchone()
        if not row:
            return fail("任务不存在")
        data = _row(row)
        files = conn.execute("SELECT * FROM file WHERE task_id = ?", (tid,)).fetchall()
        data["files"] = [db.row_to_dict(f) for f in files]
        return ok(data)
    finally:
        conn.close()


@router.post("")
def create_task(body: TaskIn):
    conn = db.get_conn()
    try:
        payload = json.dumps(body.payload_json, ensure_ascii=False) if body.payload_json else None
        cur = conn.execute(
            "INSERT INTO task(task_uid, title, part_name, material, status, payload_json)"
            " VALUES(?,?,?,?,?,?)",
            (body.task_uid, body.title, body.part_name, body.material, body.status, payload),
        )
        conn.commit()
        return ok({"id": cur.lastrowid}, "已上报")
    except Exception as exc:
        return fail(f"上报失败: {exc}")
    finally:
        conn.close()


@router.post("/upsert")
def upsert_task(body: TaskIn):
    """按 task_uid 幂等建任务：存在则更新非空字段并返回其 id，不存在则新建。

    供本地服务"上传云平台"使用：本地用会话 id(session_id)作为 task_uid，
    多次上传同一会话产物时能拿到同一个稳定的 task_id 用于文件归集，
    避免 task_uid UNIQUE 约束在重复上传时报错。
    """
    if not body.task_uid:
        return fail("缺少 task_uid")
    payload = json.dumps(body.payload_json, ensure_ascii=False) if body.payload_json else None
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM task WHERE task_uid = ?", (body.task_uid,)
        ).fetchone()
        if row:
            tid = row["id"]
            # 只覆盖本次显式带来的非空字段，避免把已有值清空
            conn.execute(
                "UPDATE task SET"
                " title = COALESCE(?, title),"
                " part_name = COALESCE(?, part_name),"
                " material = COALESCE(?, material),"
                " status = COALESCE(?, status),"
                " payload_json = COALESCE(?, payload_json)"
                " WHERE id = ?",
                (body.title, body.part_name, body.material, body.status, payload, tid),
            )
            conn.commit()
            return ok({"id": tid, "created": False}, "已存在，已更新")
        cur = conn.execute(
            "INSERT INTO task(task_uid, title, part_name, material, status, payload_json)"
            " VALUES(?,?,?,?,?,?)",
            (body.task_uid, body.title, body.part_name, body.material, body.status, payload),
        )
        conn.commit()
        return ok({"id": cur.lastrowid, "created": True}, "已创建")
    except Exception as exc:
        return fail(f"upsert 失败: {exc}")
    finally:
        conn.close()