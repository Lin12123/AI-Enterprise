"""产物：文件上传/下载/列表路由。/api/files

阶段一采用本地文件存储(路径引用)，文件落地 data/storage，DB 只存元数据+相对路径。
"""
import os
import uuid

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse

from app import db
from app.schemas import ok, fail

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("")
def list_files(task_id: int = 0):
    conn = db.get_conn()
    try:
        if task_id:
            rows = conn.execute(
                "SELECT * FROM file WHERE task_id = ? ORDER BY created_at DESC", (task_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM file ORDER BY created_at DESC").fetchall()
        return ok([db.row_to_dict(r) for r in rows])
    finally:
        conn.close()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    task_id: int = Form(0),
    file_type: str = Form(""),
):
    """接收产物文件(2D图纸/PDF/模型)，落地本地 storage 并登记。"""
    ext = os.path.splitext(file.filename or "")[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    abs_path = os.path.join(db.STORAGE_DIR, stored_name)
    os.makedirs(db.STORAGE_DIR, exist_ok=True)
    content = await file.read()
    with open(abs_path, "wb") as f:
        f.write(content)

    conn = db.get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO file(task_id, file_type, file_name, stored_path, size_bytes)"
            " VALUES(?,?,?,?,?)",
            (task_id or None, file_type, file.filename, stored_name, len(content)),
        )
        conn.commit()
        return ok({"id": cur.lastrowid, "stored_path": stored_name}, "上传成功")
    except Exception as exc:
        return fail(f"登记失败: {exc}")
    finally:
        conn.close()


@router.get("/{fid}/download")
def download_file(fid: int):
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM file WHERE id = ?", (fid,)).fetchone()
        if not row:
            return fail("文件不存在")
        abs_path = os.path.join(db.STORAGE_DIR, row["stored_path"])
        if not os.path.exists(abs_path):
            return fail("物理文件缺失")
        return FileResponse(abs_path, filename=row["file_name"] or row["stored_path"])
    finally:
        conn.close()