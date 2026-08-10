# Cut

Status: partially implemented.

## Implemented P1 Operations

- `cut_rectangle_pocket`
- `cut_slot`

## FeaturePlan Examples

```json
{"op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [20, 0], "length": 35, "width": 18, "depth": 4}}
```

```json
{"op": "cut_slot", "params": {"plane": "top_face", "center": [-20, 0], "length": 30, "width": 8, "through_all": true}}
```

## Parameters

- `plane`: allowlisted sketch plane or face selector.
- `center`: `[x, y]` center coordinate in mm. Negative coordinates are allowed as positions.
- `length`: pocket or slot length in mm, must be positive.
- `width`: pocket or slot width in mm, must be positive.
- `depth`: rectangular pocket depth in mm, must be positive.
- `through_all`: optional slot cut mode. If false, the executor uses a controlled blind cut depth.
- `angle`: reserved slot orientation field; current fixed executor supports straight center slots only.

## Notes

- `cut_rectangle_pocket` creates a centered rectangle and applies a blind cut.
- `cut_slot` uses a fixed `CreateSketchSlot` path and controlled cut operation.
- All dimensions are mm in FeaturePlan and converted to meters by the executor.
- User paths, scripts, macros, and arbitrary commands are rejected.

## Current Limits

- `cut_rectangle_pocket` supports centered rectangular blind pockets only.
- `cut_slot` supports straight center slots only.
- Complex curved slots, angled slots, and arbitrary profile cuts are planned future work.

## Test Method

- `python -m unittest tests.test_p1_policy_engine`
- `python -m unittest tests.test_p1_api_executor_dryrun`
- `python -m unittest tests.test_p1_api_executor_build`
- `python -m unittest tests.test_p1_featureplan_examples`
