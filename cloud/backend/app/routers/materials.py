"""基础数据：材料 CRUD 路由。/api/materials"""
from fastapi import APIRouter

from app import db
from app.schemas import MaterialIn, ok, fail

router = APIRouter(prefix="/api/materials", tags=["materials"])


@router.get("")
def list_materials(keyword: str = ""):
    conn = db.get_conn()
    try:
        if keyword:
            rows = conn.execute(
                "SELECT * FROM material WHERE name LIKE ? ORDER BY name",
                (f"%{keyword}%",),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM material ORDER BY name").fetchall()
        return ok([db.row_to_dict(r) for r in rows])
    finally:
        conn.close()


@router.post("")
def create_material(body: MaterialIn):
    conn = db.get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO material(name, density, remark) VALUES(?,?,?)",
            (body.name, body.density, body.remark),
        )
        conn.commit()
        return ok({"id": cur.lastrowid}, "已创建")
    except Exception as exc:
        return fail(f"创建失败: {exc}")
    finally:
        conn.close()


@router.put("/{mid}")
def update_material(mid: int, body: MaterialIn):
    conn = db.get_conn()
    try:
        conn.execute(
            "UPDATE material SET name=?, density=?, remark=?, updated_at=datetime('now') WHERE id=?",
            (body.name, body.density, body.remark, mid),
        )
        conn.commit()
        return ok({"id": mid}, "已更新")
    finally:
        conn.close()


@router.delete("/{mid}")
def delete_material(mid: int):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM material WHERE id = ?", (mid,))
        conn.commit()
        return ok({"id": mid}, "已删除")
    finally:
        conn.close()