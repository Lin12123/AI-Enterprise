# AI-SW-Enterprise

AI-SW-Enterprise is the enterprise development branch of the local Codex + SOLIDWORKS AI-assisted CAD project.

## Enterprise Migration Notes

- The Enterprise compatibility layer remains in place: `app`, `macros`, `schemas`, and `tests`.
- The implemented legacy chain is: natural language -> CADPlan Lite -> `validator.py` -> `job.ini` -> fixed VBA Runner -> SOLIDWORKS automatic modeling.
- The API Executor chain is: FeaturePlan v2 -> Feature Registry -> Policy Engine -> fixed SolidWorks API Executor.
- Do not directly remove the Enterprise compatibility layer at this stage.
- Enterprise development should prioritize architecture, schema, policy, executor interface, and tests.

## Architecture

- `app/llm_parser.py`: local rule-based parser with optional LLM parsing fallback.
- `app/validator.py`: fills defaults and rejects dangerous paths, illegal fields, executable runtime content, and out-of-range dimensions.
- `app/job_writer.py`: writes only `workspace/jobs/current_cadplan.json` and `workspace/jobs/current_job.ini`.
- `macros/AI_Enterprise_Runner.bas`: fixed, reviewable SOLIDWORKS VBA Runner.
- `src/cad_dsl`: FeaturePlan v2 structures, schema, and Feature Registry.
- `src/policy`: Policy Engine for FeaturePlan safety and allowlist validation.
- `src/solidworks_api`: fixed API Executor boundary. It supports dry-run planning, executor-side operation ordering, and implemented mounting-plate API operations behind explicit user confirmation.
- `workspace/outputs`: the only generated model output root.

## Capability Status

- P0 implemented: `create_new_part`, `create_sketch`, `sketch_center_rectangle`, `sketch_circle`, `extrude_boss`, `extrude_cut`, `create_through_hole`, `add_fillet`, `save_sldprt`, `export_step`, `capture_png`, `rebuild_model`, and `validate_rebuild`.
- MVP composite implemented: `create_base_plate`, `cut_corner_holes`, `create_center_boss`, and `cut_center_hole`. `cut_corner_holes` supports hole center edge margin through `edge_margin`; `cut_center_hole` supports optional depth-controlled center holes and controlled `target` values `boss`/`base`.
- P1 implemented: `add_chamfer`, `create_blind_hole`, `create_counterbore_hole`, `create_countersink_hole`, `cut_slot`, `cut_rectangle_pocket`, `create_linear_pattern`, `create_circular_pattern`, `mirror_feature`, `set_material`, `set_custom_property`, `modify_named_dimension`, `create_offset_plane`, and `create_axis`.
- P1 scaffolded: none in the current P1 scope. The requested P1 operations are either implemented as fixed executor paths or rejected by policy when parameters are unsafe.
- scaffolded beyond P1: operation names, registry entries, docs, policy checks, and placeholder executor functions exist for revolve, sweep, loft, shell, rib, draft, legacy reference-plane/reference-axis placeholders, advanced mirror/body pattern operations, and broader reference geometry. These scaffolded operations are blocked from execution by Policy Engine.
- planned: broader official SOLIDWORKS part feature API mappings, more sketch features, surface features, multi-body parts, assemblies, 2D drawings, and modification of existing models.
- unsupported: explicitly rejected capabilities or inputs that are outside the current product boundary, safety policy, or part-modeling roadmap. Unsupported items must not execute and should not be presented as planned work unless the capability matrix is intentionally updated.

PRD P0 status: P0 atomic operations are registered, policy-checked, dry-run visible, and connected to fixed executor code paths. P1 status: the 14 requested P1 operations are registered, policy-checked, dry-run visible, and connected to fixed executor code paths. Real API execution still requires explicit user confirmation and an already-open SolidWorks instance.

This project does not claim support for every official SOLIDWORKS feature API. See `docs/solidworks_feature_capability_matrix.md`.
Unverified or non-implemented capabilities cannot execute: scaffolded, planned, unsupported, and unknown operations are rejected before any SolidWorks connection.

## Executor Modes

`AI_SW_EXECUTOR_MODE` controls the execution path:

- `legacy_vba`: old macro mode. This is the default compatibility path: CADPlan Lite -> `job.ini` -> fixed VBA Runner. It keeps the original MVP workflow available.
- `api_executor`: new API Executor mode. This path uses CADPlan Lite -> FeaturePlan v2 -> Policy Engine -> fixed SolidWorks API Executor. It does not use VBA as the main execution method.

Status meanings:

- `implemented`: executable in the current fixed executor, subject to Policy Engine checks and the documented safety gates.
- `scaffolded`: named and modeled for future implementation, but blocked from execution by policy.
- `planned`: documented roadmap item with no current executable operation.
- `unsupported`: intentionally not supported; the system should reject the request instead of attempting execution or silently mapping it to another operation.

