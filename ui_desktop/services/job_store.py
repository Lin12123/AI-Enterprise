"""Local JSON JobStore for AI-SW Workbench mock jobs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "jobs"
SENSITIVE_TOKENS = ("api_key", "apikey", "openai_api_key", "secret", "token")
REAL_RUN_CONFIRMATION = "YES_RUN_SOLIDWORKS_API"


class JobStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    NEED_USER_INPUT = "need_user_input"
    PLANNED = "planned"
    PLANNED_MODIFIED = "planned_modified"
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    VALIDATION_PASSED = "validation_passed"
    DRY_RUNNING = "dry_running"
    DRY_RUN_PASSED = "dry_run_passed"
    DRY_RUN_FAILED = "dry_run_failed"
    AWAITING_REAL_RUN_APPROVAL = "awaiting_real_run_approval"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DesktopJob:
    job_id: str
    input_text: str
    provider: str = "local"
    executor_mode: str = "api_executor"
    status: JobStatus = JobStatus.CREATED
    featureplan_candidate: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)


def can_enter_real_run(confirmation_text: str) -> bool:
    return confirmation_text.strip() == REAL_RUN_CONFIRMATION


def next_real_run_status(confirmation_text: str) -> JobStatus:
    if can_enter_real_run(confirmation_text):
        return JobStatus.AWAITING_REAL_RUN_APPROVAL
    return JobStatus.DRY_RUN_PASSED


class JobStore:
    def __init__(self, output_root: Path | None = None) -> None:
        self.output_root = _resolve_inside_root(output_root or OUTPUT_ROOT, OUTPUT_ROOT)
        self.output_root.mkdir(parents=True, exist_ok=True)

    def create_job(self, input_text: str, provider: str = "local", executor_mode: str = "api_executor") -> DesktopJob:
        job_id = "job_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        job = DesktopJob(job_id=job_id, input_text=input_text, provider=provider, executor_mode=executor_mode)
        job.logs.append(_log_line("job", "created", "Mock desktop job created."))
        self.save_job(job)
        return job

    def job_dir(self, job_id: str) -> Path:
        if not job_id.startswith("job_") or any(part in job_id for part in ("..", "/", "\\")):
            raise ValueError("Invalid job id")
        return _resolve_inside_root(self.output_root / job_id, self.output_root)

    def save_job(self, job: DesktopJob) -> None:
        job_dir = self.job_dir(job.job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        safe_plan = _sanitize(job.featureplan_candidate)
        (job_dir / "input.txt").write_text(_redact_text(job.input_text), encoding="utf-8")
        (job_dir / "featureplan_candidate.json").write_text(
            json.dumps(safe_plan, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        state = {
            "job_id": job.job_id,
            "provider": job.provider,
            "executor_mode": job.executor_mode,
            "status": job.status.value,
        }
        (job_dir / "job_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        (job_dir / "ui_log.txt").write_text("\n".join(job.logs), encoding="utf-8")


def mock_featureplan_candidate() -> dict[str, Any]:
    return {
        "version": "2.0",
        "unit": "mm",
        "document_type": "part",
        "part_name": "mock_workbench_part",
        "intent": {
            "part_type": "mounting_plate",
            "main_structure": "rectangular base with editable parameters",
            "coordinate_basis": "centered top-plane sketch",
            "assumptions": ["mock data only", "no SolidWorks API call"],
            "missing_info": ["exact material", "manufacturing tolerance"],
        },
        "parameters": {
            "base_length": {"value": 120, "unit": "mm"},
            "base_width": {"value": 80, "unit": "mm"},
            "base_thickness": {"value": 12, "unit": "mm"},
            "fillet_radius": {"value": 3, "unit": "mm"},
        },
        "operations": [
            {"index": 1, "id": "op_001", "op": "create_new_part", "name": "New Part", "depends_on": [], "produces": ["part"], "status": "planned"},
            {"index": 2, "id": "op_002", "op": "create_sketch", "name": "Base Sketch", "depends_on": ["op_001"], "produces": ["sketch_base"], "status": "planned"},
            {"index": 3, "id": "op_003", "op": "sketch_center_rectangle", "name": "Base Rectangle", "depends_on": ["op_002"], "produces": ["profile_base"], "status": "planned"},
            {"index": 4, "id": "op_004", "op": "extrude_boss", "name": "Base Extrude", "depends_on": ["op_003"], "produces": ["solid_base"], "status": "planned"},
            {"index": 5, "id": "op_005", "op": "add_fillet", "name": "Outer Edge Fillet", "depends_on": ["op_004"], "produces": ["filleted_edges"], "status": "planned"},
        ],
        "outputs": {"save_sldprt": True, "export_step": True, "capture_png": True},
    }


def mock_output_summary(job_id: str) -> dict[str, str]:
    root = OUTPUT_ROOT / job_id
    return {
        "SLDPRT": str(root / "mock_workbench_part.SLDPRT"),
        "STEP": str(root / "mock_workbench_part.STEP"),
        "PNG": str(root / "mock_workbench_part.PNG"),
        "LOG": str(root / "ui_log.txt"),
    }


def _resolve_inside_root(path: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError("Path must stay inside outputs/jobs")
    return resolved_path


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize(inner) for key, inner in value.items() if not _is_sensitive_key(str(key))}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in SENSITIVE_TOKENS)


def _redact_text(text: str) -> str:
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


def _log_line(step: str, status: str, message: str) -> str:
    timestamp = datetime.now().strftime("%H:%M:%S")
    return f"[{timestamp}] [{step}] [{status}] {message}"
