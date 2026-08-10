# Migration From VBA Runner

## Current Compatibility

The old flow remains intact:

Natural language -> CADPlan Lite -> `validator.py` -> `job.ini` -> fixed VBA Runner -> SOLIDWORKS.

This is implemented as a compatibility path and must not be removed during this migration.

## New Direction

The new flow is:

Natural language -> FeaturePlan v2 -> Feature Registry -> Policy Engine -> fixed API Executor -> SOLIDWORKS API.

## Migration Rules

- Do not auto-run SOLIDWORKS.
- Do not auto-run `.swp` or `.bas` macros.
- Do not generate runtime code and execute it.
- Do not install pywin32 automatically.
- Keep output paths controlled by project code.
- Keep legacy VBA assets available under `macros`.

## Next Milestones

1. Add tests for FeaturePlan schema, registry, and policy rejection cases.
2. Map CADPlan Lite mounting-plate output into FeaturePlan v2 operations.
3. Add a dry-run CLI command for FeaturePlan validation.
4. Implement the first fixed SOLIDWORKS API adapter only after policy coverage is in place.
