"""Hole feature scaffold."""

OPERATION_TYPE = "cut_center_hole"
STATUS = "implemented"


def _require_feature_result(feature: object, operation_name: str) -> object:
    if feature is None:
        raise RuntimeError(f"{operation_name} failed: API returned None")
    return feature


def _add_circle(sw_model: object, x_mm: float, y_mm: float, diameter_mm: float) -> None:
    from solidworks_api.units import mm_to_m

    sw_model.SketchManager.CreateCircleByRadius(mm_to_m(x_mm), mm_to_m(y_mm), 0, mm_to_m(diameter_mm) / 2)


def _through_all_cut(sw_model: object) -> object:
    # TODO: Validate FeatureCut3 through-all arguments on the target SOLIDWORKS version.
    return sw_model.FeatureManager.FeatureCut3(
        True, False, False, 1, 0, 0, 0,
        False, False, False, False, 0, 0, False, False, False, False,
        False, True, True, True, True, False, 0, 0, False,
    )


def _blind_cut(sw_model: object, depth_mm: float) -> object:
    from solidworks_api.units import mm_to_m

    depth_m = mm_to_m(depth_mm)
    feature = sw_model.FeatureManager.FeatureCut3(
        True, False, False, 0, 0, depth_m, 0,
        False, False, False, False, 0, 0, False, False, False, False,
        False, True, True, True, True, False, 0, 0, False,
    )
    if feature is not None:
        return feature
    # SOLIDWORKS 2019 can reject a blind cut with the default direction even when
    # the exact same sketch succeeds after flipping the cut direction.
    return sw_model.FeatureManager.FeatureCut3(
        True, False, True, 0, 0, depth_m, 0,
        False, False, False, False, 0, 0, False, False, False, False,
        False, True, True, True, True, False, 0, 0, False,
    )


