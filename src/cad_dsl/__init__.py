"""FeaturePlan v2 CAD DSL package.

This package contains declarative plan structures only. It must not execute
SOLIDWORKS, macros, shell commands, or generated runtime code.
"""

from .featureplan import FeatureOperation, FeaturePlan, PlanMetadata
from .feature_registry import FeatureDefinition, FeatureRegistry, default_registry
from .cadplan_adapter import cadplan_to_featureplan

__all__ = [
    "FeatureDefinition",
    "FeatureOperation",
    "FeaturePlan",
    "FeatureRegistry",
    "PlanMetadata",
    "cadplan_to_featureplan",
    "default_registry",
]
