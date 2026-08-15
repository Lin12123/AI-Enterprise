"""SQLite 连接与建表。

阶段一用标准库 sqlite3 起步(→阶段二迁 PostgreSQL)。
库文件：cloud/backend/data/cloud.db。schema 对齐 docs/cloud_platform_design.md §4。
"""
import os
import sqlite3
from typing import Any

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "cloud.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
STORAGE_DIR = os.path.join(DATA_DIR, "storage")


def get_conn() -> sqlite3.Connection:
    """返回一个开启 Row 工厂与外键约束的连接。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def row_to_dict(row: sqlite3.Row)-> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


_SCHEMA = """
-- 基础数据：材料
CREATE TABLE IF NOT EXISTS material (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    density     REAL,
    remark      TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- 基础数据：图纸/工艺模板
CREATE TABLE IF NOT EXISTS template (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    category    TEXT,
    file_path   TEXT,
    remark      TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- 知识库：标准主表
CREATE TABLE IF NOT EXISTS standard (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_no   TEXT NOT NULL,
    standard_type TEXT,
    title         TEXT,
    version       TEXT,
    source        TEXT,
    status        TEXT DEFAULT 'published',
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(standard_no, version)
);

-- 知识库：标准条目(规则)
CREATE TABLE IF NOT EXISTS standard_rule (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id    INTEGER NOT NULL,
    scope_material TEXT,
    scope_feature  TEXT,
    clause         TEXT,
    params_json    TEXT,
    status         TEXT DEFAULT 'published',
    updated_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(standard_id) REFERENCES standard(id) ON DELETE CASCADE
);

-- 产物：插件任务
CREATE TABLE IF NOT EXISTS task (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_uid     TEXT UNIQUE,
    title        TEXT,
    part_name    TEXT,
    material     TEXT,
    status       TEXT,
    payload_json TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

-- 产物：文件(2D图纸/模型/PDF等)
CREATE TABLE IF NOT EXISTS file (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER,
    file_type   TEXT,
    file_name   TEXT,
    stored_path TEXT,
    size_bytes  INTEGER,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(task_id) REFERENCES task(id) ON DELETE SET NULL
);

-- 导入附件溯源(原始上传文件)
CREATE TABLE IF NOT EXISTS import_attachment (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id INTEGER,
    file_name   TEXT,
    stored_path TEXT,
    fmt         TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(standard_id) REFERENCES standard(id) ON DELETE SET NULL
);
"""


def init_db() -> None:
    """建表并确保数据目录存在。幂等。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(STORAGE_DIR, exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()