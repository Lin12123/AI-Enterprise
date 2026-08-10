"""Named-dimension modification implementation."""

OPERATION_TYPE = "modify_named_dimension"
STATUS = "implemented"


def modify_named_dimension(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.units import mm_to_m

    name = str(params["dimension_name"])
    value_m = mm_to_m(float(params["value"]))
    dimension = None
    if hasattr(sw_model, "Parameter"):
        dimension = sw_model.Parameter(name)
    if dimension is None:
        raise RuntimeError(f"无法找到命名尺寸: {name}")
    if hasattr(dimension, "SystemValue"):
        dimension.SystemValue = value_m
    elif hasattr(dimension, "SetSystemValue3"):
        dimension.SetSystemValue3(value_m, 0, None)
    else:
        raise RuntimeError("命名尺寸对象不支持 SystemValue/SetSystemValue3")
    state.setdefault("modified_dimensions", {})[name] = value_m
