# 云平台开发方案（AI-SW 标准知识与产物管理平台）

> 评审稿。定位：为 SolidWorks 插件 + 本地 Python 服务提供**标准知识库**与**插件产物**的集中管理。
> 关联文档：进阶出图与本地知识库架构见 [`docs/drawing_enhancement_design.md`](docs/drawing_enhancement_design.md) 第 6.5 节。

## 1. 目标与范围

围绕两条主线：
1. **知识库管理**：由客户维护行业标准（GB/T）、企业标准（Q/HW）的结构化标注参数，供插件出图时拉取。
2. **产物管理**：集中管理插件生成的零件任务、模型文件、2D 图纸等产物，可追溯、可检索、可下载。

平台形态演进（对齐已拍板决策）：
- **阶段一（当前）**：**本地部署（Windows 本机）**，尚未开发。前后端分离但单机运行，插件/本地服务通过 `http://127.0.0.1:<port>` 访问。
- **阶段二（未来）**：私有云 / 公网 SaaS。仅改部署与鉴权，接口契约不变。

设计原则：
- **前后端分离**：后端提供 REST API，前端为独立 SPA。
- **部署无关**：客户端只认可配置的 `base_url`，屏蔽本地/私有云/SaaS 差异。
- **离线约束延续**：本地 Python 服务侧对接云平台只用标准库 `urllib.request`，禁第三方包。
- **契约先行**：先定 API 契约，前后端并行开发。

## 2. 总体架构

```
┌───────────────────────────────────────────────┐
│  SolidWorks 插件 (C#)                           │
│    出图/建模 → 本地 Python 服务                  │
└───────────────┬───────────────────────────────┘
                │ localhost HTTP
┌───────────────▼───────────────────────────────┐
│  本地 Python 服务 (http_service.py, 标准库)      │
│    - 本地知识库缓存 (sqlite3)                    │
│    - cloud_client (urllib) ── 未命中/上报产物 ──┐│
└───────────────────────────────────────────────┘│
                                                  │ REST (base_url 可配置)
┌─────────────────────────────────────────────▼─┐
│  云平台后端 (API 服务)                           │
│    ├─ 知识库服务  standards / rules              │
│    ├─ 产物服务    tasks / files / drawings       │
│    ├─ 基础数据    materials / templates / users  │
│    └─ 对象存储    (文件/图纸二进制)               │
├─────────────────────────────────────────────────┤
│  云平台前端 (SPA)  管理后台                       │
│    知识库管理 / 基础数据管理 / 产物浏览            │
└─────────────────────────────────────────────────┘
```

## 3. 技术选型（已确认）

| 层 | 阶段一（本地） | 说明 |
| --- | --- | --- |
| 后端 | **FastAPI（独立进程）** | 已确认：云平台为**独立进程/独立端口**，与内网本地 Python 服务解耦，不受"禁第三方包"约束 |
| 数据库 | SQLite | 本机单文件，未来迁 PostgreSQL |
| 对象存储 | 本地文件目录 | 未来迁 MinIO / S3 |
| 前端 | **Vue3 + Vite** | 独立 SPA，构建产物静态托管 |
| 鉴权 | 阶段一免鉴权(本机) → 阶段二 Token/JWT | Token 不落库明文 |
| 文档解析 | 按导入格式选库(见 §5.4) | PDF/图片/Word/Excel/JSON 解析 |

> **C1/C2 已确认**：后端用 **FastAPI**、以**独立进程**部署。约束边界——"禁第三方包"仅适用于**内网离线的本地 Python 服务**（`service/`、`app/`、`src/`）；云平台是独立组件，可自由用第三方框架与解析库。两者仅通过 REST（可配置 base_url）通信。

### 3.1 选型理由（Python + FastAPI，而非 Java 方案）
1. **复用现有技术栈**：本地服务全为 Python、插件为 C#，选 Python 保持"Python + C#"两语言；若引入 Java + MySQL + 中间件会变成三语言 + 重运维，阶段一（本机单人、未开发）用不上。
2. **知识导入是核心难点，Python 生态最强**：PDF/Word/图片解析(pdfplumber/python-docx/OCR)与 **LLM 辅助抽取可直接复用现有 Ollama** 客户端；Java 方案往往需另起 Python 微服务做解析。
3. **阶段一交付速度快一个数量级**：单进程 + 单文件 SQLite + uvicorn 当天可跑通；Java 需先搭 MySQL/中间件/Spring 工程。
4. **不锁死未来**：C2 已定"独立进程 + REST 契约"，规模上来后可平滑迁 PostgreSQL、按需加 Redis/MQ；若客户强制 Java，可**只重写后端**而前端 Vue 与 C# 插件完全不动。

