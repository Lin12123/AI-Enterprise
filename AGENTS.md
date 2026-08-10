# AGENTS.md

This project is a local Codex + SOLIDWORKS AI-assisted CAD Enterprise.

## Enterprise Development Rules

- Keep the Enterprise compatibility layer intact; do not break existing `app`, `macros`, or `tests`.
- Runtime LLM output must not include VBA, Python, Shell, PowerShell, or any executable code.
- The LLM may only output CADPlan, FeaturePlan, or DrawingPlan.
- Every CADPlan, FeaturePlan, or DrawingPlan must pass validator and Policy Engine checks.
- SolidWorks operations must be performed by a fixed Executor.
- Output paths must be controlled.
- Do not access paths outside the project.
- Do not delete files.
- Do not read real customer CAD files.
- Do not overwrite formal engineering files.

Core constraints:

- Work only inside the current project workspace.
- Do not access files outside the project.
- Do not request full access or bypass sandbox restrictions.
- Do not use Shell, PowerShell, subprocess, os.system, network requests, or registry operations in generated runtime code.
- Do not delete files.
- Do not install dependencies.
- Do not upload CAD files.
- All generated outputs must stay in `./workspace`.
- Do not accept user-defined `output_dir`.
- AI must not generate runtime VBA.
- The fixed VBA Runner is the only macro allowed at runtime.
- Enterprise supports only `mounting_plate`.
- Default unit is `mm`.
- SOLIDWORKS API lengths must be converted from mm to m.

## Natural Language Parsing Direction

- All new requirements must be implemented with the enterprise architecture in mind.
- Do not patch natural-language failures by continuously adding local fallback phrase-matching rules.
- In `api_executor` mode, natural language must be interpreted by the LLM using the current Feature Registry and capability policy, then emitted as FeaturePlan v2.
- When natural-language parsing fails, the system must fail clearly or ask for clarification. It must not silently fabricate a partial or incomplete FeaturePlan through local fallback rules.
- Adding a new modeling capability must update the Feature Registry, schema, policy, executor, docs, and tests so the LLM prompt can expose that capability automatically.
- Local rule parsing is allowed only for the legacy CADPlan Lite / `legacy_vba` compatibility path or explicitly bounded non-enterprise fallbacks; it must not become the primary API Executor semantic layer.
