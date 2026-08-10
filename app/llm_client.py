import json
import os
from pathlib import Path

from app.openai_config import get_openai_api_key, safe_exception_message


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = PROJECT_ROOT / "app" / "prompts" / "nl_to_cadplan_lite.md"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "cadplan_lite.schema.json"
DEFAULT_MODEL = "gpt-4.1-mini"


class LlmCadplanError(RuntimeError):
    """Raised when optional LLM parsing cannot produce CADPlan Lite JSON."""


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _extract_response_text(response) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text

    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if content:
            return content

    raise LlmCadplanError("OpenAI response did not contain JSON text")


def _parse_json(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlmCadplanError("OpenAI response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise LlmCadplanError("OpenAI response JSON must be an object")
    return data


def parse_prompt_with_llm(prompt: str) -> dict:
    try:
        api_key = get_openai_api_key()
    except RuntimeError as exc:
        raise LlmCadplanError(str(exc)) from exc

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LlmCadplanError("openai package is not installed") from exc

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.environ.get("AI_SW_OPENAI_MODEL", DEFAULT_MODEL),
            messages=[
                {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "cadplan_lite",
                    "strict": True,
                    "schema": _load_schema(),
                },
            },
        )
    except Exception as exc:
        raise LlmCadplanError(f"OpenAI request failed: {safe_exception_message(exc)}") from exc

    return _parse_json(_extract_response_text(response))
