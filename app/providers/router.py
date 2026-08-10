"""Provider router for natural-language to FeaturePlan parsing."""

from __future__ import annotations

import os


SUPPORTED_PROVIDERS = {"rule_based", "openai", "local"}


def current_provider_name() -> str:
    provider = os.environ.get("AI_SW_LLM_PROVIDER", "").strip().lower()
    if provider:
        return provider
    if os.environ.get("AI_SW_USE_LLM") == "1":
        return "openai"
    return "rule_based"


def _rule_based(prompt: str) -> dict:
    from app.providers.rule_based_provider import parse_featureplan

    return parse_featureplan(prompt)


def parse_featureplan_with_provider(prompt: str) -> dict:
    provider = current_provider_name()

    if provider == "rule_based":
        return _rule_based(prompt)

    if provider == "local":
        from app.providers.local_provider import LocalProviderOutputError, parse_featureplan

        try:
            return parse_featureplan(prompt)
        except LocalProviderOutputError as exc:
            print(f"Local LLM output invalid after repair; rule_based fallback is not used for semantic parameter completion. Reason: {exc}")
            raise
        except Exception as exc:
            print(f"Local LLM unavailable, fallback to rule_based parser. Reason: {exc}")
            return _rule_based(prompt)

    if provider == "openai":
        from app.providers.openai_provider import parse_featureplan

        try:
            return parse_featureplan(prompt)
        except Exception as exc:
            print(f"OpenAI LLM unavailable, fallback to rule_based parser. Reason: {exc}")
            print("Tip: set AI_SW_LLM_PROVIDER=local to use a local Ollama model when OpenAI quota, billing, or network is unavailable.")
            return _rule_based(prompt)

    print(f"Unknown AI_SW_LLM_PROVIDER={provider}; fallback to rule_based parser.")
    return _rule_based(prompt)
