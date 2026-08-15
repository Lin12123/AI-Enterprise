# AI-SW 云平台前端

Vue3 + Vite + Element Plus 单页应用，对接 `cloud/backend` FastAPI 服务（默认端口 8800）。

## 目录结构

```
cloud/frontend/
├── index.html
├── package.json
├── vite.config.js
└── src/
    ├── main.js            # 入口：注册 Pinia / Router / Element Plus
    ├── App.vue            # 顶部导航 + 路由出口
    ├── api/
    │   ├── client.js      # axios 封装，统一处理 {ok,data,message}
    │   └── index.js       # 各业务模块 API 聚合
    ├── router/
    │   └── index.js       # 三个页面路由
    └── views/
        ├── KnowledgeView.vue   # 知识库管理（标准列表 + 导入）
        ├── BaseDataView.vue    # 基础数据（材料 + 模板）
        └── ArtifactsView.vue   # 产物管理（任务 + 文件下载）
```

## 本机启动（需 Windows / 联网环境）

> 本仓库只提交源码骨架，`node_modules` 未安装。首次使用需自行安装依赖。

```bash
cd cloud/frontend
npm install
npm run dev        # 开发服务器，默认 http://localhost:5173
```

开发期通过 Vite 代理免 CORS：所有 `/api/*` 请求转发到 `http://127.0.0.1:8800`，
配置见 [`vite.config.js`](vite.config.js)。**需先启动后端**：

```bash
cd cloud/backend
uvicorn app.main:app --reload --port 8800
```

## 构建

```bash
npm run build      # 产物输出到 dist/
npm run preview    # 本地预览构建结果
```

## 说明

- 统一响应结构 `{ok, data, message}`：`ok=true` 返回 `data`，`ok=false` 抛出 `message`。
- 文件下载走 `GET /api/files/{id}/download`，前端用 `window.open` 直连。
- 若后端端口调整，修改 [`vite.config.js`](vite.config.js) 中的 `proxy.target`。