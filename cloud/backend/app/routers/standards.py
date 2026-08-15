"""标准主表 CRUD 路由。/api/standards"""
from fastapi import APIRouter

from app import db
from app.schemas import StandardIn, ok, fail

router = APIRouter(prefix="/api/standards", tags=["standards"])


@router.get("")
def list_standards(keyword: str = "", status: str = ""):
    conn = db.get_conn()
    try:
        sql = "SELECT * FROM standard WHERE 1=1"
        args: list = []
        if keyword:
            sql += " AND (standard_no LIKE ? OR title LIKE ?)"
            args += [f"%{keyword}%", f"%{keyword}%"]
        if status:
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY updated_at DESC"
        rows = conn.execute(sql, args).fetchall()
        return ok([db.row_to_dict(r) for r in rows])
    finally:
        conn.close()


@router.get("/{sid}")
def get_standard(sid: int):
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM standard WHERE id = ?", (sid,)).fetchone()
        if not row:
            return fail("标准不存在")
        return ok(db.row_to_dict(row))
    finally:
        conn.close()


@router.post("")
def create_standard(body: StandardIn):
    conn = db.get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO standard(standard_no, standard_type, title, version, source, status)"
            " VALUES(?,?,?,?,?,?)",
            (body.standard_no, body.standard_type, body.title, body.version, body.source, body.status),
        )
        conn.commit()
        return ok({"id": cur.lastrowid}, "已创建")
    except Exception as exc:  # UNIQUE 冲突等
        return fail(f"创建失败: {exc}")
    finally:
        conn.close()


@router.put("/{sid}")
def update_standard(sid: int, body: StandardIn):
    conn = db.get_conn()
    try:
        conn.execute(
            "UPDATE standard SET standard_no=?, standard_type=?, title=?, version=?, source=?,"
            " status=?, updated_at=datetime('now') WHERE id=?",
            (body.standard_no, body.standard_type, body.title, body.version, body.source, body.status, sid),
        )
        conn.commit()
        return ok({"id": sid}, "已更新")
    finally:
        conn.close()


@router.delete("/{sid}")
def delete_standard(sid: int):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM standard WHERE id = ?", (sid,))
        conn.commit()
        return ok({"id": sid}, "已删除")
    finally:
        conn.close()