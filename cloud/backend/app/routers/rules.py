"""标准条目(规则) CRUD 路由。/api/rules

params_json 以 JSON 文本存储，出入口做序列化/反序列化。
"""
import json

from fastapi import APIRouter

from app import db
from app.schemas import RuleIn, ok, fail

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _row(r) -> dict:
    d = db.row_to_dict(r)
    if d.get("params_json"):
        try:
            d["params_json"] = json.loads(d["params_json"])
        except (ValueError, TypeError):
            pass
    return d


@router.get("")
def list_rules(standard_id: int = 0, scope_material: str = "", scope_feature: str = ""):
    conn = db.get_conn()
    try:
        sql = "SELECT * FROM standard_rule WHERE 1=1"
        args: list = []
        if standard_id:
            sql += " AND standard_id = ?"
            args.append(standard_id)
        if scope_material:
            sql += " AND scope_material = ?"
            args.append(scope_material)
        if scope_feature:
            sql += " AND scope_feature = ?"
            args.append(scope_feature)
        sql += " ORDER BY updated_at DESC"
        rows = conn.execute(sql, args).fetchall()
        return ok([_row(r) for r in rows])
    finally:
        conn.close()


@router.post("")
def create_rule(body: RuleIn):
    conn = db.get_conn()
    try:
        params = json.dumps(body.params_json, ensure_ascii=False) if body.params_json else None
        cur = conn.execute(
            "INSERT INTO standard_rule(standard_id, scope_material, scope_feature, clause, params_json, status)"
            " VALUES(?,?,?,?,?,?)",
            (body.standard_id, body.scope_material, body.scope_feature, body.clause, params, body.status),
        )
        conn.commit()
        return ok({"id": cur.lastrowid}, "已创建")
    except Exception as exc:
        return fail(f"创建失败: {exc}")
    finally:
        conn.close()


@router.put("/{rid}")
def update_rule(rid: int, body: RuleIn):
    conn = db.get_conn()
    try:
        params = json.dumps(body.params_json, ensure_ascii=False) if body.params_json else None
        conn.execute(
            "UPDATE standard_rule SET standard_id=?, scope_material=?, scope_feature=?, clause=?,"
            " params_json=?, status=?, updated_at=datetime('now') WHERE id=?",
            (body.standard_id, body.scope_material, body.scope_feature, body.clause, params, body.status, rid),
        )
        conn.commit()
        return ok({"id": rid}, "已更新")
    finally:
        conn.close()


@router.delete("/{rid}")
def delete_rule(rid: int):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM standard_rule WHERE id = ?", (rid,))
        conn.commit()
        return ok({"id": rid}, "已删除")
    finally:
        conn.close()