"""Base plate feature scaffold."""

OPERATION_TYPE = "create_base_plate"
STATUS = "implemented"


def create_base_plate(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.selectors import feature_z_range, select_top_plane
    from solidworks_api.units import mm_to_m

    length = float(params["length"])
    width = float(params["width"])
    thickness = float(params["thickness"])
    try:
        select_top_plane(sw_model)
    except Exception as exc:
        raise RuntimeError(f"閫夋嫨 Top Plane 澶辫触: {exc}") from exc
    try:
        sw_model.SketchManager.InsertSketch(True)
    except Exception as exc:
        raise RuntimeError(f"杩涘叆鑽夊浘澶辫触: {exc}") from exc
    try:
        sw_model.SketchManager.CreateCenterRectangle(0.0, 0.0, 0.0, mm_to_m(length) / 2, mm_to_m(width) / 2, 0.0)
    except Exception as exc:
        raise RuntimeError(f"鍒涘缓鐭╁舰鑽夊浘澶辫触: {exc}") from exc
    try:
        sw_model.SketchManager.InsertSketch(True)
    except Exception as exc:
        raise RuntimeError(f"閫€鍑鸿崏鍥惧け璐? {exc}") from exc
    try:
        feature = sw_model.FeatureManager.FeatureExtrusion2(
            True, False, False, 0, 0, mm_to_m(thickness), 0.0,
            False, False, False, False, 0.0, 0.0, False, False, False, False,
            True, True, True, 0, 0, False,
        )
    except Exception as exc:
        raise RuntimeError(f"鎷変几搴曟澘澶辫触: {exc}") from exc
    if feature is None:
        raise RuntimeError("鎷変几搴曟澘澶辫触: FeatureExtrusion2 returned None")
    try:
        z_range = feature_z_range(feature)
    except Exception:
        z_range = None
    top_z_m = z_range[1] if z_range is not None else mm_to_m(thickness)
    bottom_z_m = z_range[0] if z_range is not None else 0.0
    state["base"] = {
        "length": length,
        "width": width,
        "thickness": thickness,
        "feature": feature,
        "top_z_m": top_z_m,
        "bottom_z_m": bottom_z_m,
    }


def build(*args, **kwargs) -> None:
    create_base_plate(*args, **kwargs)

