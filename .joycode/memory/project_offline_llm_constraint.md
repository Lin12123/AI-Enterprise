---
name: 离线 LLM 约束
description: 'AI-Enterprise 客户为内网离线环境,LLM 只能用标准库直连本地 Ollama,禁止安装 openai/httpx 等第三方包'
type: project
---

客户软件运行在**内网离线环境**,无法联网,无法安装任何额外 Python 第三方包(含 `openai`、`httpx`)。本地内网仅允许安装 Ollama,只能通过 Ollama API 调用 LLM。

**Why:** 客户内网无联网条件,pip install 不可用;这是硬性部署约束,非偏好。

**How to apply:**
- 涉及 LLM 调用时,绝不建议或引入 `openai` / `httpx` 等第三方包。
- 本地 provider 已用标准库 `urllib.request` 直连 Ollama 原生端点 `http://localhost:11434/api/chat`,通过内置 `OllamaClient`(在 app/providers/local_provider.py)暴露 OpenAI 兼容接口。方案文档见 docs/local_llm_provider.md 的 "Offline / Air-Gapped Implementation" 一节。
- 部署需设 `AI_SW_LLM_PROVIDER=local`,默认模型 `qwen2.5-coder:7b`。
- 本机(macOS)无 SolidWorks/pytest,验证用 `.venv/bin/python -m unittest`,真机测试在 Windows 端。