"""Pattern feature implementation for fixed API executor."""

OPERATION_TYPE = "pattern"
STATUS = "implemented"


def _select_feature_by_name(sw_model: object, feature_name: str) -> None:
    from solidworks_api.com_compat import safe_select_by_id

    sw_model.ClearSelection2(True)
    feature = None
    try:
        feature = sw_model.FeatureByName(feature_name)
    except Exception:
        feature = None
    if feature is not None and hasattr(feature, "Select2") and feature.Select2(False, 0):
        return
    for object_type in ("BODYFEATURE", "REFERENCECURVES", "SKETCH", "EXTSKETCHSEGMENT"):
        if safe_select_by_id(sw_model, feature_name, object_type):
            return
    raise RuntimeError(f"Unable to select seed_feature: {feature_name}")


def create_linear_pattern(sw_model: object, params: dict, state: dict) -> None:
    params = _normalized_pattern_params(params)

    # Prefer deterministic executor geometry for registered replayable seeds.
    # This avoids unstable SW2019 pattern COM signatures while keeping the
    # operation declarative and allowlisted.
    if _replayable_seed(params, state):
        _fallback_linear_pattern_replay(sw_model, params, state)
        return

    selection_error = None
    try:
        _select_feature_by_name(sw_model, str(params["seed_feature"]))
        _create_native_linear_pattern(sw_model, params)
        return
    except Exception as exc:
        selection_error = exc

    if _fallback_linear_pattern_replay(sw_model, params, state):
        return
    raise RuntimeError(f"FeatureLinearPattern failed and no safe fallback seed was available: {selection_error}") from selection_error


def _create_native_linear_pattern(sw_model: object, params: dict) -> object:
    from solidworks_api.com_compat import ComAttempt, call_first_available
    from solidworks_api.units import mm_to_m

    count = int(params["count"])
    spacing = mm_to_m(float(params["spacing"]))
    direction = str(params.get("direction", "x")).lower()
    use_x_direction = direction == "x"

    def attempts(method_name: str) -> list[ComAttempt]:
        if method_name == "FeatureLinearPattern5":
            return [
                ComAttempt("sw2019_primary", (count, spacing, 1, 0, use_x_direction, False, "", "", False, False, False, False, False, False, False)),
                ComAttempt("sw2019_no_empty_refs", (count, spacing, 1, 0, use_x_direction, False, None, None, False, False, False, False, False, False, False)),
            ]
        if method_name == "FeatureLinearPattern4":
            return [
                ComAttempt("legacy_primary", (count, spacing, 1, 0, use_x_direction, False, "", "", False, False, False)),
                ComAttempt("legacy_no_empty_refs", (count, spacing, 1, 0, use_x_direction, False, None, None, False, False, False)),
            ]
        return []

    return call_first_available(sw_model.FeatureManager, ("FeatureLinearPattern5", "FeatureLinearPattern4"), attempts)


def _fallback_linear_pattern_replay(sw_model: object, params: dict, state: dict) -> bool:
    from solidworks_api.features.cut import cut_rectangle_pocket, cut_slot
    from solidworks_api.features.hole import create_through_hole

    seed = _replayable_seed(params, state)
    if not seed:
        return False

    count = int(params["count"])
    spacing = float(params["spacing"])
    direction = str(params.get("direction", "x")).lower()
    dx, dy = _direction_step(direction, spacing)
    seed_center = seed["center"]
    feature_type = str(seed.get("type", ""))

    for index in range(1, count):
        center = [float(seed_center[0]) + dx * index, float(seed_center[1]) + dy * index]
        if feature_type == "through_hole":
            create_through_hole(
                sw_model,
                {
                    "plane": seed.get("plane", "top_face"),
                    "center": center,
                    "diameter": seed["diameter"],
                    "through_all": seed.get("through_all", True),
                },
                state,
            )
            continue
        if feature_type == "slot":
            cut_slot(
                sw_model,
                {
                    "plane": seed.get("plane", "top_face"),
                    "center": center,
                    "length": seed["length"],
                    "width": seed["width"],
                    "direction": seed.get("direction", direction),
                    "through_all": seed.get("through_all", False),
                    "depth": seed.get("depth"),
                },
                state,
            )
            continue
        if feature_type == "rectangle_pocket":
            cut_rectangle_pocket(
                sw_model,
                {
                    "plane": seed.get("plane", "top_face"),
                    "center": center,
                    "length": seed["length"],
                    "width": seed["width"],
                    "depth": seed["depth"],
                },
                state,
            )
            continue
        return False
    return True


def _normalized_pattern_params(params: dict) -> dict:
    from cad_dsl.feature_references import normalize_feature_reference

    normalized = dict(params or {})
    if "seed_feature" in normalized:
        normalized["seed_feature"] = normalize_feature_reference(normalized.get("seed_feature"))
    return normalized


def _replayable_seed(params: dict, state: dict) -> dict | None:
    seed_feature = str(params.get("seed_feature", ""))
    features = state.get("feature_params", {})
    seed = features.get(seed_feature)
    if isinstance(seed, dict) and seed.get("type") in {"through_hole", "slot", "rectangle_pocket"}:
        return seed
    last_pattern_seed_feature = state.get("last_pattern_seed_feature")
    if isinstance(last_pattern_seed_feature, dict) and last_pattern_seed_feature.get("type") in {"through_hole", "slot", "rectangle_pocket"}:
        return last_pattern_seed_feature
    last_hole = state.get("last_hole")
    if isinstance(last_hole, dict) and last_hole.get("type") == "through_hole":
        return last_hole
    return None


def _direction_step(direction: str, spacing: float) -> tuple[float, float]:
    if direction == "x":
        return spacing, 0.0
    if direction == "y":
        return 0.0, spacing
    raise RuntimeError("Fallback linear hole pattern only supports X/Y directions")


def create_circular_pattern(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.com_compat import ComAttempt, call_first_available, safe_select_by_id

    params = _normalized_pattern_params(params)
    _select_feature_by_name(sw_model, str(params["seed_feature"]))
    axis = str(params["axis"])
    if not safe_select_by_id(sw_model, axis, "AXIS", append=True, mark=1):
        raise RuntimeError(f"Unable to select axis: {axis}")
    count = int(params["count"])
    angle = float(params.get("angle", 360))

    def attempts(method_name: str) -> list[ComAttempt]:
        if method_name == "FeatureCircularPattern5":
            return [ComAttempt("primary", (count, angle, False, "", False, True, False))]
        if method_name == "FeatureCircularPattern4":
            return [ComAttempt("legacy", (count, angle, False, "", False, True))]
        return []

    call_first_available(sw_model.FeatureManager, ("FeatureCircularPattern5", "FeatureCircularPattern4"), attempts)


def build(*_args, **_kwargs) -> None:
    raise NotImplementedError("pattern API build is planned.")
