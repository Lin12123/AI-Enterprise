"""OpenAI API key handling helpers.

This module never prints or logs the complete API key. Callers should use
``get_openai_api_key`` only to pass the value directly into the OpenAI SDK.
"""

from __future__ import annotations

import os
import re


KEY_ENV_NAME = "OPENAI_API_KEY"
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(OPENAI_API_KEY\s*=\s*)\S+", re.IGNORECASE),
    re.compile(r"(AI_SW_LOCAL_LLM_API_KEY\s*=\s*)\S+", re.IGNORECASE),
    re.compile(r"(api_key\s*=\s*)\S+", re.IGNORECASE),
    re.compile(r"(Authorization:\s*Bearer\s+)\S+", re.IGNORECASE),
)


def get_openai_api_key() -> str:
    """Return the API key from the environment or raise a user-facing error."""

    api_key = os.environ.get(KEY_ENV_NAME, "").strip()
    if not api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY。请先设置环境变量 OPENAI_API_KEY。")
    return api_key


def mask_api_key(api_key: str | None) -> str:
    """Return a display-safe key state using first 6 and last 4 characters."""

    if not api_key:
        return "not set"
    if len(api_key) <= 10:
        return "***"
    return f"{api_key[:6]}***{api_key[-4:]}"


def redact_secrets(text: str) -> str:
    """Redact API-key-like values from text before it reaches logs/errors."""

    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}[redacted]" if match.groups() else "[redacted]", redacted)
    return redacted


def safe_exception_message(exc: Exception) -> str:
    detail = str(exc).strip() or "no detail"
    return f"{type(exc).__name__}: {redact_secrets(detail)}"