Dry-run API planning:

```powershell
$env:AI_SW_EXECUTOR_MODE="api_executor"
$env:AI_SW_API_DRY_RUN="1"
python app/main.py "Create a 120x80x12 mm mounting plate with four M6 holes"
```

Real API execution requires an already-open SolidWorks instance and exact confirmation text:

```powershell
$env:AI_SW_EXECUTOR_MODE="api_executor"
python app/main.py
```

When prompted, type `YES_RUN_SOLIDWORKS_API` to allow the fixed API Executor to connect. Without that confirmation, SolidWorks is not connected.

Only implemented operations can execute. Scaffolded and planned operations are not completed capabilities.

## Safety Principles

- Run in a VM or isolated Windows user when possible.
- Do not use full filesystem access for normal development.
- Do not put important files or real customer CAD files inside this project.
- AI must not generate executable runtime VBA, Python, Shell, PowerShell, macros, scripts, commands, or code.
- The fixed VBA Runner is the only runtime macro.
- The new API Executor must remain fixed project code; LLM/Codex output may only be CADPlan or FeaturePlan.
- All API execution must flow through FeaturePlan -> Policy Engine / validator -> fixed API Executor.
- All generated outputs stay under `workspace/outputs`.
- User-defined `output_dir` is rejected.
- The app does not install dependencies, use the network by default, automatically open SOLIDWORKS, or automatically run `.swp` / `.bas` macros.

## Environment

- Windows
- Python 3.10+ using the standard library for the local test path
- Current API Executor development target: SOLIDWORKS 2019 SP5.0
- Part templates are read from the local SOLIDWORKS installation via the SOLIDWORKS API. The executor does not rely on a hardcoded template path and does not accept user-defined template paths.
- Other SOLIDWORKS versions are planned compatibility targets, not the current validation baseline.
- SOLIDWORKS, with the fixed VBA macro imported and run manually for `legacy_vba` mode

## Run The CLI

From the project root:

```powershell
python app/main.py
```

If `python` points to the Windows Store alias and the bundled interpreter exists in this project:

```powershell
.\Python314\python.exe app\main.py
```

Example request:

```text
Create a 120x80x12 mm mounting plate with four M6 clearance holes, a 30 mm diameter by 25 mm center boss, a 10 mm through center hole, and R3 outside fillets.
```

The CLI previews the CADPlan. It writes the job files only after the user confirms with `y`.

## Run AI-SW Workbench

AI-SW Workbench is the PySide6 desktop tool for AI-SW-Enterprise. It provides a local workflow for natural-language input, provider selection, FeaturePlanCandidate review, validation, dry run, and gated real SOLIDWORKS API execution.

Install PySide6 through the project requirements in your active virtual environment if it is not already available:

```powershell
pip install -r requirements.txt
```

Start it from the project root:

```powershell
python -m ui_desktop.main
```

or:

```powershell
python ui_desktop/main.py
```

Build the Windows desktop client with PyInstaller:

```cmd
build_desktop.bat
```

The packaged executable is generated at:

```text
dist\AI-SW Workbench\AI-SW Workbench.exe
```

This build step only packages the PySide6 desktop client. It does not start SOLIDWORKS, run macros, execute real API operations, or change the modeling pipeline.

Workbench flow:

1. Enter a natural-language CAD request.
2. Select provider: `local`, `openai`, or `rule_based`.
3. Click Generate Plan.
4. Review `design_intent`, `parameters`, `operations`, and JSON preview.
5. Resolve any `missing_info` by clarifying and regenerating the plan.
6. Click Validate.
7. Click Dry Run after validation passes.
8. For real SOLIDWORKS API execution, start SOLIDWORKS manually, type exactly `YES_RUN_SOLIDWORKS_API`, then click real execution.

Workbench safety notes:

- The UI does not directly control SOLIDWORKS.
- Natural language becomes FeaturePlanCandidate first.
- Validation and Policy Engine checks run before dry run or real run.
- Dry run never connects to SOLIDWORKS.
- Real run requires `YES_RUN_SOLIDWORKS_API` and `dry_run_passed`.
- Unknown, scaffolded, planned, and unsupported operations cannot execute.
- Workbench does not run macros, VBA, generated scripts, Shell, or PowerShell.
- Workbench job artifacts are stored under `outputs/jobs/job_xxx/`.
- Workbench does not save full API keys.

Workbench job files include:

- `input.txt`
- `featureplan_candidate.json`
- `validation_result.json`
- `dry_run.log`
- `dry_run_result.json`
- `execution.log`
- `outputs.json`
- `job_state.json`
- `ui_log.txt`

Read more:

- `docs/desktop_workbench_user_guide.md`
- `docs/desktop_workbench_design.md`
- `docs/desktop_workbench_real_solidworks_smoke_test.md`

## Generated Job Files

After confirmation, the app writes:

