# Slot And Pocket

Status: implemented for `cut_slot` and `cut_rectangle_pocket`.

## Function

`cut_slot` creates a controlled straight slot cut. It uses a stable rectangular through/blind slot sketch by default. The native SOLIDWORKS slot sketch API is available only as an experimental opt-in path for environments where that COM signature has been validated. `cut_rectangle_pocket` creates a centered rectangular blind pocket.

## FeaturePlan Examples

```json
{"op": "cut_slot", "params": {"plane": "top_face", "center": [-20, 0], "length": 30, "width": 8, "direction": "x", "through_all": false, "depth": 5}}
```

```json
{"op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [20, 0], "length": 35, "width": 18, "depth": 4}}
```

## Parameters

- `plane`: allowlisted plane or face selector.
- `center`: `[x, y]` center coordinate in mm.
- `length`: slot or pocket length in mm. Must be greater than 0.
- `width`: slot or pocket width in mm. Must be greater than 0.
- `direction`: optional slot span direction. Use `x` for base-length direction and `y` for base-width direction.
- `through_all`: optional slot mode.
- `depth`: required for rectangular pockets and required for blind slots when `through_all` is false.

## Policy Limits

- `cut_slot.length` must be greater than `cut_slot.width`.
- `cut_slot.direction` must be `x` or `y` when provided.
- Pocket `length`, `width`, and `depth` must be positive.
- Fuzzy planes and executable fields are rejected.

## dry_run Test

```powershell
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_008_slot_cut_dry_run_passes
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_009_rectangle_pocket_dry_run_passes
```

## Current Limitations

- Slots are straight center slots only.
- The executor supports `direction=x/y`; arbitrary slot rotation is still not part of the public FeaturePlan contract.
- The default executor path uses a rectangular slot profile for SolidWorks 2019-class COM stability; rounded slot ends are not guaranteed unless the experimental native slot API path is explicitly enabled and validated.
- Angled, curved, and arbitrary-profile slots are not implemented.
- Pockets are centered rectangles only.
