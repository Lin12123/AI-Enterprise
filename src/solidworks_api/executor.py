"""Fixed FeaturePlan -> Policy Engine -> API Executor boundary."""

from __future__ import annotations

from typing import Any, Mapping

from cad_dsl.featureplan import FeaturePlan
from cad_dsl.semantic_binding import canonicalize_featureplan_structure
from policy.policy_engine import PolicyEngine
from solidworks_api.model_builder import ModelBuilder
from solidworks_api.operation_planner import plan_operations
from solidworks_api.output_manager import plan_output_paths
from solidworks_api.results import ExecutionResult, OperationResult
from solidworks_api.session import SolidWorksSession


OUTPUT_OPERATIONS = {"save_sldprt", "export_step", "capture_png"}


class SolidWorksApiExecutor:
    """Executor skeleton.

    The executor validates plans and can produce a dry-run trace. It does not
    connect to SOLIDWORKS or execute COM calls in this stage.
    """

    def __init__(
        self,
        policy_engine: PolicyEngine | None = None,
        session: SolidWorksSession | None = None,
        model_builder: ModelBuilder | None = None,
    ) -> None:
        self.policy_engine = policy_engine or PolicyEngine()
        self.session = session or SolidWorksSession()
        self.model_builder = model_builder or ModelBuilder()

    def validate(self, plan_data: Mapping[str, Any] | FeaturePlan):
        return self.policy_engine.validate(plan_data)

    def dry_run(self, plan_data: Mapping[str, Any] | FeaturePlan) -> ExecutionResult:
        plan = plan_data if isinstance(plan_data, FeaturePlan) else FeaturePlan.from_dict(canonicalize_featureplan_structure(dict(plan_data)))
        policy_result = self.policy_engine.validate(plan)
        if not policy_result.allowed:
            return ExecutionResult(
                status="blocked",
                message="FeaturePlan 被 Policy Engine 拒绝",
                operations=tuple(
                    OperationResult(v.operation_id, "policy", "blocked", f"{v.code}: {v.message}")
                    for v in policy_result.violations
                ),
            )
        try:
            planned = plan_operations(plan)
        except Exception as exc:
            return ExecutionResult(
                status="blocked",
                message=f"FeaturePlan operation planning failed: {exc}",
                operations=(OperationResult("", "planning", "blocked", str(exc)),),
            )
        return ExecutionResult(
            status="dry_run",
            message="FeaturePlan 已验证；dry_run 不连接 SOLIDWORKS，只输出执行计划。",
            operations=tuple(
                OperationResult(operation.id, operation.op, "planned", "dry_run: 未调用 SOLIDWORKS API")
                for operation in planned.operations
            ),
            outputs=_planned_output_paths(planned),
        )

    def execute(self, plan_data: Mapping[str, Any] | FeaturePlan, dry_run: bool = True, use_active_doc: bool = False, prompt: str = "") -> ExecutionResult:
        if dry_run:
            return self.dry_run(plan_data)
        plan = plan_data if isinstance(plan_data, FeaturePlan) else FeaturePlan.from_dict(canonicalize_featureplan_structure(dict(plan_data)))
        policy_result = self.policy_engine.validate(plan)
        if not policy_result.allowed:
            return ExecutionResult(
                status="blocked",
                message="FeaturePlan 被 Policy Engine 拒绝，未连接 SOLIDWORKS。",
                operations=tuple(
                    OperationResult(v.operation_id, "policy", "blocked", f"{v.code}: {v.message}")
                    for v in policy_result.violations
                ),
            )
        try:
            planned = plan_operations(plan)
            self.session.connect()
            outputs = self.model_builder.build(self.session.require_connected(), planned, use_active_doc, prompt)
        except Exception as exc:
            return ExecutionResult(status="error", message=str(exc))
        return ExecutionResult(
            status="executed",
            message="SolidWorks API 执行完成。",
            operations=tuple(
                OperationResult(operation.id, operation.op, "executed", "已调用固定 API Executor")
                for operation in planned.operations
            ),
            outputs=outputs,
        )


def _planned_output_paths(plan: FeaturePlan) -> tuple[str, ...]:
    if plan.outputs and not any(bool(value) for value in plan.outputs.values()):
        return ()
    explicit = {operation.op for operation in plan.operations if operation.op in OUTPUT_OPERATIONS}
    if explicit:
        outputs = {
            "save_sldprt": "save_sldprt" in explicit,
            "export_step": "export_step" in explicit,
            "capture_png": "capture_png" in explicit,
        }
    else:
        outputs = dict(plan.outputs)
    return tuple(str(path) for path in plan_output_paths(plan.part_name, outputs).values())
