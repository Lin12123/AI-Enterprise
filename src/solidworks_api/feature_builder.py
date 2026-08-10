"""Feature builder dispatch skeleton."""

from __future__ import annotations

from cad_dsl.featureplan import FeatureOperation


class FeatureBuilder:
    def build_operation(self, operation: FeatureOperation) -> None:
        raise NotImplementedError(f"Feature operation is scaffolded only: {operation.op}")
