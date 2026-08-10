"""Extrude feature implementation for fixed API executor."""

OPERATION_TYPE = "extrude_boss"
STATUS = "implemented"


def _close_active_sketch(sw_model: object, state: dict) -> None:
    if state.get("active_sketch"):
        sw_model.SketchManager.InsertSketch(True)
        state["last_closed_sketch"] = state.pop("active_sketch")


def extrude_boss(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.units import mm_to_m

    sketch_name = str(params["sketch"])
    depth = float(params["depth"])
    direction = params.get("direction", "one_side")
    if direction not in {"one_side", "midplane"}:
        raise RuntimeError(f"Unsupported extrude_boss direction: {direction}")

    _close_active_sketch(sw_model, state)
    end_condition = 0
    reverse = False
    both_directions = direction == "midplane"
    feature = sw_model.FeatureManager.FeatureExtrusion2(
        True, False, reverse, end_condition, end_condition if both_directions else 0,
        mm_to_m(depth), mm_to_m(depth) if both_directions else 0.0,
        False, False, False, False, 0.0, 0.0, False, False, False, False,
        True, True, True, 0, 0, False,
    )
    if feature is None:
        raise RuntimeError("extrude_boss failed: FeatureExtrusion2 returned None")

    sketch = state.get("sketches", {}).get(sketch_name, {})
    entities = sketch.get("entities", [])
    if entities and entities[-1].get("type") == "center_rectangle":
        rect = entities[-1]
        state["base"] = {"length": rect["length"], "width": rect["width"], "thickness": depth}
    elif entities and entities[-1].get("type") == "circle":
        circle = entities[-1]
        state["boss"] = {"diameter": circle["diameter"], "height": depth}


def build(*args, **kwargs) -> None:
    extrude_boss(*args, **kwargs)

