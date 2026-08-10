"""Boss feature scaffold."""

OPERATION_TYPE = "create_center_boss"
STATUS = "implemented"


def create_center_boss(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.features.hole import _add_circle
    from solidworks_api.selectors import feature_z_range, select_face_by_z, select_feature_top_face
    from solidworks_api.units import mm_to_m

    base = state.get("base", {})
    base_thickness = float(base.get("thickness", 0))
    base_top_z_m = float(base.get("top_z_m", mm_to_m(base_thickness)))
    diameter = float(params["diameter"])
    height = float(params["height"])
    base_feature = base.get("feature")
    if base_feature is not None:
        try:
            select_feature_top_face(sw_model, base_feature, base_top_z_m)
        except Exception:
            select_face_by_z(sw_model, base_top_z_m)
    else:
        select_face_by_z(sw_model, base_top_z_m)
    sw_model.SketchManager.InsertSketch(True)
    _add_circle(sw_model, 0, 0, diameter)
    sw_model.SketchManager.InsertSketch(True)
    feature = sw_model.FeatureManager.FeatureExtrusion2(
        True, False, False, 0, 0, mm_to_m(height), 0,
        False, False, False, False, 0, 0, False, False, False, False,
        True, True, True, 0, 0, False,
    )
    if feature is None:
        raise RuntimeError("create_center_boss failed: FeatureExtrusion2 returned None")
    try:
        z_range = feature_z_range(feature)
    except Exception:
        z_range = None
    boss_top_z_m = z_range[1] if z_range is not None else base_top_z_m + mm_to_m(height)
    boss_bottom_z_m = z_range[0] if z_range is not None else base_top_z_m
    state["boss"] = {
        "diameter": diameter,
        "height": height,
        "feature": feature,
        "feature_name": str(getattr(feature, "Name", "") or "").strip(),
        "top_z_m": boss_top_z_m,
        "bottom_z_m": boss_bottom_z_m,
    }


def build(*args, **kwargs) -> None:
    create_center_boss(*args, **kwargs)

