"""Feature allowlist for FeaturePlan v2 operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class FeatureDefinition:
    op: str
    status: str
    description: str
    parameter_schema: Mapping[str, object] = field(default_factory=dict)
    executor_function: str = ""
    documentation_path: str = ""
    limitations: tuple[str, ...] = ()

    @property
    def type(self) -> str:
        return self.op

    @property
    def allowed_parameters(self) -> set[str]:
        properties = self.parameter_schema.get("properties", {})
        if isinstance(properties, dict):
            return set(properties)
        return set()

    @property
    def required_parameters(self) -> tuple[str, ...]:
        required = self.parameter_schema.get("required", ())
        if isinstance(required, (list, tuple)):
            return tuple(str(value) for value in required)
        return ()


@dataclass(frozen=True)
class FeatureRegistry:
    features: Mapping[str, FeatureDefinition] = field(default_factory=dict)

    def get(self, op: str) -> FeatureDefinition | None:
        return self.features.get(op)

    def require(self, op: str) -> FeatureDefinition:
        definition = self.get(op)
        if definition is None:
            raise KeyError(f"Feature is not registered: {op}")
        return definition

    def allowed_types(self) -> set[str]:
        return set(self.features)


def default_registry() -> FeatureRegistry:
    def schema(required: tuple[str, ...], optional: tuple[str, ...] = ()) -> dict[str, object]:
        return {
            "type": "object",
            "required": list(required),
            "properties": {name: {} for name in required + optional},
            "additionalProperties": False,
        }

    features = {
        "create_new_part": FeatureDefinition(
            op="create_new_part",
            status="implemented",
            description="Create a new part document as an explicit FeaturePlan operation.",
            parameter_schema=schema((), ("template", "part_name")),
            executor_function="create_new_part",
            documentation_path="docs/api_executor_architecture.md",
            limitations=("uses the configured SolidWorks default part template; user-provided paths are not accepted",),
        ),
        "create_sketch": FeatureDefinition(
            op="create_sketch",
            status="implemented",
            description="Create a named sketch on an allowlisted plane or face selector.",
            parameter_schema=schema(("name", "plane"), ("host",)),
            executor_function="create_sketch",
            documentation_path="docs/api_cookbook/extrusion.md",
            limitations=("allowlisted plane selectors only",),
        ),
        "sketch_center_rectangle": FeatureDefinition(
            op="sketch_center_rectangle",
            status="implemented",
            description="Add a centered rectangle to an existing named sketch.",
            parameter_schema=schema(("sketch", "center", "length", "width")),
            executor_function="sketch_center_rectangle",
            documentation_path="docs/api_cookbook/extrusion.md",
            limitations=("requires an active named sketch",),
        ),
        "sketch_circle": FeatureDefinition(
            op="sketch_circle",
            status="implemented",
            description="Add a circle to an existing named sketch.",
            parameter_schema=schema(("sketch", "center", "diameter")),
            executor_function="sketch_circle",
            documentation_path="docs/api_cookbook/hole.md",
            limitations=("requires an active named sketch",),
        ),
        "extrude_boss": FeatureDefinition(
            op="extrude_boss",
            status="implemented",
            description="Extrude a closed sketch as a boss/base feature.",
            parameter_schema=schema(("sketch", "depth"), ("direction", "merge_result")),
            executor_function="extrude_boss",
            documentation_path="docs/api_cookbook/extrusion.md",
            limitations=("one_side and midplane directions only",),
        ),
        "extrude_cut": FeatureDefinition(
            op="extrude_cut",
            status="implemented",
            description="Extrude-cut a closed sketch.",
            parameter_schema=schema(("sketch",), ("depth", "through_all", "direction")),
            executor_function="extrude_cut",
            documentation_path="docs/api_cookbook/cut.md",
            limitations=("through_all or blind depth only",),
        ),
        "create_through_hole": FeatureDefinition(
            op="create_through_hole",
            status="implemented",
            description="Create one simple through hole on an allowlisted plane or face.",
            parameter_schema=schema(("plane", "center", "diameter"), ("through_all", "host")),
            executor_function="create_through_hole",
            documentation_path="docs/api_cookbook/hole.md",
            limitations=("simple circular through hole only",),
        ),
        "create_blind_hole": FeatureDefinition(
            op="create_blind_hole",
            status="implemented",
            description="Create one simple blind circular hole on an allowlisted plane or face.",
            parameter_schema=schema(("plane", "center", "diameter", "depth"), ("host",)),
            executor_function="create_blind_hole",
            documentation_path="docs/api_cookbook/holes.md",
            limitations=("simple circular blind hole only; no Hole Wizard metadata",),
        ),
        "create_counterbore_hole": FeatureDefinition(
            op="create_counterbore_hole",
            status="implemented",
            description="Create a counterbore hole.",
            parameter_schema=schema(("plane", "center", "hole_diameter", "counterbore_diameter", "counterbore_depth"), ("through_all", "depth", "host")),
            executor_function="create_counterbore_hole",
            documentation_path="docs/api_cookbook/holes.md",
            limitations=("implemented as fixed circular through/blind cuts plus counterbore cut; full Hole Wizard metadata is planned",),
        ),
        "create_countersink_hole": FeatureDefinition(
            op="create_countersink_hole",
            status="implemented",
            description="Create a countersink hole.",
            parameter_schema=schema(("plane", "center", "hole_diameter", "countersink_diameter", "angle"), ("through_all", "depth", "host")),
            executor_function="create_countersink_hole",
            documentation_path="docs/api_cookbook/holes.md",
            limitations=("implemented as fixed circular through cut plus shallow top relief; full conical Hole Wizard countersink is planned",),
        ),
        "create_base_plate": FeatureDefinition(
            op="create_base_plate",
            status="implemented",
            description="Create the initial rectangular base plate.",
            parameter_schema=schema(("length", "width", "thickness"), ("plane",)),
            executor_function="create_base_plate",
            documentation_path="docs/api_cookbook/extrusion.md",
            limitations=("rectangle base only in current compatibility scope",),
        ),
        "cut_corner_holes": FeatureDefinition(
            op="cut_corner_holes",
            status="implemented",
            description="Cut four corner through holes in a rectangular base.",
            parameter_schema=schema(("diameter",), ("offset_x", "offset_y", "edge_margin", "through_all")),
            executor_function="cut_corner_holes",
            documentation_path="docs/api_cookbook/hole.md",
            limitations=(
                "four-hole rectangular pattern only",
                "either offset_x/offset_y or edge_margin must be provided",
                "edge_margin means hole center distance from each nearest base edge",
            ),
        ),
        "create_center_boss": FeatureDefinition(
            op="create_center_boss",
            status="implemented",
            description="Create a centered circular boss on the top face.",
            parameter_schema=schema(("diameter", "height"), ("plane", "host")),
            executor_function="create_center_boss",
            documentation_path="docs/api_cookbook/extrusion.md",
            limitations=("centered circular boss only",),
        ),
        "cut_center_hole": FeatureDefinition(
            op="cut_center_hole",
            status="implemented",
            description="Cut a centered circular hole through the boss/base or to a controlled depth.",
            parameter_schema=schema(("diameter",), ("depth", "target", "through_all")),
            executor_function="cut_center_hole",
            documentation_path="docs/api_cookbook/hole.md",
            limitations=(
                "centered circular hole only",
                "target can be boss or base; boss requires a preceding create_center_boss operation",
                "depth is a blind cut depth in mm; omit depth or set through_all=true for through cuts",
            ),
        ),
        "add_fillet": FeatureDefinition(
            op="add_fillet",
            status="implemented",
            description="Add fillets to allowlisted edge targets.",
            parameter_schema=schema(("radius",), ("target",)),
            executor_function="add_fillet",
            documentation_path="docs/api_cookbook/fillet_chamfer.md",
            limitations=("outer_edges target only in current compatibility scope",),
        ),
        "save_sldprt": FeatureDefinition(
            op="save_sldprt",
            status="implemented",
            description="Save the current part as SLDPRT with a controlled versioned filename.",
            parameter_schema=schema((), ()),
            executor_function="save_sldprt",
            documentation_path="docs/api_executor_architecture.md",
            limitations=("controlled workspace/outputs path only",),
        ),
        "export_step": FeatureDefinition(
            op="export_step",
            status="implemented",
            description="Export the current part as STEP with a controlled versioned filename.",
            parameter_schema=schema((), ()),
            executor_function="export_step",
            documentation_path="docs/api_executor_architecture.md",
            limitations=("controlled workspace/outputs path only",),
        ),
        "capture_png": FeatureDefinition(
            op="capture_png",
            status="implemented",
            description="Capture a PNG preview with a controlled versioned filename.",
            parameter_schema=schema((), ()),
            executor_function="capture_png",
            documentation_path="docs/api_executor_architecture.md",
            limitations=("controlled workspace/outputs path only",),
        ),
        "rebuild_model": FeatureDefinition(
            op="rebuild_model",
            status="implemented",
            description="Rebuild the current model and record the result.",
            parameter_schema=schema((), ()),
            executor_function="rebuild_model",
            documentation_path="docs/api_executor_architecture.md",
            limitations=("records rebuild call success/failure only",),
        ),
        "validate_rebuild": FeatureDefinition(
            op="validate_rebuild",
            status="implemented",
            description="Validate rebuild success before marking execution complete.",
            parameter_schema=schema((), ()),
            executor_function="validate_rebuild",
            documentation_path="docs/api_executor_architecture.md",
            limitations=("validates that rebuild path did not raise",),
        ),
        "add_chamfer": FeatureDefinition(
            op="add_chamfer",
            status="implemented",
            description="Add chamfer to selected edges.",
            parameter_schema=schema(("distance",), ("angle", "target")),
            executor_function="add_chamfer",
            documentation_path="docs/api_cookbook/chamfer.md",
            limitations=("outer_edges target only; uses fixed chamfer call and current edge selector",),
        ),
        "cut_slot": FeatureDefinition(
            op="cut_slot",
            status="implemented",
            description="Cut a slot.",
            parameter_schema=schema(("plane", "center", "length", "width"), ("through_all", "depth", "direction", "angle", "host")),
            executor_function="cut_slot",
            documentation_path="docs/api_cookbook/slot_pocket.md",
            limitations=(
                "straight center slot only; span direction can be x or y",
                "default executor path uses a stable rectangular slot profile on SolidWorks 2019-class COM environments",
                "native rounded-end slot via CreateSketchSlot is experimental and opt-in only",
            ),
        ),
        "cut_rectangle_pocket": FeatureDefinition(
            op="cut_rectangle_pocket",
            status="implemented",
            description="Cut a rectangular pocket.",
            parameter_schema=schema(("plane", "center", "length", "width", "depth"), ("host",)),
            executor_function="cut_rectangle_pocket",
            documentation_path="docs/api_cookbook/slot_pocket.md",
            limitations=("centered rectangular blind pocket only",),
        ),
        "create_linear_pattern": FeatureDefinition(
            op="create_linear_pattern",
            status="implemented",
            description="Create a linear pattern.",
            parameter_schema=schema(("seed_feature", "direction", "count", "spacing"), ()),
            executor_function="create_linear_pattern",
            documentation_path="docs/api_cookbook/pattern_mirror.md",
            limitations=("fixed seed-feature selection by name; complex directions and references are planned",),
        ),
        "create_circular_pattern": FeatureDefinition(
            op="create_circular_pattern",
            status="implemented",
            description="Create a circular pattern.",
            parameter_schema=schema(("seed_feature", "axis", "count"), ("angle",)),
            executor_function="create_circular_pattern",
            documentation_path="docs/api_cookbook/pattern_mirror.md",
            limitations=("fixed seed-feature selection by name; explicit axis selection hardening is planned",),
        ),
        "create_revolve_boss": FeatureDefinition(
            op="create_revolve_boss",
            status="scaffolded",
            description="Create a revolved boss.",
            parameter_schema=schema(("profile", "axis", "angle")),
            executor_function="create_revolve_boss",
            documentation_path="docs/api_cookbook/revolve_sweep_loft.md",
            limitations=("not executable yet",),
        ),
        "create_revolve_cut": FeatureDefinition(
            op="create_revolve_cut",
            status="scaffolded",
            description="Create a revolved cut.",
            parameter_schema=schema(("profile", "axis", "angle")),
            executor_function="create_revolve_cut",
            documentation_path="docs/api_cookbook/revolve_sweep_loft.md",
            limitations=("not executable yet",),
        ),
        "create_sweep_boss": FeatureDefinition(
            op="create_sweep_boss",
            status="scaffolded",
            description="Create a swept boss.",
            parameter_schema=schema(("profile", "path")),
            executor_function="create_sweep_boss",
            documentation_path="docs/api_cookbook/revolve_sweep_loft.md",
            limitations=("not executable yet",),
        ),
        "create_sweep_cut": FeatureDefinition(
            op="create_sweep_cut",
            status="scaffolded",
            description="Create a swept cut.",
            parameter_schema=schema(("profile", "path")),
            executor_function="create_sweep_cut",
            documentation_path="docs/api_cookbook/revolve_sweep_loft.md",
            limitations=("not executable yet",),
        ),
        "create_loft_boss": FeatureDefinition(
            op="create_loft_boss",
            status="scaffolded",
            description="Create a lofted boss.",
            parameter_schema=schema(("profiles",), ("guide_curves",)),
            executor_function="create_loft_boss",
            documentation_path="docs/api_cookbook/revolve_sweep_loft.md",
            limitations=("not executable yet",),
        ),
        "create_loft_cut": FeatureDefinition(
            op="create_loft_cut",
            status="scaffolded",
            description="Create a lofted cut.",
            parameter_schema=schema(("profiles",), ("guide_curves",)),
            executor_function="create_loft_cut",
            documentation_path="docs/api_cookbook/revolve_sweep_loft.md",
            limitations=("not executable yet",),
        ),
        "add_shell": FeatureDefinition(
            op="add_shell",
            status="scaffolded",
            description="Add a shell feature.",
            parameter_schema=schema(("thickness",), ("remove_faces",)),
            executor_function="add_shell",
            documentation_path="docs/api_cookbook/shell_rib_draft.md",
            limitations=("not executable yet",),
        ),
        "add_rib": FeatureDefinition(
            op="add_rib",
            status="scaffolded",
            description="Add a rib feature.",
            parameter_schema=schema(("profile", "thickness")),
            executor_function="add_rib",
            documentation_path="docs/api_cookbook/shell_rib_draft.md",
            limitations=("not executable yet",),
        ),
        "add_draft": FeatureDefinition(
            op="add_draft",
            status="scaffolded",
            description="Add draft to selected faces.",
            parameter_schema=schema(("angle", "target")),
            executor_function="add_draft",
            documentation_path="docs/api_cookbook/shell_rib_draft.md",
            limitations=("not executable yet",),
        ),
        "mirror_feature": FeatureDefinition(
            op="mirror_feature",
            status="implemented",
            description="Mirror a feature.",
            parameter_schema=schema(("seed_feature", "mirror_plane")),
            executor_function="mirror_feature",
            documentation_path="docs/api_cookbook/pattern_mirror.md",
            limitations=("fixed seed-feature and plane selection by name; body mirror is not included",),
        ),
        "set_material": FeatureDefinition(
            op="set_material",
            status="implemented",
            description="Set part material from the project-local official SOLIDWORKS material catalog.",
            parameter_schema=schema(("material",), ("material_id",)),
            executor_function="set_material",
            documentation_path="docs/api_cookbook/material_properties.md",
            limitations=("uses official SOLIDWORKS material entries from resources/materials/material_catalog.json; custom runtime material paths are not accepted",),
        ),
        "set_custom_property": FeatureDefinition(
            op="set_custom_property",
            status="implemented",
            description="Set an enterprise allowlisted custom property.",
            parameter_schema=schema(("key", "value"), ()),
            executor_function="set_custom_property",
            documentation_path="docs/api_cookbook/material_properties.md",
            limitations=("allowlisted property keys only; writes document-level custom properties",),
        ),
        "modify_named_dimension": FeatureDefinition(
            op="modify_named_dimension",
            status="implemented",
            description="Modify an allowlisted named dimension.",
            parameter_schema=schema(("dimension_name", "value"), ()),
            executor_function="modify_named_dimension",
            documentation_path="docs/api_cookbook/modify_dimension.md",
            limitations=("allowlisted dimension names only; modifies resolved dimension objects in the active model",),
        ),
        "create_offset_plane": FeatureDefinition(
            op="create_offset_plane",
            status="implemented",
            description="Create a named offset reference plane.",
            parameter_schema=schema(("name", "base_plane", "offset"), ()),
            executor_function="create_offset_plane",
            documentation_path="docs/api_cookbook/reference_geometry.md",
            limitations=("offset planes from allowlisted base planes only",),
        ),
        "create_axis": FeatureDefinition(
            op="create_axis",
            status="implemented",
            description="Create a named reference axis.",
            parameter_schema=schema(("name", "reference_type", "references"), ()),
            executor_function="create_axis",
            documentation_path="docs/api_cookbook/reference_geometry.md",
            limitations=("two-plane reference axes only",),
        ),
        "create_reference_plane": FeatureDefinition(
            op="create_reference_plane",
            status="scaffolded",
            description="Create a reference plane.",
            parameter_schema=schema(("definition",)),
            executor_function="create_reference_plane",
            documentation_path="docs/solidworks_feature_capability_matrix.md",
            limitations=("not executable yet",),
        ),
        "create_reference_axis": FeatureDefinition(
            op="create_reference_axis",
            status="scaffolded",
            description="Create a reference axis.",
            parameter_schema=schema(("definition",)),
            executor_function="create_reference_axis",
            documentation_path="docs/solidworks_feature_capability_matrix.md",
            limitations=("not executable yet",),
        ),
    }
    return FeatureRegistry(features=features)

