# AI-SW Workbench Desktop Design

AI-SW Workbench is the desktop orchestration surface for AI-SW-Enterprise. It is a local PySide6 application for reviewing and executing the enterprise CAD pipeline safely.

## Product Positioning

The desktop tool is not a direct CAD scripting surface. It coordinates the existing AI-SW-Enterprise architecture:

```text
Natural language
  -> provider router: local / openai / rule_based
  -> FeaturePlanCandidate
  -> Dependency Resolver / Constraint Validator / Schema Validator / Policy Engine / Feature Registry
  -> dry_run execution plan
  -> explicit YES_RUN_SOLIDWORKS_API confirmation
  -> fixed SolidWorks API Executor
```

The UI helps the user inspect each stage before any real SOLIDWORKS API call is allowed.

## Why PySide6

PySide6 is used because AI-SW Workbench is a Windows engineering desktop tool:

- native desktop widgets and a stable local UI model
- good support for tables, logs, split panes, JSON previews, and status panels
- no browser, web server, Electron, React, Vue, or Streamlit dependency
- can call local Python services without adding a network API layer
- supports QThread background work for long-running local operations

## Implemented Desktop Capabilities

Current Workbench implementation includes:

- startup via `python -m ui_desktop.main` and `python ui_desktop/main.py`
- three-column UI: navigation, central work area, right status panel
- natural-language input and provider selection: `local`, `openai`, `rule_based`
- real `generate_plan` through the existing provider router
- real `validate_plan` through schema, registry, dependency, constraint, topological, and policy checks
- real `dry_run` through the existing API Executor dry-run path
- real_run safety gate with exact `YES_RUN_SOLIDWORKS_API` confirmation
- real_run integration point for the existing fixed SOLIDWORKS API Executor
- background Worker using QThread when PySide6 is available
- local JSON JobStore under `outputs/jobs`
- SettingsStore without API key persistence
- structured job artifacts: input, FeaturePlanCandidate, validation, dry_run, execution log, outputs JSON
- result page with controlled current-job-folder opening

## Core Components

- `ui_desktop/main.py`: desktop startup entry.
- `ui_desktop/app_window.py`: main Workbench window and UI orchestration.
- `ui_desktop/adapters/core_engine_adapter.py`: safe adapter between UI and the existing core pipeline.
- `ui_desktop/services/execution_worker.py`: background worker for generate, validate, dry_run, and real_run calls.
- `ui_desktop/services/job_store.py`: JSON job persistence under `outputs/jobs`.
- `ui_desktop/services/settings_store.py`: non-secret local settings.
- `ui_desktop/views/*`: page-level UI views.
- `ui_desktop/widgets/*`: reusable input, table, JSON, validation, log, and status widgets.

## Job State Model

Workbench uses these job states:

- `created`
- `planning`
- `need_user_input`
- `planned`
- `planned_modified`
- `validating`
- `validation_failed`
- `validation_passed`
- `dry_running`
- `dry_run_passed`
- `dry_run_failed`
- `awaiting_real_run_approval`
- `running`
- `succeeded`
- `failed`
- `cancelled`

The UI updates buttons and status labels from these states. Dry run is disabled until validation passes. Real run is blocked unless dry run has passed and the confirmation text is exact.

## Background Execution

Long-running operations are dispatched through `ExecutionWorker`:

- `generate_plan`
- `validate_plan`
- `dry_run`
- `real_run`

Worker signals include:

- `log_message`
- `step_started`
- `step_succeeded`
- `step_failed`
- `plan_generated`
- `validation_finished`
- `dry_run_finished`
- `real_run_finished`
- `job_failed`

The worker never bypasses `CoreEngineAdapter` and never directly calls SOLIDWORKS.

## Validation Design

Desktop validation returns:

- `passed`
- `dependency_result`
- `constraint_result`
- `schema_result`
- `policy_result`
- `registry_result`
- `execution_order`
- `warnings`
- `blocking_errors`
- `can_dry_run`

Unknown, scaffolded, planned, and unsupported operations are blocked before dry run or real run.

## Real Run Design

Real run requires:

- `YES_RUN_SOLIDWORKS_API`
- job state `dry_run_passed`
- passed validation result
- empty `blocking_errors`
- implemented operations only
- controlled current job output directory

After the gate passes, Workbench calls the fixed API Executor path. Automated tests inject a mock executor and never start SOLIDWORKS.

## Artifacts

All Workbench job artifacts are stored under:

```text
outputs/jobs/job_xxx/
```

Important artifacts:

- `input.txt`
- `featureplan_candidate.json`
- `validation_result.json`
- `dry_run.log`
- `dry_run_result.json`
- `execution.log`
- `outputs.json`
- `job_state.json`
- `ui_log.txt`

API keys and secret-like fields are redacted or omitted.

## Safety Boundaries

- UI never directly executes LLM output.
- UI never accepts user-defined `output_dir`.
- UI never runs VBA or macros.
- UI never executes Shell, PowerShell, Python, VBA, or generated code.
- Real SOLIDWORKS execution must use the fixed API Executor.
- All plans must pass validation and Policy Engine.
- Only implemented Feature Registry operations can execute.
- Automatic tests must not start SOLIDWORKS.

## Future Extensions

The same pattern should be used for:

- assembly modeling through AssemblyPlan
- 2D drawings through DrawingPlan
- enterprise template libraries
- approved material and manufacturing catalogs
- batch job review
- engineering approval workflows
- richer persistent job history
