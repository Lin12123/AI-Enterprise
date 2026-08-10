# Pattern

Status: implemented.

## Implemented P1 Operations

- `create_linear_pattern`
- `create_circular_pattern`
- `mirror_feature`

## FeaturePlan Examples

```json
{"op": "create_linear_pattern", "params": {"seed_feature": "hole_001", "direction": "x", "count": 3, "spacing": 20}}
```

```json
{"op": "create_circular_pattern", "params": {"seed_feature": "hole_001", "axis": "center_axis", "count": 6, "angle": 360}}
```

```json
{"op": "mirror_feature", "params": {"seed_feature": "pocket_001", "mirror_plane": "Front"}}
```

## Parameters

- `seed_feature`: explicit feature name/id to pattern or mirror.
- `direction`: linear pattern direction, allowlisted as `x`, `y`, or `z`.
- `count`: pattern instance count, must be greater than 1 and capped by policy.
- `spacing`: linear pattern spacing in mm, must be positive.
- `axis`: circular pattern axis name/id.
- `angle`: circular pattern angle in degrees, greater than 0 and up to 360.
- `mirror_plane`: allowlisted mirror plane, such as `Top`, `Front`, `Right`, or controlled center planes.

## Notes

- Pattern and mirror operations use fixed seed feature selection by name.
- For `create_through_hole` seeds, `create_linear_pattern` can create additional controlled hole cuts directly when the native SOLIDWORKS linear-pattern COM call rejects the current signature.
- Policy rejects missing seed features, invalid directions, invalid counts, and non-allowlisted mirror planes.
- Body mirror, sketch pattern, table pattern, fill pattern, and curve-driven pattern are not included.

## Current Limits

- Seed feature selection is name-based and must be stable.
- The fixed hole fallback currently covers linear X/Y hole arrays only.
- Advanced pattern references and body patterning are planned future work.
- Circular pattern axis hardening remains limited to controlled named axes.

## Test Method

- `python -m unittest tests.test_p1_policy_engine`
- `python -m unittest tests.test_p1_api_executor_dryrun`
- `python -m unittest tests.test_p1_api_executor_build`
