"""Prompt summary generated from Policy Engine constants."""

from __future__ import annotations

from functools import lru_cache

from policy.file_safety_rules import FORBIDDEN_KEYS
from policy.geometry_rules import (
    ALLOWED_CHAMFER_TARGETS,
    ALLOWED_CUSTOM_PROPERTIES,
    ALLOWED_MIRROR_PLANES,
    ALLOWED_NAMED_DIMENSIONS,
    ALLOWED_PATTERN_DIRECTIONS,
    ALLOWED_PLANES,
    ALLOWED_REFERENCE_PLANES,
    MAX_DIMENSION_MM,
    MAX_PATTERN_COUNT,
)


@lru_cache(maxsize=1)
def build_policy_prompt_summary() -> str:
    """Return a compact LLM-facing summary of hard Policy Engine constraints."""

    return "\n".join(
        [
            "Policy Engine constraints to satisfy on the first attempt:",
            "- Top-level protocol: version='2.0', unit='mm', document_type='part', non-empty part_name, at least one operation.",
            "- Every operation must have unique id, op, params, and op must be implemented in the Feature Registry.",
            f"- Forbidden fields at any JSON depth: {_csv(FORBIDDEN_KEYS)}.",
            "- outputs may contain only boolean save_sldprt, export_step, capture_png; user output directories or paths are forbidden.",
            f"- Numeric dimensions must be positive where required and no larger than {MAX_DIMENSION_MM:g} mm.",
            f"- Planes/faces must use controlled selectors: {_csv(ALLOWED_PLANES)}.",
            "- create_sketch plane must be exactly one of Top, Front, Right, top_face. Use Top for the initial base sketch and top_face for sketches on an existing top face.",
            "- create_through_hole plane must be exactly one of Top, Front, Right, top_face. Use top_face for holes on the top surface of an existing solid.",
            "- Do not output plane values such as Top Plane, top, upper_face, top plane, or translated plane display names; convert them to the controlled selectors above.",
            "- Build a completed base solid before cuts, holes, fillets, chamfers, patterns, mirrors, or output operations.",
            "- For centered rectangular bases, base center is [0,0]; keep holes, slots, and pockets within the base boundary.",
            "- For edge-distance hole intent, convert edge distance to center coordinates and mark computed center as inferred.",
            "- cut_center_hole target='boss' requires a preceding create_center_boss; otherwise use target='base' or create_through_hole.",
            f"- Pattern direction must be one of {_csv(ALLOWED_PATTERN_DIRECTIONS)}; pattern count must be >1 and <= {MAX_PATTERN_COUNT}; spacing must be >0.",
            f"- Chamfer target must be one of {_csv(ALLOWED_CHAMFER_TARGETS)}; chamfer distance >0 and angle must be >0 and <90.",
            f"- Mirror plane must be one of {_csv(ALLOWED_MIRROR_PLANES)}.",
            f"- Reference planes must be one of {_csv(ALLOWED_REFERENCE_PLANES)}; reference names must be explicit, not auto/default/any/some/unknown.",
            "- Material must resolve to the project-local official SOLIDWORKS material catalog; prefer official material names such as 6061 Alloy or AISI 304.",
            f"- Custom property key must be one of {_csv(ALLOWED_CUSTOM_PROPERTIES)}.",
            f"- modify_named_dimension dimension_name must be one of {_csv(ALLOWED_NAMED_DIMENSIONS)} and value must be >0.",
        ]
    )


def _csv(values: set[str]) -> str:
    return ", ".join(sorted(values))