def cut_corner_holes(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.selectors import select_face_by_z, select_feature_top_face
    from solidworks_api.units import mm_to_m

    base = state.get("base", {})
    thickness = float(base.get("thickness", 0))
    base_top_z_m = float(base.get("top_z_m", mm_to_m(thickness)))
    diameter = float(params["diameter"])
    if "edge_margin" in params:
        base = state.get("base", {})
        try:
            length = float(base["length"])
            width = float(base["width"])
        except KeyError as exc:
            raise RuntimeError("cut_corner_holes edge_margin requires base length and width in executor state") from exc
        margin = float(params["edge_margin"])
        offset_x = length / 2 - margin
        offset_y = width / 2 - margin
        if offset_x <= 0 or offset_y <= 0:
            raise RuntimeError("cut_corner_holes edge_margin is too large for the current base size")
    else:
        offset_x = float(params["offset_x"])
        offset_y = float(params["offset_y"])
    base_feature = base.get("feature")
    if base_feature is not None:
        try:
            select_feature_top_face(sw_model, base_feature, base_top_z_m)
        except Exception:
            select_face_by_z(sw_model, base_top_z_m)
    else:
        select_face_by_z(sw_model, base_top_z_m)
    sw_model.SketchManager.InsertSketch(True)
    _add_circle(sw_model, -offset_x, -offset_y, diameter)
    _add_circle(sw_model, offset_x, -offset_y, diameter)
    _add_circle(sw_model, -offset_x, offset_y, diameter)
    _add_circle(sw_model, offset_x, offset_y, diameter)
    sw_model.SketchManager.InsertSketch(True)
    _require_feature_result(_through_all_cut(sw_model), "cut_corner_holes")


def cut_center_hole(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.selectors import select_face_by_z, select_feature_top_face
    from solidworks_api.units import mm_to_m

    base = state.get("base", {})
    base_thickness = float(base.get("thickness", 0))
    base_top_z_m = float(base.get("top_z_m", mm_to_m(base_thickness)))
    boss = state.get("boss", {})
    boss_height = float(boss.get("height", 0))
    target = str(params.get("target", "boss" if boss_height > 0 else "base"))
    if target == "boss" and boss_height <= 0:
        raise RuntimeError("cut_center_hole target=boss requires a preceding create_center_boss operation")
    diameter = float(params["diameter"])
    target_z_m = float(boss.get("top_z_m", base_top_z_m + mm_to_m(boss_height))) if target == "boss" else base_top_z_m
    if target == "boss":
        boss_feature = boss.get("feature")
        selection_errors: list[str] = []
        try:
            # Prefer coordinate-based selection first. For SOLIDWORKS 2019 this is
            # more stable than re-reading the previous boss COM feature object.
            select_face_by_z(sw_model, target_z_m)
        except Exception as exc:
            selection_errors.append(f"select_face_by_z: {exc}")
            if boss_feature is not None:
                try:
                    select_feature_top_face(sw_model, boss_feature, target_z_m)
                except Exception as feature_exc:
                    selection_errors.append(f"select_feature_top_face: {feature_exc}")
                    raise RuntimeError(" ; ".join(selection_errors)) from feature_exc
            else:
                raise RuntimeError(" ; ".join(selection_errors)) from exc
    else:
        select_face_by_z(sw_model, target_z_m)
    sw_model.SketchManager.InsertSketch(True)
    _add_circle(sw_model, 0, 0, diameter)
    sw_model.SketchManager.InsertSketch(True)
    has_depth = "depth" in params
    through_all = bool(params.get("through_all", not has_depth))
    if through_all:
        _require_feature_result(_through_all_cut(sw_model), "cut_center_hole")
    else:
        _require_feature_result(_blind_cut(sw_model, float(params["depth"])), "cut_center_hole")


def create_through_hole(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.sketch_builder import _select_sketch_plane

    center = params["center"]
    diameter = float(params["diameter"])
    plane = str(params.get("plane", "top_face"))
    host = str(params.get("host", "base"))
    _select_sketch_plane(sw_model, plane, state, host=host)
    sw_model.SketchManager.InsertSketch(True)
    _add_circle(sw_model, float(center[0]), float(center[1]), diameter)
    sw_model.SketchManager.InsertSketch(True)
    feature = _require_feature_result(_through_all_cut(sw_model), "create_through_hole")
    _record_seed_hole(state, feature, params, through_all=True)


def _record_seed_hole(state: dict, feature: object, params: dict, through_all: bool) -> None:
    features = state.setdefault("feature_params", {})
    holes = state.setdefault("hole_features", [])
    aliases: list[str] = []

    operation_id = str(state.get("current_operation_id", "")).strip()
    if operation_id:
        aliases.append(operation_id)
    feature_name = str(getattr(feature, "Name", "") or "").strip()
    if feature_name:
        aliases.append(feature_name)
    aliases.append(f"Hole{len(holes) + 1}")

    hole_data = {
        "type": "through_hole",
        "plane": params.get("plane", "top_face"),
        "host": params.get("host", "base"),
        "center": [float(params.get("center", [0, 0])[0]), float(params.get("center", [0, 0])[1])],
        "diameter": float(params["diameter"]),
        "through_all": bool(params.get("through_all", through_all)),
    }
    holes.append(hole_data)
    state["last_hole"] = hole_data
    for alias in dict.fromkeys(aliases):
        features[alias] = hole_data


def create_blind_hole(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.sketch_builder import _select_sketch_plane

    center = params["center"]
    diameter = float(params["diameter"])
    depth = float(params["depth"])
    plane = str(params.get("plane", "top_face"))
    host = str(params.get("host", "base"))
    _select_sketch_plane(sw_model, plane, state, host=host)
    sw_model.SketchManager.InsertSketch(True)
    _add_circle(sw_model, float(center[0]), float(center[1]), diameter)
    sw_model.SketchManager.InsertSketch(True)
    _require_feature_result(_blind_cut(sw_model, depth), "create_blind_hole")


def create_counterbore_hole(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.sketch_builder import _select_sketch_plane

    center = params["center"]
    diameter = float(params["hole_diameter"])
    counterbore_diameter = float(params["counterbore_diameter"])
    counterbore_depth = float(params["counterbore_depth"])
    plane = str(params.get("plane", "top_face"))
    host = str(params.get("host", "base"))
    through_all = bool(params.get("through_all", True))
    depth = float(params.get("depth", state.get("base", {}).get("thickness", 1)))

    _select_sketch_plane(sw_model, plane, state, host=host)
    sw_model.SketchManager.InsertSketch(True)
    _add_circle(sw_model, float(center[0]), float(center[1]), diameter)
    sw_model.SketchManager.InsertSketch(True)
    if through_all:
        _require_feature_result(_through_all_cut(sw_model), "create_counterbore_hole")
    else:
        _require_feature_result(_blind_cut(sw_model, depth), "create_counterbore_hole")

    _select_sketch_plane(sw_model, plane, state, host=host)
    sw_model.SketchManager.InsertSketch(True)
    _add_circle(sw_model, float(center[0]), float(center[1]), counterbore_diameter)
    sw_model.SketchManager.InsertSketch(True)
    _require_feature_result(_blind_cut(sw_model, counterbore_depth), "create_counterbore_hole")


def create_countersink_hole(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.sketch_builder import _select_sketch_plane

    center = params["center"]
    diameter = float(params["hole_diameter"])
    countersink_diameter = float(params["countersink_diameter"])
    plane = str(params.get("plane", "top_face"))
    host = str(params.get("host", "base"))

    _select_sketch_plane(sw_model, plane, state, host=host)
    sw_model.SketchManager.InsertSketch(True)
    _add_circle(sw_model, float(center[0]), float(center[1]), diameter)
    sw_model.SketchManager.InsertSketch(True)
    _require_feature_result(_through_all_cut(sw_model), "create_countersink_hole")

    # The countersink cone is represented by a shallow top circular cut in this fixed executor.
    # TODO: Replace with a validated Hole Wizard countersink call for production geometry.
    _select_sketch_plane(sw_model, plane, state, host=host)
    sw_model.SketchManager.InsertSketch(True)
    _add_circle(sw_model, float(center[0]), float(center[1]), countersink_diameter)
    sw_model.SketchManager.InsertSketch(True)
    _require_feature_result(_blind_cut(sw_model, 0.5), "create_countersink_hole")


def build(*args, **kwargs) -> None:
    cut_center_hole(*args, **kwargs)

