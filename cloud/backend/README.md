# AI-SW 云平台后端（P0 骨架）

FastAPI + SQLite 独立进程，与离线服务（`service/`、`app/`、`src/`）**物理隔离**。
本目录可自由使用第三方库；**切勿**把 `fastapi` 等依赖装进离线侧环境。

## 目录结构

```
cloud/backend/
├── app/
│   ├── main.py          # FastAPI 入口，注册 7 个路由 + /api/health
│   ├── db.py            # SQLite 连接 + 建表 + init_db
│   ├── schemas.py       # Pydantic 请求模型 + ok()/fail() 统一响应
│   ├── routers/         # standards / rules / materials / templates / tasks / files / knowledge
│   └── services/        # importer 导入解析（Excel/JSON 高置信）
├── data/                # 运行时自动创建：cloud.db / uploads / storage
└── requirements.txt
```

## 环境准备（在 Windows 上真跑）

```bash
cd cloud/backend
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 启动

```bash
uvicorn app.main:app --reload --port 8800
```

- 服务地址：`http://127.0.0.1:8800`
- 健康检查：`GET http://127.0.0.1:8800/api/health`
- 交互文档：`http://127.0.0.1:8800/docs`

首次启动会自动执行 `init_db()`：建表 + 创建 `data/`、`data/uploads`、`data/storage` 目录，幂等安全。

## 统一响应结构

所有接口返回：

```json
{ "ok": true, "data": {}, "message": "" }
```

失败时 `ok=false`，`message` 说明原因。

## REST 端点概览

| 资源 | 前缀 | 说明 |
| --- | --- | --- |
| 标准主表 | `/api/standards` | CRUD，支持 keyword/status 过滤 |
| 标准条目 | `/api/rules` | CRUD，params_json 结构化 |
| 材料 | `/api/materials` | CRUD |
| 模板 | `/api/templates` | CRUD，按 category 过滤 |
| 任务 | `/api/tasks` | 插件出图上报，详情联查 files |
| 文件 | `/api/files` | upload/download，本地存储 |
| 知识联动 | `/api/knowledge` | `pull` 拉取规则、`import` 导入知识 |

### 知识拉取（供本地出图服务）

```
GET /api/knowledge/pull?material=Q235&feature=hole&standard_no=GB/T 1804
```

仅返回 `status='published'` 的规则，本地服务落地缓存后重试出图。

### 知识导入（分级）

```
POST /api/knowledge/import   (multipart)
  file, standard_no, standard_type, title, version, source
```

- **Excel / JSON**：高置信，直接解析入库为 `published`
- **Word / PDF / 图片**：阶段一仅受理并存原文附件溯源，规则抽取（python-docx / pdfplumber / OCR + LLM）留待 K2 阶段

## 数据存储

- 数据库：`data/cloud.db`（SQLite；后续可迁移 PostgreSQL）
- 导入原文附件：`data/uploads/`
- 产物文件：`data/storage/`（DB 仅存相对路径引用）

## 注意

- 本机 macOS 未安装 FastAPI，仅能 `python3 -m py_compile` 做语法检查，真跑需在 Windows 建 venv。
- CORS 已全放开（`allow_origins=["*"]`），供前端 Vue3 联调，上云前需收紧。