"""云平台后端 FastAPI 入口。

定位：独立进程，与内网离线本地服务(service/app/src)解耦，仅通过 REST 通信。
职责：注册路由、启动时建表、统一响应结构。
启动：cd cloud/backend && uvicorn app.main:app --reload --port 8800
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.routers import standards, rules, materials, templates, tasks, files, knowledge


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动时确保 SQLite 建表完成
    db.init_db()
    yield


app = FastAPI(
    title="AI-SW 云平台",
    description="标准知识库 + 插件产物管理（前后端分离，独立进程）",
    version="0.1.0",
    lifespan=lifespan,
)

# 阶段一本机开发放开 CORS，供 Vue3 前端(vite dev server)联调
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(standards.router)
app.include_router(rules.router)
app.include_router(materials.router)
app.include_router(templates.router)
app.include_router(tasks.router)
app.include_router(files.router)
app.include_router(knowledge.router)


@app.get("/api/health")
def health():
    return {"ok": True, "data": {"status": "up"}, "message": ""}