# Modify Dimension

Status: implemented for `modify_named_dimension`.

## Function

`modify_named_dimension` changes a controlled named dimension in the active model. It does not allow arbitrary feature-tree edits.

## FeaturePlan Example

```json
{"op": "modify_named_dimension", "params": {"dimension_name": "D_base_length", "value": 150}}
```

## Parameters

- `dimension_name`: must be from the editable named-dimension allowlist.
- `value`: new dimension value in mm. Must be greater than 0.

## Policy Limits

- Unknown dimensions are rejected.
- Value must be positive.
- Existing model modification must not overwrite original CAD files.

## dry_run Test

```powershell
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_015_modify_named_dimension_dry_run_and_rejection
```

## Current Limitations

- The dimension must already exist in the active model during real execution.
- Suppression, deletion, reorder, rename, and arbitrary feature-tree operations are not implemented.
