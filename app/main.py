import json
import os
import re
import sys
from pathlib import Path


project_root = Path(__file__).resolve().parents[1]
for path in (project_root, project_root / "src"):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)
from cad_dsl.cadplan_adapter import cadplan_to_featureplan
from cad_dsl.nl_featureplan_parser import LlmFeaturePlanError, parse_prompt_to_featureplan
from app.job_writer import write_cadplan_json, write_job_ini
from app.llm_parser import current_parse_mode, parse_prompt_to_cadplan
from policy.policy_engine import PolicyEngine
from solidworks_api.executor import SolidWorksApiExecutor


def _fmt(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def show_plan(cadplan: dict) -> None:
    if cadplan.get("template") == "blank_part":
        outputs = cadplan.get("outputs", {})
        print("CADPlan preview:")
        print(f"- Template: blank_part")
        print(f"- Part name: {cadplan.get('part_name', 'blank_part')}")
        print("- Geometry: empty part")
        names = []
        if outputs.get("save_sldprt", True):
            names.append("SLDPRT")
        if outputs.get("export_step", False):
            names.append("STEP")
        if outputs.get("capture_png", False):
            names.append("PNG")
        print(f"- Outputs: {' / '.join(names) if names else 'none'}")
        for note in cadplan.get("notes", []):
            print(f"- Note: {note}")
        return

    base = cadplan["base"]
    corner = cadplan.get("corner_holes", {})
    boss = cadplan.get("center_boss", {})
    center_hole = cadplan.get("center_hole", {})
    fillet = cadplan.get("fillet", {})
    outputs = cadplan.get("outputs", {})

    print("CADPlan preview:")
    if base.get("shape", "rectangle") == "circle":
        print(f"- Base: circle, diameter {_fmt(base['diameter'])} mm, thickness {_fmt(base['thickness'])} mm")
    else:
        print(f"- Base: {_fmt(base['length'])} x {_fmt(base['width'])} x {_fmt(base['thickness'])} mm")
    if corner.get("enabled"):
        print(
            f"- Corner holes: 4 holes, diameter {_fmt(corner['diameter'])} mm, "
            f"position +/-{_fmt(corner['offset_x'])}, +/-{_fmt(corner['offset_y'])} mm"
        )
    else:
        print("- Corner holes: disabled")
    if boss.get("enabled"):
        print(f"- Center boss: diameter {_fmt(boss['diameter'])} mm, height {_fmt(boss['height'])} mm")
    else:
        print("- Center boss: disabled")
    if center_hole.get("enabled"):
        print(f"- Center hole: diameter {_fmt(center_hole['diameter'])} mm")
    else:
        print("- Center hole: disabled")
    if fillet.get("enabled"):
        print(f"- Fillet: R{_fmt(fillet['radius'])}")
    else:
        print("- Fillet: disabled")

    names = []
    if outputs.get("save_sldprt", True):
        names.append("SLDPRT")
    if outputs.get("export_step", True):
        names.append("STEP")
    if outputs.get("capture_png", True):
        names.append("PNG")
    print(f"- Outputs: {' / '.join(names)}")

    for note in cadplan.get("notes", []):
        print(f"- Note: {note}")


def show_featureplan(featureplan) -> None:
    print("FeaturePlan v2 preview:")
    print(json.dumps(featureplan.to_dict(), ensure_ascii=False, indent=2))


def show_execution_result(result) -> None:
    print(f"Executor status: {result.status}")
    print(f"Message: {result.message}")
    for operation in result.operations:
        print(f"- {operation.operation_id}: {operation.operation_type} [{operation.status}] {operation.message}")
    if result.outputs:
        print("Planned/created outputs:")
        for output in result.outputs:
            print(f"- {output}")


def executor_mode() -> str:
    mode = os.environ.get("AI_SW_EXECUTOR_MODE", "legacy_vba").strip().lower()
    if mode not in {"legacy_vba", "api_executor"}:
        raise ValueError("AI_SW_EXECUTOR_MODE must be legacy_vba or api_executor")
    return mode


def run_legacy_vba(cadplan: dict) -> int:
    show_plan(cadplan)
    if cadplan.get("template") != "mounting_plate":
        print("legacy_vba only supports mounting_plate. Use AI_SW_EXECUTOR_MODE=api_executor for blank_part.")
        return 1
    answer = input("Continue and write job files? y/n ").strip().lower()
    if answer != "y":
        print("Cancelled; job files were not written.")
        return 0

    cadplan_path = write_cadplan_json(cadplan)
    job_path = write_job_ini(cadplan)
    print(f"Generated: {cadplan_path}")
    print(f"Generated: {job_path}")
    print("Next: open SOLIDWORKS manually, import, and run macros/AI_Enterprise_Runner.bas.")
    return 0


def run_api_executor(cadplan: dict) -> int:
    featureplan = cadplan_to_featureplan(cadplan)
    show_featureplan(featureplan)

    policy_result = PolicyEngine().validate(featureplan)
    if not policy_result.allowed:
        print("Policy Engine rejected FeaturePlan:")
        for violation in policy_result.violations:
            prefix = f"{violation.operation_id}: " if violation.operation_id else ""
            print(f"- {prefix}{violation.code}: {violation.message}")
        return 1

    executor = SolidWorksApiExecutor()
    dry_run_result = executor.dry_run(featureplan)
    show_execution_result(dry_run_result)

    if os.environ.get("AI_SW_API_DRY_RUN", "").strip() == "1":
        print("AI_SW_API_DRY_RUN=1, stopping before SolidWorks connection.")
        return 0

    answer = input("Type YES_RUN_SOLIDWORKS_API to connect to the already-open SolidWorks instance: ").strip()
    if answer != "YES_RUN_SOLIDWORKS_API":
        print("Not confirmed. SolidWorks was not connected and no API execution was run.")
        return 0

    result = executor.execute(featureplan, dry_run=False)
    show_execution_result(result)
    return 0 if result.status == "executed" else 1


def run_featureplan_api_executor(featureplan) -> int:
    show_featureplan(featureplan)

    policy_result = PolicyEngine().validate(featureplan)
    if not policy_result.allowed:
        print("Policy Engine rejected FeaturePlan:")
        for violation in policy_result.violations:
            prefix = f"{violation.operation_id}: " if violation.operation_id else ""
            print(f"- {prefix}{violation.code}: {violation.message}")
        return 1

    executor = SolidWorksApiExecutor()
    dry_run_result = executor.dry_run(featureplan)
    show_execution_result(dry_run_result)

    if os.environ.get("AI_SW_API_DRY_RUN", "").strip() == "1":
        print("AI_SW_API_DRY_RUN=1, stopping before SolidWorks connection.")
        return 0

    answer = input("Type YES_RUN_SOLIDWORKS_API to connect to the already-open SolidWorks instance: ").strip()
    if answer != "YES_RUN_SOLIDWORKS_API":
        print("Not confirmed. SolidWorks was not connected and no API execution was run.")
        return 0

    result = executor.execute(featureplan, dry_run=False)
    show_execution_result(result)
    return 0 if result.status == "executed" else 1


def main() -> int:
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:]).strip()
    else:
        print("Enter a mounting-plate design request, then press Enter to generate CADPlan Lite.")
        prompt = input("> ").strip()
    if not prompt:
        print("No request entered; exiting.")
        return 1

    try:
        mode = executor_mode()
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Parse mode: {current_parse_mode()}")
    print(f"Executor mode: {mode}")

    if mode == "api_executor":
        try:
            featureplan = parse_prompt_to_featureplan(prompt)
        except LlmFeaturePlanError as exc:
            print(f"FeaturePlan provider parsing failed: {exc}")
            print("请检查 AI_SW_LLM_PROVIDER，或直接提供/测试 FeaturePlan。")
            return 1
        if featureplan is not None:
            return run_featureplan_api_executor(featureplan)

    try:
        cadplan = parse_prompt_to_cadplan(prompt)
    except ValueError as exc:
        if mode == "legacy_vba" and ("倒角" in prompt or re.search(r"\bC\s*\d", prompt, re.IGNORECASE)):
            print("Validation failed: 当前 legacy_vba 旧宏模式不支持倒角/C 倒角。")
            print("C2 倒角属于 P1 API Executor 能力，请切换 AI_SW_EXECUTOR_MODE=api_executor，并先用 AI_SW_API_DRY_RUN=1 验证执行计划。")
            return 1
        print(f"Validation failed: {exc}")
        return 1

    if mode == "legacy_vba":
        return run_legacy_vba(cadplan)
    return run_api_executor(cadplan)


if __name__ == "__main__":
    raise SystemExit(main())
