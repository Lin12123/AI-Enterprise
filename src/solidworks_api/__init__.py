"""Fixed SOLIDWORKS API Executor skeleton.

This package intentionally contains no automatic SOLIDWORKS startup behavior.
Real API calls will be added only after FeaturePlan policy validation and a
fixed executor boundary are complete.
"""

from .executor import SolidWorksApiExecutor
from .results import ExecutionResult, OperationResult

__all__ = ["ExecutionResult", "OperationResult", "SolidWorksApiExecutor"]
