# AI-SW Enterprise Safety Policy

## Runtime Generation Rules

- The LLM must not generate VBA, Python, Shell, PowerShell, or any executable code at runtime.
- The LLM may only output CADPlan or DrawingPlan documents.
- Every CADPlan or DrawingPlan must pass validator and Policy Engine checks before execution.
- SolidWorks actions must be performed only by a fixed executor.

## File and Path Rules

- All output paths must be controlled by the project.
- Do not access paths outside the project workspace.
- Do not delete files.
- Do not read real customer CAD files.
- Do not overwrite formal engineering files.

## Enterprise Compatibility Rules

- Keep `app`, `macros`, `schemas`, and `tests` working while enterprise modules are introduced.
- Do not remove the Enterprise compatibility layer during the current migration stage.
