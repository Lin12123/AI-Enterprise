"""Reference geometry feature implementations."""

OPERATION_TYPE = "reference_geometry"
STATUS = "implemented"


def create_offset_plane(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.units import mm_to_m

    name = str(params["name"])
    base_plane = str(params["base_plane"])
    offset = mm_to_m(float(params["offset"]))
    sw_model.ClearSelection2(True)
    if not sw_model.Extension.SelectByID2(base_plane, "PLANE", 0, 0, 0, False, 0, None, 0):
        raise RuntimeError(f"无法选择 base_plane: {base_plane}")
    if not hasattr(sw_model.FeatureManager, "InsertRefPlane"):
        raise RuntimeError("InsertRefPlane API is unavailable")
    feature = sw_model.FeatureManager.InsertRefPlane(8, offset, 0, 0, 0, 0)
    if feature is None:
        raise RuntimeError("InsertRefPlane returned None")
    try:
        feature.Name = name
    except Exception:
        pass
    state.setdefault("reference_geometry", {})[name] = feature


def create_axis(sw_model: object, params: dict, state: dict) -> None:
    name = str(params["name"])
    reference_type = str(params["reference_type"])
    references = list(params["references"])
    if reference_type != "two_planes":
        raise RuntimeError("create_axis 当前仅支持 reference_type=two_planes")
    if len(references) != 2:
        raise RuntimeError("create_axis two_planes 需要两个平面引用")
    sw_model.ClearSelection2(True)
    for index, plane in enumerate(references):
        if not sw_model.Extension.SelectByID2(str(plane), "PLANE", 0, 0, 0, index > 0, 0, None, 0):
            raise RuntimeError(f"无法选择 axis plane: {plane}")
    if not hasattr(sw_model.FeatureManager, "InsertRefAxis"):
        raise RuntimeError("InsertRefAxis API is unavailable")
    feature = sw_model.FeatureManager.InsertRefAxis(0)
    if feature is None:
        raise RuntimeError("InsertRefAxis returned None")
    try:
        feature.Name = name
    except Exception:
        pass
    state.setdefault("reference_geometry", {})[name] = feature


def build(*_args, **_kwargs) -> None:
    raise NotImplementedError("reference_geometry API build is planned.")
