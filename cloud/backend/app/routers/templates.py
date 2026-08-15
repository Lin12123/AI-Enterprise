"""基础数据：图纸/工艺模板 CRUD 路由。/api/templates"""
from fastapi import APIRouter

from app import db
from app.schemas import TemplateIn, ok, fail

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
def list_templates(category: str = ""):
    conn = db.get_conn()
    try:
        if category:
            rows = conn.execute(
                "SELECT * FROM template WHERE category = ? ORDER BY name",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM template ORDER BY name").fetchall()
        return ok([db.row_to_dict(r) for r in rows])
    finally:
        conn.close()


@router.post("")
def create_template(body: TemplateIn):
    conn = db.get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO template(name, category, file_path, remark) VALUES(?,?,?,?)",
            (body.name, body.category, body.file_path, body.remark),
        )
        conn.commit()
        return ok({"id": cur.lastrowid}, "已创建")
    except Exception as exc:
        return fail(f"创建失败: {exc}")
    finally:
        conn.close()


@router.put("/{tid}")
def update_template(tid: int, body: TemplateIn):
    conn = db.get_conn()
    try:
        conn.execute(
            "UPDATE template SET name=?, category=?, file_path=?, remark=?, updated_at=datetime('now') WHERE id=?",
            (body.name, body.category, body.file_path, body.remark, tid),
        )
        conn.commit()
        return ok({"id": tid}, "已更新")
    finally:
        conn.close()


@router.delete("/{tid}")
def delete_template(tid: int):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM template WHERE id = ?", (tid,))
        conn.commit()
        return ok({"id": tid}, "已删除")
    finally:
        conn.close()