# AI-SW Workbench User Guide

AI-SW Workbench is the PySide6 desktop tool for AI-SW-Enterprise. It gives users a local workflow for natural-language CAD requests, FeaturePlan review, validation, dry run, and controlled SOLIDWORKS API execution.

## Start The Desktop Tool

From the project root:

```powershell
python -m ui_desktop.main
```

Alternative:

```powershell
python ui_desktop/main.py
```

If PySide6 is missing, install project requirements in your virtual environment first. Do not store API keys in settings files.

## Basic Workflow

1. Open AI-SW Workbench.
2. Enter a natural-language part request in the large input box.
3. Select a provider:
   - `local`: local Ollama / OpenAI-compatible provider.
   - `openai`: cloud OpenAI provider, optional.
   - `rule_based`: local deterministic compatibility parser.
4. Click `Generate Plan`.
5. Review design intent, parameters, operations, and JSON preview.
6. If `missing_info` is shown, clarify the request or edit the plan in a later supported workflow before execution.
7. Click `Validate`.
8. If validation passes, click `Dry Run`.
9. If dry run passes and you want real SOLIDWORKS execution, type exactly:

   ```text
   YES_RUN_SOLIDWORKS_API
   ```

10. Click real execution. SOLIDWORKS must already be open.

## Reviewing The Generated Plan

After plan generation, the center workspace shows:

- `design_intent`: part type, main structure, coordinate basis, assumptions, and missing information.
- `parameters`: extracted and inferred dimensions or controlled settings.
- `operations`: FeaturePlan operations in planned order.
- JSON preview: the exact FeaturePlanCandidate saved for the job.

Workbench does not pass natural language directly to SOLIDWORKS. It always goes through FeaturePlan and policy checks.

## Handling Missing Info

`missing_info` means the parser or model could not safely determine a required design detail. For enterprise use, do not silently fabricate incomplete geometry. Clarify the requirement, regenerate the plan, then validate again.

## Validation

The `Validate` button runs the desktop validation chain:

- Dependency Resolver
- Constraint Validator
- Topological Sorter
- Schema Validator
- Policy Engine
- Feature Registry checks

Validation fails if the plan contains dangerous fields, unknown operations, missing references, cyclic dependencies, non-implemented operations, unsupported outputs, or unsafe geometry.

Validation results are saved under the current job directory:

```text
outputs/jobs/job_xxx/validation_result.json
```

## Dry Run

Dry run verifies that the plan is executable without connecting to SOLIDWORKS. It requires validation to pass first.

Dry run saves:

```text
outputs/jobs/job_xxx/dry_run.log
outputs/jobs/job_xxx/dry_run_result.json
```

Dry run never starts SOLIDWORKS, never calls `win32com`, and never runs macros.

## Real Run

Real run is guarded by multiple checks:

- confirmation must be exactly `YES_RUN_SOLIDWORKS_API`
- current job status must be `dry_run_passed`
- validation must have passed
- `blocking_errors` must be empty
- no dangerous fields are allowed
- unknown, scaffolded, planned, or unsupported operations are rejected
- output directory must remain under `outputs/jobs/job_xxx`
- execution must use the fixed API Executor path

Workbench does not run VBA and does not execute generated scripts. Real run calls the project-owned SOLIDWORKS API Executor only after all gates pass.

## Dry Run vs Real Run

- Dry run: validates and plans operations only; no SOLIDWORKS connection.
- Real run: after explicit confirmation, calls the fixed SOLIDWORKS API Executor against an already-open SOLIDWORKS instance.

## Outputs And Logs

Workbench job records are stored in:

```text
outputs/jobs/job_xxx/
```

Common files:

- `input.txt`: redacted user input
- `featureplan_candidate.json`: generated FeaturePlanCandidate
- `validation_result.json`: validation result
- `dry_run.log`: dry run text log
- `dry_run_result.json`: dry run structured result
- `execution.log`: real execution log
- `outputs.json`: recorded output files
- `job_state.json`: current job state
- `ui_log.txt`: UI log

Model outputs from the underlying API Executor may still be generated in the project-controlled workspace output folders according to executor policy. Workbench records those paths in `outputs.json`.

## Opening Output Folders

The Workbench result page may open only the current job directory under `outputs/jobs/job_xxx`. It must not open arbitrary user-provided paths.

## Common Errors

- Missing PySide6: install project requirements in the active virtual environment.
- Local provider unavailable: start Ollama or switch provider.
- OpenAI quota/authentication error: switch to local or rule_based provider.
- Validation failed: inspect `blocking_errors` and regenerate or correct the request.
- Dry run blocked: run validation first and fix all blocking errors.
- Real run rejected: check confirmation text, dry run status, validation result, and operation statuses.
- SOLIDWORKS connection failed: start SOLIDWORKS manually and confirm pywin32 is installed.

## Why UI Does Not Directly Control SOLIDWORKS

The UI is not a CAD executor. It is an orchestration surface. This keeps enterprise safety boundaries intact:

Natural language -> FeaturePlan -> validation/policy -> dry run -> explicit confirmation -> fixed API Executor.

This prevents LLM output, UI text, or user-provided paths from directly controlling SOLIDWORKS.

## Safety Boundaries

- Do not save or print full API keys.
- Do not accept user-defined output directories.
- Do not run macros from Workbench.
- Do not execute VBA, Python, Shell, PowerShell, or dynamic code from plans.
- Do not read customer CAD files automatically.
- Do not overwrite formal engineering files.
- Only implemented Feature Registry operations can execute.

## Future Extensions

Planned extensions should keep the same architecture:

- assemblies through an AssemblyPlan and assembly-specific Policy Engine
- drawings through DrawingPlan and drawing validators
- enterprise template libraries for controlled part families
- approved material/template catalogs
- richer job history and review workflows
- operator audit trail and approval workflow
