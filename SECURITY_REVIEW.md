# SECURITY_REVIEW.md

Security review for the current Enterprise implementation.

## Checklist

1. Delete-file logic: no automatic delete-file behavior was found in Python or VBA runtime code. Cleanup of old outputs remains a manual user action.
2. Shell / PowerShell / subprocess / os.system: runtime code does not use these capabilities.
3. Network requests: Python and VBA runtime code do not make network requests in the default local flow.
4. User-defined `output_dir`: `validator.py` and `job_writer.py` reject `output_dir`; output roots are controlled by project code.
5. Overwrite behavior: Python writes fixed `current_*` job files; VBA output uses versioned names such as `_v001` and `_v002` for model outputs.
6. AI-generated VBA: not allowed. Runtime uses only the fixed `macros/AI_Enterprise_Runner.bas` macro.
7. Validator coverage: rejects negative dimensions, oversized dimensions, oversized holes, out-of-bounds hole positions, center holes larger than the boss, oversized fillets, illegal templates, illegal `part_name`, dangerous path fields, project-external path intent, and executable runtime content.
8. VBA prohibited capabilities: `AI_Enterprise_Runner.bas` contains no external command execution, file deletion, network, or registry logic.
9. Python project-local paths: path definitions are based on `PROJECT_ROOT`; writes are constrained to `workspace/jobs` and project-local output paths.
10. Manual macro execution: documentation directs the user to manually open SOLIDWORKS and run the fixed VBA Runner.

## Residual Risks

- SOLIDWORKS face selection, cut direction, and fillet edge selection may vary by version or modeling history and may need recorded macro snippets.
- `PROJECT_ROOT` in the VBA Runner is an absolute path for this local project. If the project folder moves, update that constant in the macro.
- Python overwrites `workspace/jobs/current_cadplan.json` and `workspace/jobs/current_job.ini`; this is the fixed job-file behavior and does not overwrite versioned model outputs.

## Decision

The current implementation satisfies the Enterprise safety boundary for the local flow: no network use by default, no dependency installation, no automatic external-app execution, no project-external output paths, and no AI-generated runtime VBA.
