# Part Modeling Operation Mapping

This mapping is conservative and mirrors the Feature Registry. Scaffolded operations are blocked by Policy Engine and are not executable capabilities.

| PRD Level | Operation | Status | Notes |
| --- | --- | --- | --- |
| P0 | `create_new_part` | implemented | Fixed executor path. |
| P0 | `create_sketch` | implemented | Allowlisted planes/faces only. |
| P0 | `sketch_center_rectangle` | implemented | Center rectangle only. |
| P0 | `sketch_circle` | implemented | Circle only. |
| P0 | `extrude_boss` | implemented | One-side/midplane only. |
| P0 | `extrude_cut` | implemented | Through-all or blind cut. |
| P0 | `create_through_hole` | implemented | Simple circular through hole. |
| P0 | `add_fillet` | implemented | Current outer-edge selector only. |
| P1 | `create_blind_hole` | implemented | Simple circular blind hole. |
| P1 | `cut_rectangle_pocket` | implemented | Centered rectangular blind pocket. |
| P1 | `add_chamfer` | implemented | Outer-edge chamfer only. |
| P1 | `create_counterbore_hole` | implemented | Fixed cuts; full Hole Wizard metadata planned. |
| P1 | `create_countersink_hole` | implemented | Fixed cuts; full conical Hole Wizard countersink planned. |
| P1 | `cut_slot` | implemented | Straight center slot only. |
| P1 | `create_linear_pattern` | implemented | Seed feature selected by name. |
| P1 | `create_circular_pattern` | implemented | Seed feature selected by name. |
| P1 | `mirror_feature` | implemented | Feature mirror only. |
| P1 | `set_material` | implemented | Official SOLIDWORKS material catalog index. |
| P1 | `set_custom_property` | implemented | Property key allowlist. |
| P1 | `modify_named_dimension` | implemented | Named dimension allowlist. |
| P1 | `create_offset_plane` | implemented | Offset from allowlisted base plane. |
| P1 | `create_axis` | implemented | Two-plane axis only. |
