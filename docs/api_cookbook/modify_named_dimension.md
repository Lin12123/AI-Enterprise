# Modify Named Dimension

Status: implemented.

## Implemented P1 Operation

- `modify_named_dimension`

## FeaturePlan Example

```json
{"op": "modify_named_dimension", "params": {"dimension_name": "D_base_length", "value": 150}}
```

## Parameters

- `dimension_name`: allowlisted named dimension, such as `D_base_length`.
- `value`: new dimension value in mm, must be positive.

## Notes

- The operation is registered, policy-checked, and executable against the active model.
- Only allowlisted dimension names may be modified.
- Existing CAD files must not be opened or overwritten by this operation in the current stage.

## Current Limits

- The active model must already contain the named dimension.
- Feature deletion, suppression, rename, and reorder operations are not included.
- Editing existing customer CAD files is outside the current safe execution boundary.

## Test Method

- `python -m unittest tests.test_p1_policy_engine`
- `python -m unittest tests.test_p1_api_executor_dryrun`
- `python -m unittest tests.test_p1_api_executor_build`
