# API Cookbook

## Status

- implemented: cookbook pages document P0 and P1 fixed executor operations. Examples are declarative FeaturePlan snippets, not executable scripts.
- scaffolded: P2/P3 cookbook topics and executor boundaries are documented where implementation is not complete.
- planned: broader official SOLIDWORKS API mappings beyond the current fixed executor surface.

This cookbook is design documentation for the future API Executor. It must not be treated as generated runtime code. Do not auto-run SOLIDWORKS, macros, shell commands, or generated scripts from these pages.

Rules for cookbook examples:

- Prefer fixed executor operations over generated scripts.
- Keep all examples non-destructive by default.
- Avoid customer file paths and real CAD data.
- Document input schemas, validation expectations, and controlled output paths.

## Topics

- [Extrusion](extrusion.md)
- [Cut](cut.md)
- [Hole](hole.md)
- [Fillet and Chamfer](fillet_chamfer.md)
- [Pattern](pattern.md)
- [Material and Properties](material_properties.md)
- [Modify Named Dimension](modify_named_dimension.md)
- [Reference Geometry](reference_geometry.md)
- [Revolve, Sweep, and Loft](revolve_sweep_loft.md)
- [Shell, Rib, and Draft](shell_rib_draft.md)
