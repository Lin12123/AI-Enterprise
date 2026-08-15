"""标准主表 CRUD 路由。/api/standards"""
import os

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
    """删除标准：级联删除其规则(standard_rule ON DELETE CASCADE)，
    并清理导入附件记录与物理文件。"""
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT id FROM standard WHERE id = ?", (sid,)).fetchone()
        if not row:
            return fail("标准不存在")

        # 先取该标准的附件物理文件，删库后再清盘
        atts = conn.execute(
            "SELECT stored_path FROM import_attachment WHERE standard_id = ?", (sid,)
        ).fetchall()

        rule_cnt = conn.execute(
            "SELECT COUNT(*) AS c FROM standard_rule WHERE standard_id = ?", (sid,)
        ).fetchone()["c"]

        # 删附件登记(ON DELETE SET NULL 不会自动删记录，这里显式清理)
        conn.execute("DELETE FROM import_attachment WHERE standard_id = ?", (sid,))
        # 删标准主表 -> standard_rule 随 ON DELETE CASCADE 一并删除
        conn.execute("DELETE FROM standard WHERE id = ?", (sid,))
        conn.commit()

        # 清理物理文件(尽力而为，失败不阻断)
        for a in atts:
            sp = a["stored_path"]
            if not sp:
                continue
            abs_path = os.path.join(db.UPLOAD_DIR, sp)
            try:
                if os.path.exists(abs_path):
                    os.remove(abs_path)
            except OSError:
                pass

        return ok({"id": sid, "deleted_rules": rule_cnt}, f"已删除标准及其 {rule_cnt} 条规则")
    finally:
        conn.close()