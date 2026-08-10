# Reference Geometry

Status: implemented for `create_offset_plane` and `create_axis`.

## Function

Reference geometry operations create controlled reference planes and axes from explicit allowlisted references.

## FeaturePlan Examples

```json
{"op": "create_offset_plane", "params": {"name": "Plane_Offset_25", "base_plane": "Top", "offset": 25}}
```

```json
{"op": "create_axis", "params": {"name": "Axis_Center", "reference_type": "two_planes", "references": ["Front", "Right"]}}
```

## Parameters

- `name`: stable reference geometry name. It must be unique within the FeaturePlan.
- `base_plane`: allowlisted base plane for offset plane creation.
- `offset`: offset distance in mm. It cannot be 0.
- `reference_type`: current supported value is `two_planes`.
- `references`: two explicit allowlisted planes used to define the axis.

## Policy Limits

- Empty, fuzzy, or unknown references are rejected.
- Offset plane names and axis names must be unique.
- Only allowlisted base planes are accepted.
- User-selected arbitrary faces and path-like fields are rejected.

## dry_run Test

```powershell
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_016_offset_plane_dry_run_and_uniqueness_rejection
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_017_create_axis_dry_run_and_reference_rejection
```

## Current Limitations

- Offset planes are supported only from allowlisted base planes.
- Axes are supported only from two-plane references.
- Points, cylinder-derived axes, midplanes, and angle planes are planned future work.
