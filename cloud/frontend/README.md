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
    ├── App.vue            # ThinkForm 布局：顶栏 + 侧边栏 + 路由出口
    ├── api/
    │   ├── client.js      # axios 封装，统一处理 {ok,data,message}
    │   ├── index.js       # 各业务模块 API 聚合（真实接口 + 假数据封装）
    │   └── mock.js        # 假数据源（总览 / 项目 / 插件 / 知识库分类）
    ├── styles/
    │   └── theme.css      # ThinkForm 公共样式（tf-page/tf-card/tf-grid 等）
    ├── router/
    │   └── index.js       # 五模块路由（懒加载）
    └── views/
        ├── OverviewView.vue    # ① 企业运营总览（指标 / 待审批 / 覆盖率）
        ├── ProjectsView.vue    # ② 项目图纸管理（卡片 + 搜索 + 启用禁用）
        ├── KnowledgeView.vue    # ③ 知识库管理（三分类 + 发布状态 + 导入）
        ├── ModelsView.vue      # ④ 模型管理（占位，本地模型）
        └── PluginsView.vue     # ⑤ 插件管理（Manifest / SBOM / 采用指标）
```

## 本机启动（需 Node ≥ 18 环境）

> 本仓库只提交源码骨架，`node_modules` 未安装（已被 `.gitignore` 排除）。
> Vite 5 要求 **Node.js ≥ 18**（低版本会报 `??=` 语法错误）。
> 在 Windows 上首次使用需自行安装 Node 18/20 LTS 并安装依赖（Mac 的 `node_modules` 不能跨平台拷贝）。

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