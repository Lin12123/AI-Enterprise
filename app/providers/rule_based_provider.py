"""Rule-based provider that adapts CADPlan Lite into FeaturePlan v2."""

from __future__ import annotations

from app.llm_parser import parse_prompt_with_rules
from app.validator import validate_cadplan
from cad_dsl.cadplan_adapter import cadplan_to_featureplan


def parse_featureplan(prompt: str) -> dict:
    print("LLM provider: rule_based")
    cadplan = validate_cadplan(parse_prompt_with_rules(prompt))
    return cadplan_to_featureplan(cadplan).to_dict()
