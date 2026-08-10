# Chamfer

Status: implemented for `add_chamfer`.

## Function

`add_chamfer` adds a controlled chamfer to allowlisted edge selectors after the FeaturePlan passes the Policy Engine.

## FeaturePlan Example

```json
{"op": "add_chamfer", "params": {"target": "outer_edges", "distance": 2, "angle": 45}}
```

## Parameters

- `distance`: chamfer distance in mm. Must be greater than 0.
- `angle`: optional chamfer angle in degrees. Must be greater than 0 and less than 90.
- `target`: controlled selector. Allowed values are `outer_edges` and `selected_edges`.

## Policy Limits

- Fuzzy targets are rejected.
- User-provided paths, scripts, macros, commands, or runtime code fields are rejected recursively.
- Only implemented operations may reach the fixed executor.

## dry_run Test

```powershell
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_002_chamfer_dry_run_passes
```

## Current Limitations

- `outer_edges` depends on stable base topology.
- `selected_edges` must come from a controlled preselection path; arbitrary user-picked geometry is not accepted by FeaturePlan.
- Variable chamfers and two-distance chamfers are not implemented.
