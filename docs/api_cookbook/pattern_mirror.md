# Pattern And Mirror

Status: implemented for `create_linear_pattern`, `create_circular_pattern`, and `mirror_feature`.

## Function

These operations repeat or mirror an explicit seed feature through controlled named references. For a seed made by `create_through_hole`, `create_linear_pattern` can use a fixed hole-instance fallback instead of the native SOLIDWORKS pattern API when COM pattern calls are incompatible.

## FeaturePlan Examples

```json
{"op": "create_linear_pattern", "params": {"seed_feature": "blind_001", "direction": "x", "count": 3, "spacing": 20}}
```

```json
{"op": "create_circular_pattern", "params": {"seed_feature": "blind_001", "axis": "Axis_01", "count": 6, "angle": 360}}
```

```json
{"op": "mirror_feature", "params": {"seed_feature": "pocket_001", "mirror_plane": "Front"}}
```

## Parameters

- `seed_feature`: explicit seed feature name/id. Fuzzy references are rejected.
- `direction`: linear pattern direction, allowlisted as `x`, `y`, or `z`.
- `count`: must be greater than 1 and no more than the system limit.
- `spacing`: linear pattern spacing in mm. Must be greater than 0.
- `axis`: explicit circular pattern axis.
- `angle`: circular pattern angle. Must be greater than 0 and no more than 360.
- `mirror_plane`: allowlisted mirror plane.

## Policy Limits

- Missing, fuzzy, or empty references are rejected.
- Body patterns and arbitrary geometry selection are not exposed through FeaturePlan.
- Scaffolded/planned pattern variants cannot execute.

## dry_run Test

```powershell
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_010_linear_pattern_dry_run_passes
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_011_circular_pattern_dry_run_passes
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_012_mirror_feature_dry_run_passes
```

## Current Limitations

- Selection is name-based and requires stable feature names.
- `create_linear_pattern` supports a controlled fallback for `create_through_hole` seeds such as `Hole1`; it creates additional hole cuts at the requested spacing.
- Non-hole seeds still depend on the native SOLIDWORKS pattern API and may require version-specific hardening.
- Body mirror, fill pattern, curve-driven pattern, and table pattern are not implemented.