### 3.2 演进路径
- **阶段一**：FastAPI + SQLite + 本地文件存储 + Vue3，本机单进程。
- **阶段二**：SQLite → PostgreSQL；本地目录 → MinIO/S3；加 Token/JWT + 用户角色；私有云 / SaaS 部署。
- **阶段三（按需）**：高并发/多租户时引入 Redis 缓存、消息队列；如客户强制企业 Java 栈，仅后端重写、契约不变。

### 3.3 工程结构与隔离（已确认：现有仓新建 cloud/ 子目录）

云平台**不塞进现有本地服务**，而是在现有 Git 仓新建独立 `cloud/` 子目录，拥有**独立 venv / requirements / package.json**，与内网离线服务物理隔离。

```
AI-Enterprise/
├── service/ app/ src/     ← 现有：内网离线本地服务（禁第三方包，只用标准库）
├── plugin/                ← 现有：C# 插件
├── cloud/                 ← 新建：云平台（独立进程，可自由用第三方库）
│   ├── backend/           ← FastAPI + SQLite
│   │   ├── requirements.txt   （独立依赖，不影响离线服务）
│   │   ├── app/
│   │   │   ├── main.py        FastAPI 入口 / 路由注册
│   │   │   ├── db.py          sqlite3 连接与建表
│   │   │   ├── models/        知识库 / 产物 / 基础数据 ORM 或 dataclass
│   │   │   ├── routers/       standards / rules / tasks / files / materials
│   │   │   ├── services/      导入解析(pdf/word/excel/ocr)、知识拉取打包
│   │   │   └── storage/       本地对象存储目录封装
│   │   └── data/              SQLite 库文件 + 上传原文附件
│   └── frontend/          ← Vue3 + Vite（独立 package.json）
│       └── src/               知识库管理 / 基础数据 / 产物浏览
└── docs/
```

隔离要点：
- **依赖隔离**：`cloud/backend` 用独立 venv，FastAPI/pdfplumber/OCR 等第三方包只装在此，**绝不进入** `service/app/src`，保护客户内网离线运行。
- **进程隔离**：独立 `uvicorn` 进程 + 独立端口，对齐 C2；与本地服务仅通过 REST(可配置 base_url) 通信。
- **未来可拆仓**：需独立 CI/CD 或异地部署时，`cloud/` 可整体迁出为独立 Git 仓，代码组织不变。

## 4. 数据模型（核心表）

### 4.1 基础数据
```
material    材料: id, code, name, category(steel/aluminum...), density, remark
template    图纸模板: id, name, drwdot_path/blob, projection(1st/3rd), paper, standard_no
user        用户(阶段二): id, name, role(admin/editor/viewer), token_hash
```

### 4.2 知识库
```
standard        标准: id, standard_no, standard_type(industry/enterprise),
                      name, version, status(draft/published), source(manual/import)
standard_rule   规则条目(结构化标注参数):
                id, standard_id, scope_material, scope_feature, clause,
                params_json{tolerance_grade, surface_ra, tech_note, template_hint},
                updated_at
```
> 与本地知识库 `standard_rules` schema 对齐，云端为主库，本地为按需缓存。

### 4.3 插件产物
```
task     任务: id, source(plugin), type(model/drawing), title, status,
              created_by, created_at, meta_json(零件/出图参数)
file     文件: id, task_id, kind(sldprt/slddrw/pdf/dwg/preview),
              filename, size, storage_uri, checksum, created_at
```

## 5. REST API 契约（云平台后端）

统一响应：`{ "ok": bool, "data": ..., "message": str }`；分页 `?page=&size=`。

### 5.1 知识库
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/standards` | 标准列表（可按 type/status 过滤） |
| POST | `/api/standards` | 新增标准（客户录入初始内容） |
| PUT | `/api/standards/{id}` | 编辑/发布标准 |
| POST | `/api/standards/import` | 批量导入，支持 PDF/图片/Word/Excel/JSON（详见 §5.4），客户提供初始内容主入口 |
| GET | `/api/rules` | 规则条目查询（material/feature/standard 过滤） |
| POST/PUT/DELETE | `/api/rules[/{id}]` | 规则条目增改删 |
| GET | `/api/knowledge/pull` | **供本地服务按需拉取**：入参 `standard_no/feature` 列表，返回匹配 `standard_rule` 打包 |

### 5.2 产物管理
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/tasks` | 插件/本地服务上报任务（建模/出图） |
| GET | `/api/tasks` | 任务列表（按 type/status/时间过滤） |
| GET | `/api/tasks/{id}` | 任务详情 + 关联文件 |
| POST | `/api/files` | 上传产物文件（multipart，或先拿预签名 URL） |
| GET | `/api/files/{id}/download` | 下载产物 |

