"""JSON cleanup helpers for LLM provider responses."""

from __future__ import annotations

import json
import re
from typing import Any


class ProviderJsonError(RuntimeError):
    """Raised when provider text cannot be converted into a JSON object."""


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProviderJsonError("LLM response was not valid FeaturePlan JSON") from exc
    if not isinstance(data, dict):
        raise ProviderJsonError("LLM response JSON must be an object")
    return data
