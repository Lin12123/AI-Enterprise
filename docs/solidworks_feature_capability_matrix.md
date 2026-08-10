# SOLIDWORKS Feature Capability Matrix

This matrix is intentionally conservative. The project does not claim support for all official SOLIDWORKS APIs.

Status values are limited to `implemented`, `scaffolded`, `planned`, and `unsupported`.

| Category | Feature / Operation | FeaturePlan op | Status | Executor file | Notes |
| --- | --- | --- | --- | --- | --- |
| Document Lifecycle | New Part | `create_new_part` | implemented | `src/solidworks_api/model_builder.py` | Creates a new part through the configured SolidWorks default part template; no user path accepted. |
| Base Features | Extrude rectangular base | `create_base_plate` | implemented | `src/solidworks_api/features/base_plate.py` | Creates a centered rectangle on Top Plane and extrudes it. Live API behavior still needs SOLIDWORKS-version validation. |
| Base Features | Extrude Boss | `extrude_boss` | implemented | `src/solidworks_api/features/extrude.py` | Fixed one-side/midplane extrusion for closed sketches. |
| Base Features | Revolve Boss | `create_revolve_boss` | scaffolded | `src/solidworks_api/features/revolve.py` | Registry entry only; not executable. |
| Base Features | Sweep Boss | `create_sweep_boss` | scaffolded | `src/solidworks_api/features/sweep.py` | Registry entry only; not executable. |
| Base Features | Loft Boss | `create_loft_boss` | scaffolded | `src/solidworks_api/features/loft.py` | Registry entry only; not executable. |
| Cut Features | Extruded Cut | `extrude_cut` | implemented | `src/solidworks_api/features/cut.py` | Fixed through-all or blind extruded cut. |
| Cut Features | Extruded Cut corner holes | `cut_corner_holes` | implemented | `src/solidworks_api/features/hole.py` | Four circular holes only; accepts center offsets or `edge_margin` as hole-center distance from base edges. Through-all call has TODO for version validation. |
| Cut Features | Extruded Cut center hole | `cut_center_hole` | implemented | `src/solidworks_api/features/hole.py` | Center circular through or depth-controlled blind cut only; `target=boss` starts from the raised platform and requires a preceding center boss. Through-all call has TODO for version validation. |
| Cut Features | Slot Cut | `cut_slot` | implemented | `src/solidworks_api/features/cut.py` | Straight center slot using a stable rectangular slot profile by default; experimental native `CreateSketchSlot` path is opt-in only for validated COM environments. |
| Cut Features | Rectangular Pocket | `cut_rectangle_pocket` | implemented | `src/solidworks_api/features/cut.py` | Centered rectangular blind pocket only; uses fixed rectangle sketch plus blind cut. |
| Cut Features | Revolved Cut | `create_revolve_cut` | scaffolded | `src/solidworks_api/features/revolve.py` | Registry entry only; not executable. |
| Cut Features | Swept Cut | `create_sweep_cut` | scaffolded | `src/solidworks_api/features/sweep.py` | Registry entry only; not executable. |
| Cut Features | Lofted Cut | `create_loft_cut` | scaffolded | `src/solidworks_api/features/loft.py` | Registry entry only; not executable. |
| Hole Features | Simple Hole | `cut_corner_holes`, `cut_center_hole` | implemented | `src/solidworks_api/features/hole.py` | Limited to current mounting-plate holes; corner holes support `edge_margin`, center hole supports optional `depth` and controlled `target`. |
| Hole Features | Through Hole | `create_through_hole` | implemented | `src/solidworks_api/features/hole.py` | Simple circular through hole on allowlisted plane/face selector. |
| Hole Features | Blind Hole | `create_blind_hole` | implemented | `src/solidworks_api/features/hole.py` | Simple circular blind hole on an allowlisted plane/face selector. |
| Hole Features | Counterbore | `create_counterbore_hole` | implemented | `src/solidworks_api/features/hole.py` | Fixed circular cut plus counterbore relief; full Hole Wizard metadata is planned. |
| Hole Features | Countersink | `create_countersink_hole` | implemented | `src/solidworks_api/features/hole.py` | Fixed through cut plus shallow top relief; full conical Hole Wizard countersink is planned. |
| Hole Features | Tapped Hole | n/a | planned | n/a | Not in Feature Registry yet. |
| Edge Features | Fillet | `add_fillet` | implemented | `src/solidworks_api/features/fillet.py` | Supports `outer_edges`; topology selection has TODO for production hardening. |
| Edge Features | Chamfer | `add_chamfer` | implemented | `src/solidworks_api/features/chamfer.py` | `outer_edges` and controlled `selected_edges` targets only. |
| Pattern/Mirror | Linear Pattern | `create_linear_pattern` | implemented | `src/solidworks_api/features/pattern.py` | Seed feature selected by name; controlled `create_through_hole` seeds such as `Hole1` can fall back to additional fixed hole cuts when native pattern COM calls are incompatible. Complex references are planned. |
| Pattern/Mirror | Circular Pattern | `create_circular_pattern` | implemented | `src/solidworks_api/features/pattern.py` | Seed feature and explicit axis selected by name. |
| Pattern/Mirror | Mirror | `mirror_feature` | implemented | `src/solidworks_api/features/mirror.py` | Feature mirror only; body mirror is not included. |
| Shape Modification | Shell | `add_shell` | scaffolded | `src/solidworks_api/features/shell.py` | Registry entry only; not executable. |
| Shape Modification | Draft | `add_draft` | scaffolded | `src/solidworks_api/features/draft.py` | Registry entry only; not executable. |
| Shape Modification | Rib | `add_rib` | scaffolded | `src/solidworks_api/features/rib.py` | Registry entry only; not executable. |
| Reference Geometry | Plane | `create_reference_plane` | scaffolded | `src/solidworks_api/features/reference_geometry.py` | Registry entry only; not executable. |
| Reference Geometry | Axis | `create_reference_axis` | scaffolded | `src/solidworks_api/features/reference_geometry.py` | Registry entry only; not executable. |
| Reference Geometry | Offset Plane | `create_offset_plane` | implemented | `src/solidworks_api/features/reference_geometry.py` | Offset plane from allowlisted base plane. |
| Reference Geometry | Axis (P1) | `create_axis` | implemented | `src/solidworks_api/features/reference_geometry.py` | Two-plane reference axis only. |
| Reference Geometry | Point | n/a | planned | n/a | Not in Feature Registry yet. |
| Sketch Support | Create Sketch | `create_sketch` | implemented | `src/solidworks_api/sketch_builder.py` | Creates a named sketch on allowlisted plane/face selectors. |
| Sketch Support | Rectangle | `sketch_center_rectangle` | implemented | `src/solidworks_api/sketch_builder.py` | Center rectangle in an active named sketch. |
| Sketch Support | Circle | `sketch_circle` | implemented | `src/solidworks_api/sketch_builder.py` | Circle in an active named sketch. |
| Sketch Support | Line | n/a | planned | n/a | Not in Feature Registry yet. |
| Sketch Support | Arc | n/a | planned | n/a | Not in Feature Registry yet. |
| Sketch Support | Slot | `cut_slot` | implemented | `src/solidworks_api/features/cut.py` | Slot sketch is exposed through fixed `cut_slot`; default execution uses a rectangular profile, while native rounded-end slot remains an experimental opt-in path. |
| Model Validation | Rebuild Model | `rebuild_model` | implemented | `src/solidworks_api/model_builder.py` | Calls fixed rebuild path and records call success/failure. |
| Model Validation | Validate Rebuild | `validate_rebuild` | implemented | `src/solidworks_api/model_builder.py` | Confirms rebuild path has completed without raising. |
| Output | Save SLDPRT | `outputs.save_sldprt` | implemented | `src/solidworks_api/model_builder.py` | Output path fixed under `workspace/outputs/parts`; versioned names avoid overwrite. |
| Output | Save SLDPRT Operation | `save_sldprt` | implemented | `src/solidworks_api/model_builder.py` | Explicit operation using controlled versioned output path. |
| Output | Export STEP | `outputs.export_step` | implemented | `src/solidworks_api/model_builder.py` | Output path fixed under `workspace/outputs/exports`; versioned names avoid overwrite. |
| Output | Export STEP Operation | `export_step` | implemented | `src/solidworks_api/model_builder.py` | Explicit operation using controlled versioned output path. |
| Output | Capture PNG | `outputs.capture_png` | implemented | `src/solidworks_api/model_builder.py` | Output path fixed under `workspace/outputs/previews`; versioned names avoid overwrite. |
| Output | Capture PNG Operation | `capture_png` | implemented | `src/solidworks_api/model_builder.py` | Explicit operation using controlled versioned output path. |
| Material / Properties | Set Material | `set_material` | implemented | `src/solidworks_api/features/material_properties.py` | Uses project-local official SOLIDWORKS material index `resources/materials/material_catalog.json`; no runtime SolidWorks material enumeration and no user material database path accepted. |
| Material / Properties | Set Custom Property | `set_custom_property` | implemented | `src/solidworks_api/features/material_properties.py` | Property key allowlist; document-level custom properties only. |
| Modify / Parameters | Modify Named Dimension | `modify_named_dimension` | implemented | `src/solidworks_api/features/modify.py` | Named dimension allowlist; modifies active model dimension objects only. |
| Assemblies | Assembly creation | n/a | planned | n/a | Not supported. |
| Drawings | 2D drawing creation | n/a | planned | n/a | Not supported. |
| Surfaces | Surface features | n/a | planned | n/a | Not supported. |
