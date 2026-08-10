"""Cloud OpenAI provider for FeaturePlan generation."""

from __future__ import annotations

from app.featureplan_llm_client import LlmFeaturePlanError, parse_featureplan_with_llm


class OpenAiProviderError(RuntimeError):
    """Raised when OpenAI cannot produce a FeaturePlan JSON object."""


def parse_featureplan(prompt: str) -> dict:
    print("LLM provider: openai")
    try:
        return parse_featureplan_with_llm(prompt)
    except LlmFeaturePlanError as exc:
        raise OpenAiProviderError(str(exc)) from exc
