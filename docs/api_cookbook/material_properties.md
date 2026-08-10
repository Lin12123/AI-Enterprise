# Material Properties

Status: implemented for `set_material` and `set_custom_property`.

## Function

Material and property operations set controlled metadata on the active part through fixed executor functions.

Materials are resolved from `resources/materials/material_catalog.json`, which is a project-local index of official SOLIDWORKS material entries. The local or cloud LLM should map user wording, such as `Aluminum_6061` or `6061 aluminum`, to the closest official SOLIDWORKS material name in that catalog.

New FeaturePlans should prefer official SOLIDWORKS material display names in `set_material.params.material`, for example `6061 Alloy` or `AISI 304`. `material_id` remains accepted for backward compatibility, but it is not the preferred LLM output.

## FeaturePlan Examples

```json
{"op": "set_material", "params": {"material": "6061 Alloy"}}
```

```json
{"op": "set_material", "params": {"material": "AISI 304"}}
```

```json
{"op": "set_custom_property", "params": {"key": "PartNumber", "value": "P1-001"}}
```

## Parameters

- `material`: official SOLIDWORKS material display name from `resources/materials/material_catalog.json`.
- `material_id`: optional backward-compatible catalog id, not preferred for new LLM output.
- `key`: custom property key from the allowlist.
- `value`: non-empty property value.

Allowed property keys:

- `PartNumber`
- `Description`
- `Designer`
- `ProjectNo`
- `Revision`
- `MaterialSpec`

## Policy Limits

- Materials outside the official SOLIDWORKS material catalog index are rejected.
- Search terms in the catalog help natural-language mapping only; they are not custom executable material definitions.
- Custom property keys outside the allowlist are rejected.
- User material database paths are not accepted.
- Executable text fields and user output paths are rejected recursively.

## dry_run Test

```powershell
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_013_material_allowlist_dry_run_and_rejection
python -m unittest tests.test_p1_integration_dryrun.TestP1IntegrationDryRun.test_tc_p1_014_custom_property_allowlist_dry_run_and_rejection
```

## Current Limitations

- The executor does not enumerate SOLIDWORKS material databases at runtime.
- Real material application still depends on the target SOLIDWORKS installation containing one of the catalog's official candidate database/name entries.
- If a SOLIDWORKS version or language pack uses a different official display name, update `resources/materials/material_catalog.json`; do not accept user-provided material database paths in FeaturePlan.
- Custom properties are document-level properties only.
- Configuration-specific properties are planned future work.
