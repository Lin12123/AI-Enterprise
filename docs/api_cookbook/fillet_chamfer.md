# Fillet And Chamfer

Status: fillet implemented, chamfer implemented.

## Implemented P1 Operation

- `add_chamfer`: applies a fixed chamfer to an allowlisted edge target.

## FeaturePlan Example

```json
{"op": "add_chamfer", "params": {"target": "outer_edges", "distance": 2, "angle": 45}}
```

## Parameters

- `target`: allowlisted edge selector. Current implementation supports `outer_edges` and controlled `selected_edges`.
- `distance`: chamfer distance in mm, must be positive.
- `angle`: chamfer angle in degrees, policy range is greater than 0 and less than 90.

## Notes

- The executor derives edges from stable selectors rather than user-picked geometry.
- `add_fillet` remains implemented for `outer_edges` as a P0 edge operation.
- `add_chamfer` runs only after FeaturePlan passes Policy Engine.

## Current Limits

- Current `add_chamfer` supports `outer_edges` and controlled `selected_edges` only.
- Variable chamfer, two-distance chamfer, and face-set based chamfers are planned future work.

## Test Method

- `python -m unittest tests.test_p1_policy_engine`
- `python -m unittest tests.test_p1_api_executor_dryrun`
- `python -m unittest tests.test_p1_api_executor_build`
