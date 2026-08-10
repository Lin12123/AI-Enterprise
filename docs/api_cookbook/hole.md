# Hole

Status: partially implemented.

## Implemented P1 Operations

- `create_blind_hole`: simple circular blind hole on an allowlisted plane or face selector.
- `create_counterbore_hole`: fixed counterbore represented by controlled circular cuts.
- `create_countersink_hole`: fixed countersink represented by controlled circular cuts.

## Implemented MVP Composite Hole Operations

- `cut_corner_holes`: four corner holes in a rectangular base. The location can be supplied as `offset_x`/`offset_y` from the part center, or as `edge_margin`, meaning hole-center distance from the nearest base edges.
- `cut_center_hole`: centered circular hole through the boss/base or to a controlled blind `depth`. Use `target: "boss"` for a hole starting from the center raised platform, and `target: "base"` for a hole starting from the rectangular base.

## FeaturePlan Examples

```json
{"op": "create_blind_hole", "params": {"plane": "top_face", "center": [0, 0], "diameter": 8, "depth": 5}}
```

```json
{"op": "create_counterbore_hole", "params": {"plane": "top_face", "center": [0, 0], "hole_diameter": 6.6, "counterbore_diameter": 12, "counterbore_depth": 4, "through_all": true}}
```

```json
{"op": "create_countersink_hole", "params": {"plane": "top_face", "center": [0, 0], "hole_diameter": 6.6, "countersink_diameter": 12, "angle": 90, "through_all": true}}
```

```json
{"op": "cut_corner_holes", "params": {"diameter": 6.6, "edge_margin": 10, "through_all": true}}
```

```json
{"op": "cut_center_hole", "params": {"diameter": 10, "target": "boss", "depth": 37, "through_all": false}}
```

## Parameters

- `plane`: allowlisted sketch plane or face selector, such as `top_face`, `Top`, `Front`, or `Right`.
- `center`: `[x, y]` center coordinate in mm. Negative coordinates are allowed as positions.
- `diameter`: blind-hole diameter in mm, must be positive.
- `hole_diameter`: main hole diameter for counterbore/countersink operations, must be positive.
- `depth`: blind hole depth in mm, must be positive.
- `counterbore_diameter`: counterbore relief diameter in mm, must be greater than `hole_diameter`.
- `counterbore_depth`: counterbore relief depth in mm, must be positive.
- `countersink_diameter`: countersink top diameter in mm, must be greater than `hole_diameter`.
- `angle`: countersink angle in degrees, policy range is greater than 0 and no more than 180.
- `through_all`: optional boolean for counterbore/countersink main through cut.
- `offset_x` / `offset_y`: corner-hole center offsets from the rectangular base center in mm.
- `edge_margin`: corner-hole center distance from the nearest rectangular base edges in mm. The fixed executor converts it to center offsets using the current base length and width.
- `cut_center_hole.depth`: optional center-hole blind cut depth in mm. If `depth` is present and `through_all` is omitted, the executor treats the center hole as a blind cut.
- `cut_center_hole.target`: `boss` or `base`. `boss` requires a preceding `create_center_boss` operation and selects the boss top face before sketching.

## Notes

- All FeaturePlan dimensions are mm and are converted to meters inside the fixed executor.
- User paths, output directories, scripts, macros, and commands are not accepted.
- These operations must pass Feature Registry and Policy Engine before any API execution.

## Current Limits

- `create_blind_hole` is a simple circular blind cut, not Hole Wizard metadata.
- `create_counterbore_hole` is implemented as main circular cut plus counterbore relief.
- `create_countersink_hole` is implemented as main circular cut plus shallow top relief; full conical countersink geometry is planned.
- `cut_corner_holes.edge_margin` requires a base plate earlier in the same FeaturePlan so the executor can calculate offsets.
- `cut_center_hole.depth` is a fixed blind cut depth, not Hole Wizard metadata.
- If `cut_center_hole.target` is `boss` but no center boss exists in executor state, execution is blocked instead of falling back to the base face.
- Threaded holes and Hole Wizard standard libraries are not implemented.

## Test Method

- `python -m unittest tests.test_p1_policy_engine`
- `python -m unittest tests.test_p1_api_executor_dryrun`
- `python -m unittest tests.test_p1_api_executor_build`
- `python -m unittest tests.test_p1_featureplan_examples`
