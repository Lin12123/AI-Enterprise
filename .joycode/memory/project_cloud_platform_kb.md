---
name: 云平台与知识库需求决策
description: AI-Enterprise 进阶出图的云平台+本地知识库架构已拍板的关键决策
type: project
---

进阶版 2D 出图引入"本地知识库(第一优先)+云平台(按需拉取)"两层，为决策引擎提供标准标注参数。已拍板决策：

- **云平台部署**：先本地部署(Windows 本机，尚未开发)，未来可能私有云 / 公网 SaaS；客户端用可配置 base_url + 标准库 urllib 屏蔽差异。
- **云平台技术栈(已定)**：后端 FastAPI、独立进程/独立端口(与内网本地服务解耦，不受禁第三方包约束)；数据库 SQLite→未来 PostgreSQL；前端 Vue3+Vite SPA。已否决 Java+MySQL+中间件方案(阶段一本机单人过重、三语言运维成本高、文档解析+Ollama LLM 抽取 Python 生态更强)；未来若客户强制 Java 可只重写后端，契约不变。
- **知识库初始内容**：由客户提供，导入支持 PDF/图片/Word/Excel/JSON(Excel/JSON 高置信直接入库，Word/PDF/图片抽取走草稿+人工确认)。
- **未命中策略**：硬阻断——不兜底出图，返回 need_fetch 要求先补齐标准。
- **工程结构(已定)**：云平台在现有 Git 仓新建 cloud/ 子目录(cloud/backend FastAPI + cloud/frontend Vue3)，拥有独立 venv/requirements/package.json，与内网离线服务(service/app/src)物理隔离——第三方包绝不进离线服务；独立 uvicorn 进程+独立端口；未来可整体拆为独立仓。
- **云平台需求**：前后端分离 + 基础数据管理(材料/模板) + 知识库管理 + 插件产物管理(任务/文件/2D图纸)。

**Why:** 客户内网离线，标准知识需集中维护且插件出图强依赖；产物需可追溯。
**How to apply:** 设计文档见 docs/cloud_platform_design.md 与 docs/drawing_enhancement_design.md 第6.5节；本地服务对接云平台仍受"禁第三方包"约束，云平台(cloud/)为独立组件可自由用第三方库。仅剩业务开放问题 C3(知识粒度)、C4(产物存储方式)待客户拍板。