- `workspace/jobs/current_cadplan.json`
- `workspace/jobs/current_job.ini`

`current_job.ini` does not include `output_dir`. Output locations are controlled by the fixed VBA Runner and the project-local `workspace/outputs` boundary, not by user input, parser output, or LLM output.

## Optional LLM Structured Outputs

The natural-language parser uses a provider router. The default provider is local `rule_based` parsing, so the app can still run when cloud API keys, network, billing, or quotas are unavailable.

See `docs/local_llm_provider.md` for the local Ollama setup, provider differences, and fallback behavior.

Provider selection:

```powershell
$env:AI_SW_LLM_PROVIDER="rule_based"  # default
$env:AI_SW_LLM_PROVIDER="openai"      # optional cloud OpenAI
$env:AI_SW_LLM_PROVIDER="local"       # local Ollama OpenAI-compatible API
```

Local Ollama defaults:

```powershell
$env:AI_SW_LLM_PROVIDER="local"
$env:AI_SW_LOCAL_LLM_BASE_URL="http://localhost:11434/v1"
$env:AI_SW_LOCAL_LLM_MODEL="qwen2.5-coder:7b"
$env:AI_SW_LOCAL_LLM_API_KEY="<local-ollama-api-key>"
```

The local provider only targets `localhost` / `127.0.0.1` OpenAI-compatible endpoints and does not read `OPENAI_API_KEY`.

OpenAI cloud parsing is optional:

```powershell
pip install openai
$env:AI_SW_LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="<your-openai-api-key>"
python app/main.py
```

Rules:

- API keys are read only from the `OPENAI_API_KEY` environment variable.
- `OPENAI_API_KEY` is used only by the `openai` provider.
- Local Ollama provider settings are read only from `AI_SW_LOCAL_LLM_BASE_URL`, `AI_SW_LOCAL_LLM_MODEL`, and `AI_SW_LOCAL_LLM_API_KEY`.
- Do not write API keys into code, README files, logs, tests, FeaturePlan, CADPlan, or terminal output.
- If key status must be displayed, show only the first 6 and last 4 characters with `***` in the middle.
- If `OPENAI_API_KEY` is missing, the app asks the user to set the environment variable.
- Local `.env` files are ignored by git and must not be committed.
- Missing packages, missing API keys, network failures, quota/billing/rate-limit failures, Ollama connection failures, and JSON parsing failures fall back to `rule_based`.
- LLM output may only be CADPlan Lite JSON or FeaturePlan v2 JSON. CADPlan must pass `app/validator.py`; FeaturePlan must pass schema and Policy Engine checks before executor use.
- LLM output must not include `output_dir`, `path`, `file_path`, `save_path`, `absolute_path`, or `system_path`.
- LLM output must not include VBA, Python, Shell, PowerShell, macro, script, commands, code, or executable instructions.
- The CLI does not automatically run SOLIDWORKS or `.swp` macros.

## Run In SOLIDWORKS

1. Open SOLIDWORKS manually.
2. Open the VBA macro editor.
3. Import `macros/AI_Enterprise_Runner.bas`.
4. Run `main()`.
5. If face selection, cut direction, or fillet edge selection differs in your SOLIDWORKS version, replace the marked local API calls with recorded macro snippets.

## Outputs

- SLDPRT: `workspace/outputs/parts`
- STEP: `workspace/outputs/exports`
- PNG: `workspace/outputs/previews`
- Log: `workspace/logs/run_log.txt`

The VBA Runner uses `_v001`, `_v002`, `_v003` style names to avoid overwriting existing model outputs.

## Tests

```powershell
python -m unittest discover -s tests
```

With the project interpreter:

```powershell
.\Python314\python.exe -m unittest discover -s tests
```

## Known Limits

- Only the `mounting_plate` template is supported.
- API Executor support is limited to PRD P0 operations, the existing MVP composite operations, implemented P1 operations, and dry-run planning for allowlisted FeaturePlan v2 operations.
- Material mapping is driven by the project-local official SOLIDWORKS material index `resources/materials/material_catalog.json`. Local/cloud LLM providers should map user wording to an official SOLIDWORKS material name from that catalog, and the fixed executor applies the catalog's SolidWorks database/name mapping instead of enumerating SolidWorks material databases at runtime.
- pywin32 is not installed automatically. Install it manually before using confirmed real API execution.
- Assemblies, drawings, BOM, GD&T, surfaces, sheet metal, and PDM workflows are not supported yet.
- SOLIDWORKS is not launched automatically.
- Macros are not run automatically.
- Some SOLIDWORKS API selection behavior may need macro-recorded adjustments per SOLIDWORKS version.

## Upgrade Path

- Add more templates while keeping structured CADPlan / DrawingPlan output.
- Strengthen natural-language coverage and schema validation.
- Expand the Policy Engine.
- Add a fixed executor interface for SOLIDWORKS operations.
- Keep AI output declarative and non-executable.

