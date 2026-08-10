# FeaturePlan v2

## Status

- implemented: PRD P0 atomic operations, the 14 requested P1 operations, plus current MVP composite FeaturePlan operations `create_base_plate`, `cut_corner_holes`, `create_center_boss`, `cut_center_hole`, and `add_fillet`.
- scaffolded: remaining P2/P3 operations such as revolve, sweep, loft, shell, rib, draft, advanced mirror/body pattern operations, broader reference geometry, and advanced surface/body features.
- planned: broader natural-language generation of atomic FeaturePlan operations and full executor integration.

## Shape

FeaturePlan v2 is declarative JSON:

```json
{
  "version": "2.0",
  "unit": "mm",
  "document_type": "part",
  "part_name": "ai_mounting_plate",
  "operations": [
    {
      "id": "base_001",
      "op": "create_base_plate",
      "params": {
        "length": 120,
        "width": 80,
        "thickness": 12,
        "plane": "Top"
      }
    }
  ],
  "outputs": {
    "save_sldprt": true,
    "export_step": true,
    "capture_png": true
  }
}
```

## Rules

- Unit is `mm`.
- Operations must be allowlisted by the Feature Registry.
- Parameters must be allowlisted per operation.
- Dangerous path fields and executable runtime text are rejected by policy.
- Scaffolded and planned operations are blocked unless explicitly enabled for analysis-only use.

## PRD P0 Atomic Operation Status

Implemented: `create_new_part`, `create_sketch`, `sketch_center_rectangle`, `sketch_circle`, `extrude_boss`, `extrude_cut`, `create_through_hole`, `create_blind_hole`, `cut_rectangle_pocket`, `add_fillet`, `save_sldprt`, `export_step`, `capture_png`, `rebuild_model`, and `validate_rebuild`.

The older MVP composite operations remain available for compatibility.