### 5.3 基础数据
`GET/POST/PUT/DELETE /api/materials`、`/api/templates`；阶段二增 `/api/users`、`/api/auth/login`。

### 5.4 知识导入 — 多格式支持（已确认）

`POST /api/standards/import` 支持上传常规文档，服务端**解析→抽取→转结构化 `standard_rule` 草稿→人工确认发布**。

| 格式 | 解析方案（FastAPI 侧，可用第三方库） | 抽取策略 |
| --- | --- | --- |
| **Excel** (.xlsx) | `openpyxl` / `pandas` | **首选**：按约定列模板直接映射为规则条目，命中率最高 |
| **JSON** | 标准库 | 直接按 schema 导入，供系统间对接 |
| **Word** (.docx) | `python-docx` | 提取正文/表格 → 规则草稿，需人工校对 |
| **PDF** | `pdfplumber` / `PyMuPDF` | 文字层直接提取；扫描件走 OCR |
| **图片** (png/jpg) | OCR（`pytesseract` 等） | 扫描标准页 → 文本 → 草稿，需人工校对 |

导入流程：
```
上传文件 → 存对象存储 → 按类型解析 → 抽取候选规则(status=draft)
        → 前端"导入向导"人工核对/补全 → 批量发布(status=published)
```
- **原文留存**：上传的 PDF/图片/Word 作为标准附件保存，规则条目 `source_file_id` 关联，便于溯源核对。
- **可靠性分级**：Excel/JSON 视为高置信直接入库；Word/PDF/图片抽取结果一律先 `draft`，必须人工确认后才 `published`（避免解析噪声污染出图参数）。
- **可选 LLM 辅助抽取**：Word/PDF 文本可选调 LLM 结构化为规则条目（云平台侧不受离线约束），仍需人工确认。

## 6. 前端模块（SPA 管理后台）

1. **知识库管理**：标准列表/编辑/发布、规则条目表格编辑、**批量导入向导**（客户提供初始内容的核心入口）、版本管理。
2. **基础数据管理**：材料库、模板库（上传 `.drwdot`、设投影法/图幅）。
3. **产物管理**：任务列表（建模/出图）、任务详情、关联文件预览与下载、按材料/时间检索。
4. **系统（阶段二）**：用户与角色、鉴权、审计日志。

## 7. 与本地服务/插件的联动

- **拉取标准**：本地 `cloud_client.fetch()` → `GET /api/knowledge/pull` → 写入本地 `standard_rules` 缓存（对应出图未命中→硬阻断→提示拉取流程）。
- **上报产物**：本地服务在建模/出图成功后 `POST /api/tasks` + `POST /api/files` 上报（阶段一可先本地记录，联通后补传，避免阻塞出图）。
- **配置**：`base_url`、`token` 走 `app/config.py` / 环境变量，Token 不落库不入日志。

## 8. 分阶段开发计划

- **P0 契约与骨架**：定 REST 契约 + 数据模型；后端建 SQLite schema；前端脚手架（路由/布局）。
- **P1 知识库管理闭环**：标准/规则 CRUD + 批量导入 + `GET /api/knowledge/pull`；打通本地服务按需拉取。
- **P2 产物管理**：任务/文件上报与浏览；本地服务出图成功后上报。
- **P3 基础数据**：材料/模板管理。
- **P4 上云与鉴权（未来）**：迁 PostgreSQL/对象存储、用户角色、Token/JWT、私有云或 SaaS 部署。

## 9. 开放问题（部分已拍板）

- **C1 已定**：云平台后端用 **FastAPI**（第三方框架），仅约束内网本地服务禁第三方包。
- **C2 已定**：云平台为**独立进程 / 独立端口**，与本地 Python 服务通过 REST 通信。
- **C5 已定**：初始内容导入支持 **PDF / 图片 / Word / Excel / JSON**（见 §5.4），Excel/JSON 高置信入库，其余走草稿+人工确认。
- **C3 待定**：知识粒度——录入是否只维护结构化标注参数条目（推荐），不常驻整份标准原文（原文仅作附件溯源）？
- **C4 待定**：产物二进制走对象存储集中管理，还是仅存本地路径引用（文件已在 `workspace/outputs`）？