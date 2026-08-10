# Holes

Status: implemented for `create_blind_hole`, `create_counterbore_hole`, and `create_countersink_hole`.

## Function

These operations create controlled hole features from declarative FeaturePlan parameters. They do not expose arbitrary Hole Wizard settings or user file paths.

## FeaturePlan Examples

```json
{"op": "create_blind_hole", "params": {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": 5}}
```

```json
{"op": "create_counterbore_hole", "params": {"plane": "top_face", "center": [0, 0], "hole_diameter": 6.6, "counterbore_diameter": 12, "counterbore_depth": 4}}
```

```json
{"op": "create_countersink_hole", "params": {"plane": "top_face", "center": [0, 0], "hole_diameter": 6.6, "countersink_diameter": 12, "angle": 90}}
```

## Parameters

- `plane`: allowlisted plane or face selector.
- `center`: `[x, y]` center coordinate in mm.
- `diameter`: blind-hole diameter in mm. Must be greater than 0.
- `depth`: blind-hole or optional blind main-cut depth in mm. Must be greater than 0 when used.
- `hole_diameter`: main hole diameter for counterbore/countersink. Must be greater than 0.
- `counterbore_diameter`: must be greater than `hole_diameter`.
- `counterbore_depth`: must be greater than 0.
- `countersink_diameter`: must be greater than `hole_diameter`.
- `angle`: countersink angle. Must be greater than 0 and no more than 180.
- `through_all`: optional boolean for counterbore/countersink main cut.

## Policy Limits

- Invalid planes, malformed centers, non-positive dimensions, and invalid diameter relationships are rejected.
- User-defined output paths and executable text fields are rejected recursively.
- Hole Wizard standards, tapped holes, and thread metadata are not accepted in P1 FeaturePlan.

## dry_run Test

```powershell
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_004_blind_hole_dry_run_passes
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_006_counterbore_hole_dry_run_passes
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_007_countersink_hole_dry_run_passes
```

## Current Limitations

- Blind holes are simple circular cuts.
- Counterbore and countersink are fixed executor paths, not complete Hole Wizard features.
- Full conical countersink validation against live SolidWorks versions remains future hardening.
