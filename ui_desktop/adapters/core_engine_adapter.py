"""Safe adapter boundary between AI-SW Workbench and the core pipeline.

This first batch intentionally does not call LLM providers, SolidWorks,
win32com, macros, or real API execution. It establishes the return format and
security checks that later batches can reuse when connecting the real pipeline.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import types
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ui_desktop.services.job_store import OUTPUT_ROOT, REAL_RUN_CONFIRMATION

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _looks_like_project_root(path: Path) -> bool:
    return (path / "app").is_dir() and (path / "src").is_dir() and (path / "ui_desktop").is_dir()


def _discover_project_root() -> Path:
    env_root = os.environ.get("AI_SW_PROJECT_ROOT", "").strip()
    if env_root:
        candidate = Path(env_root)
        if _looks_like_project_root(candidate):
            return candidate.resolve()

    candidates: list[Path] = []
    for base in (Path.cwd(), PROJECT_ROOT, Path(__file__).resolve().parents[2]):
        try:
            resolved = base.resolve()
        except Exception:
            continue
        candidates.append(resolved)
        candidates.extend(resolved.parents)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if _looks_like_project_root(candidate):
            return candidate

    return PROJECT_ROOT


def _bootstrap_core_paths() -> None:
    project_root = _discover_project_root()
    os.environ["AI_SW_PROJECT_ROOT"] = str(project_root)

    for insert_path in (str(project_root / "src"), str(project_root)):
        if insert_path in sys.path:
            sys.path.remove(insert_path)
        sys.path.insert(0, insert_path)


_bootstrap_core_paths()


def _load_workspace_package(module_name: str, package_dir: Path) -> types.ModuleType:
    init_file = package_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        module_name,
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load package from workspace: {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_workspace_module(module_name: str, file_path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from workspace: {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _force_workspace_parser_modules() -> None:
    project_root = _discover_project_root()
    app_dir = project_root / "app"
    providers_dir = app_dir / "providers"
    src_dir = project_root / "src"
    cad_dsl_dir = src_dir / "cad_dsl"
    policy_dir = src_dir / "policy"
    solidworks_api_dir = src_dir / "solidworks_api"

    prefixes = ("app", "cad_dsl", "policy", "solidworks_api")
    for module_name in list(sys.modules):
        if module_name.startswith(prefixes):
            sys.modules.pop(module_name, None)

    _load_workspace_package("cad_dsl", cad_dsl_dir)
    _load_workspace_module("cad_dsl.featureplan", cad_dsl_dir / "featureplan.py")
    _load_workspace_module("cad_dsl.feature_registry", cad_dsl_dir / "feature_registry.py")
    _load_workspace_module("cad_dsl.cadplan_adapter", cad_dsl_dir / "cadplan_adapter.py")
    _load_workspace_module("cad_dsl.featureplan_prompt", cad_dsl_dir / "featureplan_prompt.py")
    _load_workspace_module("cad_dsl.semantic_binding", cad_dsl_dir / "semantic_binding.py")

    _load_workspace_package("policy", policy_dir)
    _load_workspace_module("policy.geometry_rules", policy_dir / "geometry_rules.py")
    _load_workspace_module("policy.file_safety_rules", policy_dir / "file_safety_rules.py")
    _load_workspace_module("policy.policy_engine", policy_dir / "policy_engine.py")

    _load_workspace_package("solidworks_api", solidworks_api_dir)
    _load_workspace_module("solidworks_api.operation_planner", solidworks_api_dir / "operation_planner.py")

    _load_workspace_package("app", app_dir)
    _load_workspace_package("app.providers", providers_dir)
    _load_workspace_module("app.openai_config", app_dir / "openai_config.py")
    _load_workspace_module("app.providers.json_utils", providers_dir / "json_utils.py")
    _load_workspace_module("app.providers.rule_based_provider", providers_dir / "rule_based_provider.py")
    _load_workspace_module("app.providers.openai_provider", providers_dir / "openai_provider.py")
    _load_workspace_module("app.providers.local_provider", providers_dir / "local_provider.py")
    _load_workspace_module("app.providers.router", providers_dir / "router.py")

ALLOWED_PROVIDERS = {"local", "openai", "rule_based"}
SENSITIVE_TOKENS = ("api_key", "apikey", "openai_api_key", "secret", "token")


@dataclass(frozen=True)
class AdapterResult:
    ok: bool
    status: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    logs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "message": self.message,
            "data": self.data,
            "logs": list(self.logs),
        }


class CoreEngineAdapter:
    """Thin, safe desktop-facing wrapper for future core pipeline calls."""

    def __init__(self, output_root: Path | None = None) -> None:
        self.output_root = _ensure_inside_outputs(output_root or OUTPUT_ROOT)
        self.output_root.mkdir(parents=True, exist_ok=True)

    def generate_plan(self, natural_language: str, provider: str, job_id: str | None = None) -> AdapterResult:
        provider = _normalize_provider(provider)
        if provider not in ALLOWED_PROVIDERS:
            return _error("invalid_provider", f"Unsupported provider: {_redact(provider)}")

        safe_prompt = _redact(natural_language)
        try:
            if job_id:
                os.environ["AI_SW_JOB_DEBUG_DIR"] = str(_job_dir_for_id(self.output_root, job_id))
            parse_result = _parse_with_existing_provider(natural_language, provider)
            raw_plan = parse_result["plan"]
            parse_info = parse_result["parse_info"]
            plan = _to_featureplan_candidate(raw_plan, provider, parse_info)
            if job_id:
                _save_generated_plan(self.output_root, job_id, safe_prompt, plan)
        except Exception as exc:
            return _error("planning_failed", f"FeaturePlan generation failed: {exc}")
        finally:
            os.environ.pop("AI_SW_JOB_DEBUG_DIR", None)

        safe_prompt = _redact(natural_language)
        status = "need_user_input" if _needs_user_input(plan) else "planned"
        parse_logs = tuple(_parse_info_logs(parse_info))
        return AdapterResult(
            ok=True,
            status=status,
            message="FeaturePlanCandidate generated by existing AI-SW parser pipeline.",
            data={
                "provider": provider,
                "actual_parse_source": parse_info.get("actual_provider", provider),
                "parse_info": parse_info,
                "natural_language": safe_prompt,
                "plan": _sanitize(plan),
            },
            logs=(_log_line("generate_plan", status, "Existing provider router generated a FeaturePlanCandidate."),) + parse_logs,
        )

    def validate_plan(self, plan: dict[str, Any], job_id: str | None = None) -> AdapterResult:
        safe_plan = _sanitize(plan)
        result = _run_validation_chain(safe_plan)
        if job_id:
            _save_validation_result(self.output_root, job_id, result)
        status = "validation_passed" if result["passed"] else "validation_failed"
        return AdapterResult(
            ok=result["passed"],
            status=status,
            message="FeaturePlan validation passed." if result["passed"] else "FeaturePlan validation failed.",
            data=result,
            logs=(_log_line("validate_plan", status, "Validation chain completed without SolidWorks connection."),),
        )

    def dry_run(
        self,
        plan: dict[str, Any],
        validation_result: dict[str, Any] | None = None,
        job_id: str | None = None,
    ) -> AdapterResult:
        if not plan:
            result = _dry_run_blocked("No FeaturePlan is available for dry_run.")
            if job_id:
                _save_dry_run_result(self.output_root, job_id, result)
            return AdapterResult(ok=False, status="dry_run_failed", message="dry_run blocked.", data=result, logs=tuple(result["dry_run_log"]))

        if not validation_result:
            result = _dry_run_blocked("FeaturePlan must pass validate_plan before dry_run.")
            if job_id:
                _save_dry_run_result(self.output_root, job_id, result)
            return AdapterResult(ok=False, status="dry_run_failed", message="dry_run blocked.", data=result, logs=tuple(result["dry_run_log"]))

        blocking_errors = validation_result.get("blocking_errors", []) if isinstance(validation_result, dict) else []
        if not validation_result.get("passed") or blocking_errors:
            result = _dry_run_blocked("FeaturePlan validation has blocking errors.", errors=list(blocking_errors))
            if job_id:
                _save_dry_run_result(self.output_root, job_id, result)
            return AdapterResult(ok=False, status="dry_run_failed", message="dry_run blocked.", data=result, logs=tuple(result["dry_run_log"]))

        executor_result = _run_existing_dry_run(_sanitize(plan))
        result = _dry_run_result_from_executor(executor_result, validation_result)
        if job_id:
            _save_dry_run_result(self.output_root, job_id, result)
        return AdapterResult(
            ok=result["passed"],
            status="dry_run_passed" if result["passed"] else "dry_run_failed",
            message="dry_run passed without SolidWorks connection." if result["passed"] else "dry_run failed.",
            data=result,
            logs=tuple(result["dry_run_log"]),
        )

    def real_run(
        self,
        plan: dict[str, Any],
        confirmation: str,
        job_context: dict[str, Any],
        executor: Any | None = None,
    ) -> AdapterResult:
        gate = _validate_real_run_gate(self.output_root, _sanitize(plan), confirmation, job_context)
        if not gate["passed"]:
            return AdapterResult(
                ok=False,
                status="real_run_rejected",
                message="real_run rejected by safety gate.",
                data=gate,
                logs=tuple(gate["real_run_log"]),
            )

        executor = executor or _run_existing_real_executor

        try:
            execution_result = executor(_sanitize(plan), job_context)
        except TypeError:
            execution_result = executor(_sanitize(plan))
        except Exception as exc:
            result = {
                **gate,
                "passed": False,
                "status": "failed",
                "executed": False,
                "errors": [f"executor failed: {_redact(str(exc))}"],
                "real_run_log": gate["real_run_log"] + [_log_line("real_run", "failed", _redact(str(exc)))],
            }
            _save_execution_artifacts(self.output_root, str(job_context.get("job_id", "")), result)
            return AdapterResult(ok=False, status="failed", message="real_run executor failed.", data=result, logs=tuple(result["real_run_log"]))

        result = _real_run_result_from_executor(gate, execution_result)
        _save_execution_artifacts(self.output_root, str(job_context.get("job_id", "")), result)
        return AdapterResult(
            ok=result["status"] == "succeeded",
            status=result["status"],
            message=result["message"],
            data=result,
            logs=tuple(result["real_run_log"]),
        )

    def get_output_files(self, job_id: str) -> AdapterResult:
        try:
            job_dir = _job_dir_for_id(self.output_root, job_id)
        except ValueError as exc:
            return _error("invalid_output_path", str(exc))
        files = {
            "SLDPRT": str(job_dir / "mock_workbench_part.SLDPRT"),
            "STEP": str(job_dir / "mock_workbench_part.STEP"),
            "PNG": str(job_dir / "mock_workbench_part.PNG"),
            "LOG": str(job_dir / "ui_log.txt"),
        }
        return AdapterResult(
            ok=True,
            status="outputs_ready",
            message="Mock output file summary generated.",
            data={"job_id": job_id, "files": files},
            logs=(_log_line("get_output_files", "ready", "Mock output paths resolved under outputs/jobs."),),
        )


def _normalize_provider(provider: str) -> str:
    return str(provider or "").strip().lower()


def _parse_with_existing_provider(prompt: str, provider: str) -> dict[str, Any]:
    if getattr(sys, "frozen", False):
        _force_workspace_parser_modules()

    from app.providers.router import parse_featureplan_with_provider
    from cad_dsl.semantic_binding import canonicalize_featureplan_structure

    previous = os.environ.get("AI_SW_LLM_PROVIDER")
    previous_debug_dir = os.environ.get("AI_SW_LOCAL_LLM_DEBUG_DIR")
    debug_dir = os.environ.get("AI_SW_JOB_DEBUG_DIR", "").strip()
    os.environ["AI_SW_LLM_PROVIDER"] = provider
    if debug_dir:
        os.environ["AI_SW_LOCAL_LLM_DEBUG_DIR"] = debug_dir
    stdout_buffer = io.StringIO()
    try:
        with redirect_stdout(stdout_buffer):
            plan = canonicalize_featureplan_structure(parse_featureplan_with_provider(prompt))
    finally:
        if previous is None:
            os.environ.pop("AI_SW_LLM_PROVIDER", None)
        else:
            os.environ["AI_SW_LLM_PROVIDER"] = previous
        if previous_debug_dir is None:
            os.environ.pop("AI_SW_LOCAL_LLM_DEBUG_DIR", None)
        else:
            os.environ["AI_SW_LOCAL_LLM_DEBUG_DIR"] = previous_debug_dir
    if not isinstance(plan, dict):
        raise ValueError("parser returned a non-dict plan")
    parse_info = _detect_parse_info(provider, stdout_buffer.getvalue(), plan)
    return {"plan": plan, "parse_info": parse_info}


def _to_featureplan_candidate(plan: dict[str, Any], provider: str, parse_info: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate = _sanitize(plan)
    metadata = dict(candidate.get("metadata") or {})
    metadata.setdefault("source", provider)
    metadata["provider"] = provider
    if parse_info:
        metadata["provider_requested"] = parse_info.get("requested_provider", provider)
        metadata["provider_actual"] = parse_info.get("actual_provider", provider)
        metadata["provider_fallback_used"] = bool(parse_info.get("fallback_used", False))
    candidate["metadata"] = metadata
    candidate.setdefault("version", "2.0")
    candidate.setdefault("unit", "mm")
    candidate.setdefault("document_type", "part")
    candidate.setdefault("part_name", metadata.get("name") or candidate.get("part_name") or "unnamed_part")
    candidate["intent"] = _extract_intent(candidate)
    candidate["parameters"] = _extract_parameters(candidate)
    candidate["operations"] = _normalize_operations(candidate.get("operations", []))
    candidate.setdefault("outputs", {})
    return candidate


def _extract_intent(candidate: dict[str, Any]) -> dict[str, Any]:
    existing = candidate.get("intent")
    if isinstance(existing, dict):
        return existing
    operations = candidate.get("operations") if isinstance(candidate.get("operations"), list) else []
    op_names = [str(operation.get("op", "")) for operation in operations if isinstance(operation, dict)]
    assumptions = candidate.get("assumptions", [])
    missing_info = candidate.get("missing_info", [])
    metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
    return {
        "part_type": candidate.get("document_type", "part"),
        "main_structure": ", ".join(op_names) if op_names else "parsed FeaturePlan",
        "coordinate_basis": _infer_coordinate_basis(operations),
        "assumptions": assumptions if isinstance(assumptions, list) else [],
        "missing_info": missing_info if isinstance(missing_info, list) else [],
        "description": metadata.get("description", ""),
    }


def _infer_coordinate_basis(operations: list[dict[str, Any]]) -> str:
    for operation in operations:
        params = operation.get("params", {}) if isinstance(operation, dict) else {}
        plane = params.get("plane") if isinstance(params, dict) else None
        if plane:
            return str(plane)
    return "FeaturePlan operation order"


def _extract_parameters(candidate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    parameters = candidate.get("parameters")
    if isinstance(parameters, dict) and parameters:
        return parameters
    extracted: dict[str, dict[str, Any]] = {}
    for operation in candidate.get("operations", []):
        if not isinstance(operation, dict):
            continue
        op_id = str(operation.get("id") or operation.get("op") or f"op_{len(extracted) + 1}")
        params = operation.get("params", {})
        if not isinstance(params, dict):
            continue
        for key, value in params.items():
            name = f"{op_id}.{key}"
            unit = "mm" if _looks_like_length_key(key) else ""
            extracted[name] = {"value": value, "unit": unit}
    return extracted


def _normalize_operations(operations: Any) -> list[dict[str, Any]]:
    from cad_dsl.feature_references import normalize_feature_reference

    normalized: list[dict[str, Any]] = []
    if not isinstance(operations, list):
        return normalized
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            continue
        op_name = str(operation.get("op", ""))
        op_id = str(operation.get("id") or f"op_{index:03d}")
        params = dict(operation.get("params") or {})
        if "seed_feature" in params:
            params["seed_feature"] = normalize_feature_reference(params.get("seed_feature"))
        normalized.append(
            {
                **operation,
                "index": operation.get("index", index),
                "id": op_id,
                "op": op_name,
                "params": params,
                "name": operation.get("name") or op_name,
                "depends_on": operation.get("depends_on", []),
                "produces": operation.get("produces", []),
                "status": operation.get("status", "planned"),
            }
        )
    return normalized


def _looks_like_length_key(key: str) -> bool:
    lowered = str(key).lower()
    return any(word in lowered for word in ("length", "width", "height", "thickness", "depth", "diameter", "radius", "offset", "spacing"))


def _needs_user_input(candidate: dict[str, Any]) -> bool:
    intent = candidate.get("intent", {})
    if isinstance(intent, dict) and intent.get("missing_info"):
        return True
    missing_info = candidate.get("missing_info")
    return isinstance(missing_info, list) and bool(missing_info)


def _detect_parse_info(requested_provider: str, router_output: str, plan: dict[str, Any]) -> dict[str, Any]:
    sanitized_output = _redact(router_output or "").strip()
    actual_provider = requested_provider
    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    metadata_provider = str(metadata.get("provider") or metadata.get("source") or "").strip().lower()
    if metadata_provider in ALLOWED_PROVIDERS:
        actual_provider = metadata_provider

    output_lower = sanitized_output.lower()
    if "llm provider: rule_based" in output_lower:
        actual_provider = "rule_based"
    elif "llm provider: local" in output_lower:
        actual_provider = "local"
    elif "llm provider: openai" in output_lower:
        actual_provider = "openai"

    fallback_used = actual_provider != requested_provider or "fallback to rule_based parser" in output_lower
    repair_rounds = output_lower.count("requesting local model repair") + output_lower.count("repair still invalid")
    return {
        "requested_provider": requested_provider,
        "actual_provider": actual_provider,
        "fallback_used": fallback_used,
        "repair_rounds": repair_rounds,
        "router_output": sanitized_output,
    }


def _parse_info_logs(parse_info: dict[str, Any]) -> list[str]:
    requested = str(parse_info.get("requested_provider", ""))
    actual = str(parse_info.get("actual_provider", requested))
    fallback = "yes" if parse_info.get("fallback_used") else "no"
    repair_rounds = int(parse_info.get("repair_rounds", 0) or 0)
    lines = [
        _log_line("parse_source", "info", f"requested={requested}; actual={actual}; fallback={fallback}; repair_rounds={repair_rounds}"),
    ]
    router_output = str(parse_info.get("router_output", "")).strip()
    if router_output:
        for raw_line in router_output.splitlines():
            cleaned = raw_line.strip()
            if cleaned:
                lines.append(_log_line("parse_source", "trace", cleaned))
    return lines


def _save_generated_plan(output_root: Path, job_id: str, safe_prompt: str, plan: dict[str, Any]) -> None:
    job_dir = _job_dir_for_id(output_root, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "input.txt").write_text(safe_prompt, encoding="utf-8")
    (job_dir / "featureplan_candidate.json").write_text(
        json.dumps(_sanitize(plan), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _save_validation_result(output_root: Path, job_id: str, result: dict[str, Any]) -> None:
    job_dir = _job_dir_for_id(output_root, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "validation_result.json").write_text(
        json.dumps(_sanitize(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _save_dry_run_result(output_root: Path, job_id: str, result: dict[str, Any]) -> None:
    job_dir = _job_dir_for_id(output_root, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    safe_result = _sanitize(result)
    (job_dir / "dry_run_result.json").write_text(
        json.dumps(safe_result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (job_dir / "dry_run.log").write_text("\n".join(safe_result.get("dry_run_log", [])), encoding="utf-8")


def _save_execution_artifacts(output_root: Path, job_id: str, result: dict[str, Any]) -> None:
    job_dir = _job_dir_for_id(output_root, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    safe_result = _sanitize(result)
    (job_dir / "execution.log").write_text(
        "\n".join(str(line) for line in safe_result.get("real_run_log", [])),
        encoding="utf-8",
    )
    (job_dir / "outputs.json").write_text(
        json.dumps(_real_run_output_summary(job_dir, safe_result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _validate_real_run_gate(output_root: Path, plan: dict[str, Any], confirmation: str, job_context: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if str(confirmation).strip() != REAL_RUN_CONFIRMATION:
        errors.append("confirmation must be YES_RUN_SOLIDWORKS_API")

    if str(job_context.get("status", "")) != "dry_run_passed":
        errors.append("current job status must be dry_run_passed before real_run")

    validation_result = job_context.get("validation_result")
    if not isinstance(validation_result, dict) or not validation_result.get("passed"):
        errors.append("validation_result must be passed before real_run")
    else:
        blocking_errors = validation_result.get("blocking_errors", [])
        if blocking_errors:
            errors.append("validation_result contains blocking_errors")
        for capability in validation_result.get("registry_result", {}).get("capability_status", []):
            status = capability.get("status")
            if status != "implemented":
                errors.append(f"validation_result contains non-implemented operation {capability.get('op')}: {status}")

    gate_validation = _run_validation_chain(plan)
    for error in gate_validation.get("blocking_errors", []):
        errors.append(f"preflight: {error}")

    for capability in gate_validation.get("registry_result", {}).get("capability_status", []):
        status = capability.get("status")
        if status != "implemented":
            errors.append(f"operation {capability.get('op')} is {status}; real_run requires implemented operations only")

    job_id = str(job_context.get("job_id", "")).strip()
    try:
        job_dir = _job_dir_for_id(output_root, job_id)
    except Exception as exc:
        errors.append(str(exc))
        job_dir = None
    output_dir = job_context.get("output_dir")
    if output_dir:
        try:
            resolved_output = Path(str(output_dir)).resolve()
            if job_dir is None or (resolved_output != job_dir and job_dir not in resolved_output.parents):
                errors.append("output_dir must stay inside outputs/jobs/<job_id>")
        except Exception as exc:
            errors.append(f"invalid output_dir: {exc}")

    passed = not errors
    status = "real_run_gate_passed" if passed else "real_run_rejected"
    log_message = "real_run safety gate passed" if passed else "; ".join(errors)
    return {
        "passed": passed,
        "status": status,
        "executed": False,
        "warnings": warnings,
        "errors": errors,
        "job_id": job_id,
        "output_dir": str(job_dir) if job_dir is not None else "",
        "validation_result": validation_result if isinstance(validation_result, dict) else {},
        "preflight_validation": gate_validation,
        "real_run_log": [_log_line("real_run", status, log_message)],
    }


def _real_run_result_from_executor(gate: dict[str, Any], execution_result: Any) -> dict[str, Any]:
    if isinstance(execution_result, AdapterResult):
        status = "succeeded" if execution_result.ok else "failed"
        message = execution_result.message
        data = execution_result.data
    elif isinstance(execution_result, dict):
        status = str(execution_result.get("status") or ("succeeded" if execution_result.get("ok", True) else "failed"))
        message = str(execution_result.get("message", "mock executor finished"))
        data = execution_result
    else:
        status = str(getattr(execution_result, "status", "succeeded"))
        message = str(getattr(execution_result, "message", "executor finished"))
        data = {
            "raw_status": status,
            "message": message,
            "outputs": list(getattr(execution_result, "outputs", ())),
            "operations": [
                {
                    "operation_id": operation.operation_id,
                    "operation_type": operation.operation_type,
                    "status": operation.status,
                    "message": operation.message,
                }
                for operation in getattr(execution_result, "operations", ())
            ],
        }
    if status in {"executed", "success", "ok"}:
        status = "succeeded"
    result = {
        **gate,
        "status": status,
        "executed": status == "succeeded",
        "message": message,
        "executor_result": _sanitize(data),
        "real_run_log": gate["real_run_log"] + [_log_line("real_run", status, message)],
    }
    if status != "succeeded":
        result["passed"] = False
        result.setdefault("errors", []).append(message)
    return result


def _real_run_output_summary(job_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    files = {
        "execution_log": str(job_dir / "execution.log"),
        "outputs_json": str(job_dir / "outputs.json"),
    }
    executor_outputs = _extract_executor_outputs(result)
    for path in executor_outputs:
        suffix = Path(path).suffix.lower()
        if suffix == ".sldprt":
            files["sldprt"] = path
        elif suffix in {".step", ".stp"}:
            files["step"] = path
        elif suffix in {".png", ".jpg", ".jpeg"}:
            files["png"] = path
    return {
        "job_dir": str(job_dir),
        "status": result.get("status", ""),
        "files": files,
        "executor_outputs": executor_outputs,
    }


def _extract_executor_outputs(result: dict[str, Any]) -> list[str]:
    executor_result = result.get("executor_result", {})
    outputs: Any = []
    if isinstance(executor_result, dict):
        outputs = executor_result.get("outputs") or executor_result.get("files") or []
    if isinstance(outputs, dict):
        return [str(value) for value in outputs.values()]
    if isinstance(outputs, (list, tuple)):
        return [str(value) for value in outputs]
    return []


def _dry_run_blocked(message: str, errors: list[str] | None = None) -> dict[str, Any]:
    all_errors = list(errors or [])
    all_errors.insert(0, message)
    return {
        "passed": False,
        "steps": [],
        "warnings": [],
        "errors": all_errors,
        "dry_run_log": [_log_line("dry_run", "blocked", message)],
        "connected_solidworks": False,
    }


def _run_existing_dry_run(plan: dict[str, Any]) -> Any:
    from cad_dsl.semantic_binding import canonicalize_featureplan_structure
    from solidworks_api.executor import SolidWorksApiExecutor

    return SolidWorksApiExecutor().dry_run(canonicalize_featureplan_structure(plan))


def _run_existing_real_executor(plan: dict[str, Any], _job_context: dict[str, Any] | None = None) -> Any:
    from solidworks_api.executor import SolidWorksApiExecutor

    return SolidWorksApiExecutor().execute(plan, dry_run=False)


def _dry_run_result_from_executor(executor_result: Any, validation_result: dict[str, Any]) -> dict[str, Any]:
    passed = getattr(executor_result, "status", "") == "dry_run"
    steps = [
        {
            "operation_id": operation.operation_id,
            "operation_type": operation.operation_type,
            "status": operation.status,
            "message": operation.message,
        }
        for operation in getattr(executor_result, "operations", ())
    ]
    dry_run_log = [
        _log_line("dry_run", step["status"], f"{step['operation_id']}: {step['operation_type']} - {step['message']}")
        for step in steps
    ]
    if not dry_run_log:
        dry_run_log = [_log_line("dry_run", getattr(executor_result, "status", "unknown"), getattr(executor_result, "message", ""))]
    errors: list[str] = []
    if not passed:
        errors.append(getattr(executor_result, "message", "dry_run failed"))
        errors.extend(step["message"] for step in steps if step["status"] in {"blocked", "error", "failed"})
    return {
        "passed": passed,
        "steps": steps,
        "warnings": list(validation_result.get("warnings", [])),
        "errors": errors,
        "dry_run_log": dry_run_log,
        "executor_status": getattr(executor_result, "status", ""),
        "executor_message": getattr(executor_result, "message", ""),
        "outputs": list(getattr(executor_result, "outputs", ())),
        "connected_solidworks": False,
    }


def _run_validation_chain(plan: dict[str, Any]) -> dict[str, Any]:
    from cad_dsl.semantic_binding import canonicalize_featureplan_structure

    plan = canonicalize_featureplan_structure(plan)
    warnings: list[str] = []
    blocking_errors: list[str] = []

    schema_result = _schema_validate(plan)
    blocking_errors.extend(schema_result["errors"])

    registry_result = _registry_validate(plan)
    blocking_errors.extend(registry_result["errors"])
    warnings.extend(registry_result["warnings"])

    dependency_result = _dependency_resolve(plan)
    blocking_errors.extend(dependency_result["errors"])

    constraint_result = _constraint_validate(plan)
    blocking_errors.extend(constraint_result["errors"])

    policy_result = _policy_validate(plan)
    blocking_errors.extend(policy_result["errors"])

    execution_order = dependency_result.get("execution_order", [])
    passed = not blocking_errors
    return {
        "passed": passed,
        "dependency_result": dependency_result,
        "constraint_result": constraint_result,
        "schema_result": schema_result,
        "policy_result": policy_result,
        "registry_result": registry_result,
        "execution_order": execution_order,
        "warnings": warnings,
        "blocking_errors": blocking_errors,
        "can_dry_run": passed,
    }


def _schema_validate(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(plan, dict):
        return {"passed": False, "errors": ["schema: plan must be an object"]}
    for key in ("version", "unit", "document_type", "part_name", "operations"):
        if key not in plan:
            errors.append(f"schema: missing required top-level field: {key}")
    allowed = {"version", "unit", "document_type", "part_name", "metadata", "intent", "parameters", "operations", "outputs"}
    for key in plan:
        if key not in allowed:
            errors.append(f"schema: unsupported top-level field: {key}")
    if plan.get("version") != "2.0":
        errors.append("schema: version must be 2.0")
    if plan.get("unit") != "mm":
        errors.append("schema: unit must be mm")
    if plan.get("document_type") != "part":
        errors.append("schema: document_type must be part")
    operations = plan.get("operations")
    if not isinstance(operations, list) or not operations:
        errors.append("schema: operations must be a non-empty array")
    else:
        for index, operation in enumerate(operations):
            if not isinstance(operation, dict):
                errors.append(f"schema: operations[{index}] must be an object")
                continue
            for key in ("id", "op", "params"):
                if key not in operation:
                    errors.append(f"schema: operations[{index}] missing required field: {key}")
            if "params" in operation and not isinstance(operation.get("params"), dict):
                errors.append(f"schema: operations[{index}].params must be an object")
            if "depends_on" in operation and not isinstance(operation.get("depends_on"), list):
                errors.append(f"schema: operations[{index}].depends_on must be an array")
    outputs = plan.get("outputs", {})
    if outputs is not None and not isinstance(outputs, dict):
        errors.append("schema: outputs must be an object")
    return {"passed": not errors, "errors": errors}


def _registry_validate(plan: dict[str, Any]) -> dict[str, Any]:
    from cad_dsl.feature_registry import default_registry

    registry = default_registry()
    errors: list[str] = []
    warnings: list[str] = []
    capability_status: list[dict[str, str]] = []
    for operation in plan.get("operations", []) if isinstance(plan.get("operations"), list) else []:
        if not isinstance(operation, dict):
            continue
        op_id = str(operation.get("id", ""))
        op_name = str(operation.get("op", ""))
        definition = registry.get(op_name)
        if definition is None:
            errors.append(f"registry: unknown op: {op_name}")
            capability_status.append({"id": op_id, "op": op_name, "status": "unknown"})
            continue
        capability_status.append({"id": op_id, "op": op_name, "status": definition.status})
        if definition.status != "implemented":
            message = f"registry: {op_name} is {definition.status}; not executable"
            warnings.append(message)
            errors.append(message)
    return {"passed": not errors, "errors": errors, "warnings": warnings, "capability_status": capability_status}


def _dependency_resolve(plan: dict[str, Any]) -> dict[str, Any]:
    operations = plan.get("operations", [])
    if not isinstance(operations, list):
        return {"passed": False, "errors": ["dependency: operations must be an array"], "execution_order": []}
    ids: list[str] = []
    id_to_operation: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            continue
        op_id = str(operation.get("id", ""))
        if not op_id:
            errors.append(f"dependency: operation at index {index} is missing id")
            continue
        if op_id in id_to_operation:
            errors.append(f"dependency: duplicate operation id: {op_id}")
        ids.append(op_id)
        id_to_operation[op_id] = operation
    id_set = set(ids)
    prerequisites: dict[str, set[str]] = {op_id: set() for op_id in ids}
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op_id = str(operation.get("id", ""))
        for dependency in operation.get("depends_on", []) or []:
            dependency_id = str(dependency)
            if dependency_id not in id_set:
                errors.append(f"dependency: {op_id} references missing depends_on id: {dependency_id}")
            elif dependency_id != op_id:
                prerequisites.setdefault(op_id, set()).add(dependency_id)
    order, cycle_errors = _topological_order(ids, prerequisites)
    errors.extend(cycle_errors)
    reference_errors = _validate_operation_references(operations, id_set)
    errors.extend(reference_errors)
    return {"passed": not errors, "errors": errors, "execution_order": order if not cycle_errors else []}


def _topological_order(ids: list[str], prerequisites: dict[str, set[str]]) -> tuple[list[str], list[str]]:
    remaining = set(ids)
    order: list[str] = []
    while remaining:
        ready = [op_id for op_id in ids if op_id in remaining and not (prerequisites.get(op_id, set()) & remaining)]
        if not ready:
            return order, ["dependency: cyclic dependency detected"]
        for op_id in ready:
            remaining.remove(op_id)
            order.append(op_id)
    return order, []


def _validate_operation_references(operations: list[Any], id_set: set[str]) -> list[str]:
    from cad_dsl.feature_references import build_seed_feature_aliases_from_dicts, resolve_seed_feature_reference

    errors: list[str] = []
    sketch_names = {
        str(operation.get("params", {}).get("name"))
        for operation in operations
        if isinstance(operation, dict) and operation.get("op") == "create_sketch" and isinstance(operation.get("params"), dict)
    }
    seed_aliases = build_seed_feature_aliases_from_dicts([operation for operation in operations if isinstance(operation, dict)])
    seed_names = set(seed_aliases) | set(id_set)
    for operation in operations:
        if not isinstance(operation, dict) or not isinstance(operation.get("params"), dict):
            continue
        op_id = str(operation.get("id", ""))
        op_name = operation.get("op")
        params = operation["params"]
        if op_name in {"sketch_center_rectangle", "sketch_circle", "extrude_boss", "extrude_cut"}:
            sketch = str(params.get("sketch", ""))
            if sketch and sketch not in sketch_names:
                errors.append(f"dependency: {op_id} references missing sketch: {sketch}")
        if op_name in {"create_linear_pattern", "create_circular_pattern", "mirror_feature"}:
            seed = str(params.get("seed_feature", ""))
            resolved_seed = resolve_seed_feature_reference(seed, seed_aliases)
            if seed and resolved_seed not in seed_names:
                errors.append(f"dependency: {op_id} references missing seed_feature: {seed}")
    return errors


def _constraint_validate(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        from cad_dsl.featureplan import FeaturePlan
        from cad_dsl.semantic_binding import canonicalize_featureplan_structure
        from solidworks_api.operation_planner import plan_operations

        planned = plan_operations(FeaturePlan.from_dict(canonicalize_featureplan_structure(plan)))
        execution_order = [operation.id for operation in planned.operations]
    except Exception as exc:
        errors.append(f"constraint: {exc}")
        execution_order = []
    return {"passed": not errors, "errors": errors, "execution_order": execution_order}


def _policy_validate(plan: dict[str, Any]) -> dict[str, Any]:
    try:
        from policy.policy_engine import PolicyEngine

        result = PolicyEngine().validate(plan)
    except Exception as exc:
        return {"passed": False, "errors": [f"policy: {exc}"], "violations": []}
    violations = [
        {
            "code": violation.code,
            "message": violation.message,
            "operation_id": violation.operation_id,
        }
        for violation in result.violations
    ]
    errors = [f"policy:{item['code']}: {item['operation_id']} {item['message']}".strip() for item in violations]
    return {"passed": result.allowed, "errors": errors, "violations": violations}


def _error(status: str, message: str) -> AdapterResult:
    return AdapterResult(
        ok=False,
        status=status,
        message=_redact(message),
        data={},
        logs=(_log_line("adapter", "error", _redact(message)),),
    )


def _job_dir_for_id(output_root: Path, job_id: str) -> Path:
    job_id_text = str(job_id or "").strip()
    if not job_id_text.startswith("job_") or any(part in job_id_text for part in ("..", "/", "\\")):
        raise ValueError("Invalid job id; output paths must stay under outputs/jobs")
    return _ensure_inside_outputs(output_root / job_id_text)


def _ensure_inside_outputs(path: Path) -> Path:
    resolved_root = OUTPUT_ROOT.resolve()
    resolved_path = Path(path).resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError("Path must stay inside outputs/jobs")
    return resolved_path


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize(inner) for key, inner in value.items() if not _is_sensitive_key(str(key))}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _redact(value)
    return value


def _redact(text: str) -> str:
    redacted = str(text)
    for token in SENSITIVE_TOKENS:
        marker = token + "="
        lowered = redacted.lower()
        index = lowered.find(marker)
        if index >= 0:
            end = redacted.find(" ", index)
            if end < 0:
                end = len(redacted)
            redacted = redacted[: index + len(marker)] + "[redacted]" + redacted[end:]
    return redacted


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in SENSITIVE_TOKENS)


def _log_line(step: str, status: str, message: str) -> str:
    return f"[{datetime.now().strftime('%H:%M:%S')}] [{step}] [{status}] {message}"
