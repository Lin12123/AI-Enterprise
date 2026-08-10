"""Natural language -> FeaturePlan v2 parser for API Executor mode."""

from __future__ import annotations

from app.featureplan_llm_client import LlmFeaturePlanError
from app.providers.router import parse_featureplan_with_provider
from cad_dsl.featureplan import FeaturePlan


def parse_prompt_to_featureplan(prompt: str) -> FeaturePlan | None:
    """Return a provider-generated FeaturePlan.

    Provider failures are handled by the router, which falls back to rule_based
    parsing. The returned FeaturePlan still goes through Policy Engine before
    any executor can run.
    """

    try:
        data = parse_featureplan_with_provider(prompt)
    except Exception as exc:
        raise LlmFeaturePlanError(str(exc)) from exc
    return FeaturePlan.from_dict(data)


__all__ = ["LlmFeaturePlanError", "parse_prompt_to_featureplan"]
