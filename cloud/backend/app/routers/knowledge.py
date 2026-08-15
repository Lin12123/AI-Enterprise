"""知识库联动：拉取 + 导入。/api/knowledge

- GET  /api/knowledge/pull   本地服务出图未命中时按 material/feature 拉取匹配规则打包
- POST /api/knowledge/import 上传 Excel/JSON/Word/PDF/图片，解析入库(高置信)或存草稿
"""
import json
import os
import threading
import uuid

from fastapi import APIRouter, UploadFile, File, Form

from app import db
from app.schemas import ok, fail
from app.services import importer

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

# 流式落盘分块大小(1MB)，避免大文件全量入内存
_CHUNK = 1024 * 1024
# 走后台异步抽取的文档类格式(耗时:抽正文 + LLM 推理)
_ASYNC_FMTS = {"docx", "pdf", "png", "jpg", "jpeg", "bmp", "tif", "tiff"}


@router.get("/pull")
def pull(material: str = "", feature: str = "", standard_no: str = ""):
    """按范围返回已发布规则，供本地服务落地缓存。命中为空时 data.hits=[]。"""
    conn = db.get_conn()
    try:
        sql = (
            "SELECT r.*, s.standard_no, s.standard_type, s.version"
            " FROM standard_rule r JOIN standard s ON r.standard_id = s.id"
            " WHERE r.status = 'published'"
        )
        args: list = []
        if material:
            sql += " AND (r.scope_material = ? OR r.scope_material IS NULL OR r.scope_material = '')"
            args.append(material)
        if feature:
            sql += " AND (r.scope_feature = ? OR r.scope_feature IS NULL OR r.scope_feature = '')"
            args.append(feature)
        if standard_no:
            sql += " AND s.standard_no = ?"
            args.append(standard_no)
        rows = conn.execute(sql, args).fetchall()
        hits = []
        for r in rows:
            d = db.row_to_dict(r)
            if d.get("params_json"):
                try:
                    d["params_json"] = json.loads(d["params_json"])
                except (ValueError, TypeError):
                    pass
            hits.append(d)
        return ok({"hits": hits, "count": len(hits)})
    finally:
        conn.close()


@router.post("/import")
async def import_knowledge(
    file: UploadFile = File(...),
    standard_no: str = Form(...),
    standard_type: str = Form(""),
    title: str = Form(""),
    version: str = Form(""),
    source: str = Form("import"),
):
    """导入知识文件。

    Excel/JSON 高置信直接 published(同步)；Word/PDF/图片体量大且需 LLM 抽取，
    这里只做流式落盘 + 登记后立即返回(秒回)，抽取转后台线程执行，前端轮询 /import/status。
    """
    ext = os.path.splitext(file.filename or "")[1].lstrip(".").lower()

    # 原文流式落盘(分块写)，避免大文件全量入内存
    os.makedirs(db.UPLOAD_DIR, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    abs_path = os.path.join(db.UPLOAD_DIR, stored_name)
    try:
        with open(abs_path, "wb") as f:
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as exc:
        return fail(f"文件落盘失败: {exc}")

    is_async = ext in _ASYNC_FMTS

    conn = db.get_conn()
    try:
        # upsert 标准主表
        row = conn.execute(
            "SELECT id FROM standard WHERE standard_no = ? AND IFNULL(version,'') = ?",
            (standard_no, version or ""),
        ).fetchone()
        if row:
            standard_id = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO standard(standard_no, standard_type, title, version, source)"
                " VALUES(?,?,?,?,?)",
                (standard_no, standard_type or None, title or None, version or None, source),
            )
            standard_id = cur.lastrowid

        # 附件溯源登记(带抽取状态)
        cur = conn.execute(
            "INSERT INTO import_attachment(standard_id, file_name, stored_path, fmt, extract_status)"
            " VALUES(?,?,?,?,?)",
            (standard_id, file.filename, stored_name, ext, "pending" if is_async else "done"),
        )
        attachment_id = cur.lastrowid
        conn.commit()
    except Exception as exc:
        conn.close()
        return fail(f"登记失败: {exc}")

    # 文档类：转后台线程异步抽取，立即返回
    if is_async:
        conn.close()
        threading.Thread(
            target=_extract_worker,
            args=(attachment_id, standard_id, ext, abs_path),
            daemon=True,
        ).start()
        return ok(
            {"standard_id": standard_id, "attachment_id": attachment_id,
             "inserted": 0, "high_conf": False, "async": True},
            "文件已上传，正在后台抽取规则，请稍候…",
        )

    # Excel/JSON：同步高置信入库
    try:
        parsed, high_conf = importer.dispatch(ext, abs_path, None)
        inserted = _insert_rules(conn, standard_id, parsed)
        conn.commit()
        msg = "导入完成" if high_conf else f"已抽取 {inserted} 条规则"
        return ok(
            {"standard_id": standard_id, "attachment_id": attachment_id,
             "inserted": inserted, "high_conf": high_conf, "async": False},
            msg,
        )
    except Exception as exc:
        return fail(f"入库失败: {exc}")
    finally:
        conn.close()


def _insert_rules(conn, standard_id: int, parsed: list) -> int:
    """批量写入规则，返回写入条数。"""
    inserted = 0
    for item in parsed:
        params = json.dumps(item.get("params_json") or {}, ensure_ascii=False)
        conn.execute(
            "INSERT INTO standard_rule(standard_id, scope_material, scope_feature, clause, params_json, status)"
            " VALUES(?,?,?,?,?,?)",
            (standard_id, item.get("scope_material"), item.get("scope_feature"),
             item.get("clause"), params, item.get("status", "published")),
        )
        inserted += 1
    return inserted


def _extract_worker(attachment_id: int, standard_id: int, ext: str, abs_path: str) -> None:
    """后台线程：执行文档抽取并写 draft 规则，全程更新 import_attachment 状态。"""
    conn = db.get_conn()
    try:
        conn.execute(
            "UPDATE import_attachment SET extract_status='running' WHERE id=?",
            (attachment_id,),
        )
        conn.commit()

        parsed, _ = importer.dispatch(ext, abs_path, None)
        inserted = _insert_rules(conn, standard_id, parsed)

        if inserted > 0:
            msg = f"已自动抽取 {inserted} 条草稿规则，请人工确认后发布"
        else:
            msg = "已受理并留存原文，未能自动抽取规则(可能是图片或模型不可达)，请人工补录"
        conn.execute(
            "UPDATE import_attachment SET extract_status='done', extract_message=?, extract_count=? WHERE id=?",
            (msg, inserted, attachment_id),
        )
        conn.commit()
    except Exception as exc:
        try:
            conn.execute(
                "UPDATE import_attachment SET extract_status='failed', extract_message=? WHERE id=?",
                (f"抽取失败: {exc}", attachment_id),
            )
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()


@router.get("/import/status")
def import_status(attachment_id: int):
    """查询后台抽取进度，供前端轮询。"""
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT id, standard_id, extract_status, extract_message, extract_count"
            " FROM import_attachment WHERE id=?",
            (attachment_id,),
        ).fetchone()
        if not row:
            return fail("附件不存在")
        return ok({
            "attachment_id": row["id"],
            "standard_id": row["standard_id"],
            "status": row["extract_status"],
            "message": row["extract_message"] or "",
            "inserted": row["extract_count"] or 0,
        })
    finally:
        conn.close()