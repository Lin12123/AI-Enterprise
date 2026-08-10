import json
import os
from pathlib import Path

from app.openai_config import get_openai_api_key, safe_exception_message
from app.providers.json_utils import extract_json_object, ProviderJsonError
from cad_dsl.featureplan_prompt import build_featureplan_prompt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "src" / "cad_dsl" / "featureplan_schema.json"
DEFAULT_MODEL = "gpt-4.1-mini"


class LlmFeaturePlanError(RuntimeError):
    """Raised when optional LLM parsing cannot produce FeaturePlan v2 JSON."""


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

    raise LlmFeaturePlanError("OpenAI response did not contain JSON text")


def _parse_json(text: str) -> dict:
    try:
        data = extract_json_object(text)
    except (json.JSONDecodeError, ProviderJsonError) as exc:
        raise LlmFeaturePlanError("OpenAI response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise LlmFeaturePlanError("OpenAI response JSON must be an object")
    return data


def parse_featureplan_with_llm(prompt: str) -> dict:
    try:
        api_key = get_openai_api_key()
    except RuntimeError as exc:
        raise LlmFeaturePlanError(str(exc)) from exc

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LlmFeaturePlanError("openai package is not installed") from exc

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.environ.get("AI_SW_OPENAI_MODEL", DEFAULT_MODEL),
            messages=[
                {"role": "system", "content": build_featureplan_prompt()},
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "featureplan_v2",
                    "strict": True,
                    "schema": _load_schema(),
                },
            },
        )
    except Exception as exc:
        raise LlmFeaturePlanError(f"OpenAI request failed: {safe_exception_message(exc)}") from exc

    return _parse_json(_extract_response_text(response))
