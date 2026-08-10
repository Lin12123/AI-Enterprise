"""Chamfer feature implementation for fixed API executor."""

OPERATION_TYPE = "add_chamfer"
STATUS = "implemented"


def add_chamfer(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.features.fillet import _select_outer_edges
    from solidworks_api.units import mm_to_m

    target = params.get("target", "outer_edges")
    distance = float(params["distance"])
    angle = float(params.get("angle", 45))
    sw_model.ClearSelection2(True)

    if target == "outer_edges":
        base = state.get("base", {})
        selected = _select_outer_edges(
            sw_model,
            float(base.get("length", 0)),
            float(base.get("width", 0)),
            float(base.get("thickness", 0)),
        )
        if selected < 4:
            raise RuntimeError(f"选择 outer_edges 失败，已选择 {selected} 条边")
    elif target == "selected_edges":
        selection_manager = getattr(sw_model, "SelectionManager", None)
        selected = 0
        if selection_manager is not None and hasattr(selection_manager, "GetSelectedObjectCount2"):
            selected = int(selection_manager.GetSelectedObjectCount2(-1))
        if selected <= 0:
            raise RuntimeError("selected_edges 目标没有可用的受控选择集")
    else:
        raise RuntimeError("add_chamfer target 只能是 outer_edges 或 selected_edges")

    feature = sw_model.FeatureManager.InsertFeatureChamfer(4, 1, mm_to_m(distance), angle, 0, 0, 0, 0)
    if feature is None:
        raise RuntimeError("InsertFeatureChamfer returned None")


def build(*_args, **_kwargs) -> None:
    add_chamfer(*_args, **_kwargs)
