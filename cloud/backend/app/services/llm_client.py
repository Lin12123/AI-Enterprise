"""云平台侧 LLM 客户端：直连本地 Ollama 原生 /api/chat。

设计说明
--------
- 云平台(cloud/)为独立进程，不受内网离线服务"禁第三方包"约束；但此处仍用标准库
  urllib，避免为一次 HTTP 调用引入额外依赖，且与内网侧 provider 实现思路一致，便于统一部署。
- 默认对接与内网侧相同的本地 Ollama(qwen2.5-coder:7b)；地址/模型可用环境变量覆盖：
    AI_CLOUD_LLM_BASE_URL   默认 http://localhost:11434
    AI_CLOUD_LLM_MODEL      默认 qwen2.5-coder:7b
    AI_CLOUD_LLM_TIMEOUT    默认 120(秒，文档抽取可能较慢)
- 提供 chat_json()：强制模型输出 JSON(Ollama format=json)，并做一层稳健解析。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_TIMEOUT = 120


def _base_url() -> str:
    return (os.environ.get("AI_CLOUD_LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def _model() -> str:
    return os.environ.get("AI_CLOUD_LLM_MODEL") or DEFAULT_MODEL


def _timeout() -> int:
    raw = os.environ.get("AI_CLOUD_LLM_TIMEOUT")
    if not raw:
        return DEFAULT_TIMEOUT
    try:
        return max(5, int(raw))
    except (ValueError, TypeError):
        return DEFAULT_TIMEOUT


class LlmUnavailable(RuntimeError):
    """Ollama 不可达或返回异常时抛出，供上层降级处理。"""


def chat_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """调用本地 Ollama /api/chat，要求模型输出 JSON，返回解析后的 dict。

    失败(网络不通/超时/非 JSON)时抛 LlmUnavailable，由调用方决定降级(如仅存原文草稿)。
    """
    url = f"{_base_url()}/api/chat"
    body = {
        "model": _model(),
        "stream": False,
        "format": "json",  # 让 Ollama 约束输出为合法 JSON
        "options": {"temperature": 0.1},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=_timeout()) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LlmUnavailable(f"Ollama 不可达: {exc}") from exc

    try:
        envelope = json.loads(raw)
        content = (envelope.get("message") or {}).get("content", "")
    except (ValueError, TypeError) as exc:
        raise LlmUnavailable(f"Ollama 响应体解析失败: {exc}") from exc

    parsed = _loads_lenient(content)
    if parsed is None:
        raise LlmUnavailable("模型输出不是可解析的 JSON")
    return parsed


def _loads_lenient(text: str) -> dict[str, Any] | None:
    """稳健解析模型输出的 JSON：直接解析失败时，尝试截取第一个 {...} 片段。"""
    text = (text or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {"rules": obj}
    except (ValueError, TypeError):
        pass
    # 兜底：截取最外层大括号片段再试一次
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except (ValueError, TypeError):
            return None
    return None


def is_available() -> bool:
    """轻量探活：GET Ollama 根路径，判断本地服务是否可达。"""
    try:
        with urllib.request.urlopen(_base_url(), timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False