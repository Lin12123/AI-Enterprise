"""Cut feature implementation for fixed API executor."""

import math
import os

OPERATION_TYPE = "extrude_cut"
STATUS = "implemented"


def extrude_cut(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.features.extrude import _close_active_sketch
    from solidworks_api.features.hole import _through_all_cut
    from solidworks_api.units import mm_to_m

    _close_active_sketch(sw_model, state)
    if params.get("through_all", False):
        feature = _through_all_cut(sw_model)
        if feature is None:
            raise RuntimeError("extrude_cut through_all failed: FeatureCut3 returned None")
        return

    depth = float(params["depth"])
    reverse = params.get("direction", "normal") == "reverse"
    sw_model.FeatureManager.FeatureCut3(
        True, False, reverse, 0, 0, mm_to_m(depth), 0,
        False, False, False, False, 0, 0, False, False, False, False,
        False, True, True, True, True, False, 0, 0, False,
    )


def cut_rectangle_pocket(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.features.extrude import _close_active_sketch
    from solidworks_api.features.hole import _blind_cut
    from solidworks_api.sketch_builder import _select_sketch_plane
    from solidworks_api.units import mm_to_m

    center = params.get("center", [0, 0])
    length = float(params["length"])
    width = float(params["width"])
    depth = float(params["depth"])
    plane = str(params.get("plane", "top_face"))
    host = str(params.get("host", "base"))
    _close_active_sketch(sw_model, state)
    _select_sketch_plane(sw_model, plane, state, host=host)
    sw_model.SketchManager.InsertSketch(True)
    sw_model.SketchManager.CreateCenterRectangle(
        mm_to_m(float(center[0])),
        mm_to_m(float(center[1])),
        0,
        mm_to_m(float(center[0]) + length / 2),
        mm_to_m(float(center[1]) + width / 2),
        0,
    )
    sw_model.SketchManager.InsertSketch(True)
    feature = _blind_cut(sw_model, depth)
    if feature is None:
        raise RuntimeError("cut_rectangle_pocket failed: FeatureCut3 returned None")
    _record_pattern_seed_feature(
        state,
        feature,
        feature_type="rectangle_pocket",
        params={"plane": plane, "host": host, "center": [float(center[0]), float(center[1])], "length": length, "width": width, "depth": depth},
    )


def _slot_error_context(plane, host, x, y, sketch_length, sketch_width, depth, direction) -> str:
    """拼接 slot 切除失败时的排查上下文，便于从技术日志定位参数问题。"""
    return (
        f" [plane={plane}, host={host}, center=({x:.3f},{y:.3f}), "
        f"sketch_length={sketch_length:.3f}, sketch_width={sketch_width:.3f}, "
        f"depth={depth:.3f}, direction={direction}]"
    )


def _slot_top_z_m(state: dict):
    """推断 slot 所在顶面的 z 坐标(米)。优先用 base.top_z_m，其次用厚度换算。"""
    from solidworks_api.units import mm_to_m

    base = state.get("base", {})
    top_z_m = base.get("top_z_m")
    if top_z_m is not None:
        try:
            return float(top_z_m)
        except (TypeError, ValueError):
            pass
    thickness = float(base.get("thickness", 0) or 0)
    if thickness > 0:
        return mm_to_m(thickness)
    return None


def _try_select_slot_face_by_center(
    sw_model: object, plane: str, host: str, state: dict, x_mm: float, y_mm: float
) -> bool:
    """优先用 slot 的 center 坐标命中所在顶面，避免选到被前序孔洞切碎的其它面片。

    仅对 host=base 的 top_face 生效；命中返回 True，未命中返回 False 让调用方回退
    到通用 top_face 选面策略。任何异常都视为未命中(返回 False)，绝不因选面兜底
    而中断主流程。
    """
    if plane != "top_face" or str(host or "base").strip().lower() != "base":
        return False
    top_z_m = _slot_top_z_m(state)
    if top_z_m is None:
        return False
    try:
        from solidworks_api.selectors import select_face_by_point_candidates
        from solidworks_api.units import mm_to_m

        # 以 slot 中心为核心构造候选点：中心优先，再沿槽附近做小偏移兜底，
        # 确保命中的是 slot 轮廓真正覆盖的那块面片。
        offsets_mm = [(0.0, 0.0), (2.0, 0.0), (-2.0, 0.0), (0.0, 2.0), (0.0, -2.0)]
        candidates = [
            (mm_to_m(x_mm + dx), mm_to_m(y_mm + dy), top_z_m) for dx, dy in offsets_mm
        ]
        select_face_by_point_candidates(sw_model, candidates)
        return True
    except Exception:
        return False


def _describe_active_sketch(sw_model: object) -> str:
    """采集当前草图诊断信息(轮廓段数/线弧数)，拼入失败日志方便下次定位。

    该函数仅用于切除失败后的排查，任何异常都吞掉并返回可读的降级说明，
    绝不因诊断采集本身失败而掩盖原始的 FeatureCut3 错误。
    """
    parts: list[str] = []
    try:
        sketch = None
        try:
            candidate = getattr(sw_model.SketchManager, "ActiveSketch", None)
            sketch = candidate() if callable(candidate) else candidate
        except Exception:
            sketch = None
        if sketch is None:
            return " [sketch_diag: 无法获取活动草图对象(可能已退出草图)]"
        try:
            segs = sketch.GetSketchSegments()
            seg_count = len(segs) if segs is not None else 0
            parts.append(f"segments={seg_count}")
        except Exception as exc:
            parts.append(f"segments=?({exc})")
        for attr in ("GetLineCount2", "GetArcCount2"):
            try:
                method = getattr(sketch, attr, None)
                if callable(method):
                    parts.append(f"{attr}={method(0)}")
            except Exception:
                continue
    except Exception as exc:
        return f" [sketch_diag: 采集失败 {exc}]"
    if not parts:
        return " [sketch_diag: 无可用草图诊断信息]"
    return " [sketch_diag: " + ", ".join(parts) + "]"


def cut_slot(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.features.extrude import _close_active_sketch
    from solidworks_api.features.hole import _blind_cut
    from solidworks_api.sketch_builder import _select_sketch_plane
    from solidworks_api.units import mm_to_m

    center = params.get("center", [0, 0])
    length = float(params["length"])
    width = float(params["width"])
    plane = str(params.get("plane", "top_face"))
    host = str(params.get("host", "base"))
    through_all = bool(params.get("through_all", False))
    depth = float(params.get("depth", state.get("base", {}).get("thickness", 1)))
    direction = str(params.get("direction", "x")).strip().lower()
    angle_deg = float(params.get("angle", 90 if direction == "y" else 0))
    x = float(center[0])
    y = float(center[1])
    sketch_length = length
    sketch_width = width
    base = state.get("base", {})
    base_length = float(base.get("length", 0) or 0)
    base_width = float(base.get("width", 0) or 0)
    overshoot_mm = 0.2
    is_open_edge = False
    if direction == "y" and base_width > 0 and abs(length - base_width) <= 1e-6:
        # Open-edge width-direction slots need a slight overshoot past the side edges;
        # otherwise SOLIDWORKS can treat the contour as an invalid closed cut and
        # FeatureCut3 returns None on SW2019.
        sketch_length = length + overshoot_mm
        is_open_edge = True
    elif direction == "x" and base_length > 0 and abs(length - base_length) <= 1e-6:
        sketch_length = length + overshoot_mm
        is_open_edge = True

    _close_active_sketch(sw_model, state)
    # 关键：slot 的草图基准面必须是 slot 轮廓覆盖区域的那块顶面。
    # 前序的孔/口袋操作会把原始整块顶面切割成多个面片，若沿用通用
    # top_face 选面（取最高 z 碎片面 / 选 (0,0,z) 那片面），当 slot 中心
    # 偏离原点(如 center=(-36,0))时可能落在其它面片上，导致草图画在错误
    # 的面上、FeatureCut3 找不到可切实体而返回 None。这里优先用 slot 自己
    # 的 center 坐标去命中面，命中失败再回退通用 top_face 选面。
    if not _try_select_slot_face_by_center(sw_model, plane, host, state, x, y):
        _select_sketch_plane(sw_model, plane, state, host=host)
    sw_model.SketchManager.InsertSketch(True)
    # 开边贯通槽（轮廓要跨出板边）必须用矩形轮廓：native slot 的圆弧端头一旦
    # 延伸超出板边缘，端头圆弧落在实体之外，SW2019 会认为这不是有效的贯穿切除
    # 轮廓，FeatureCut3 返回 None。只有非开边的"内部盲槽"才允许用 native slot。
    use_native = (
        _native_slot_api_enabled()
        and not is_open_edge
        and hasattr(sw_model.SketchManager, "CreateSketchSlot")
    )
    if use_native:
        try:
            _create_native_slot(sw_model, x, y, sketch_length, sketch_width, angle_deg)
        except Exception:
            _create_rectangular_slot_fallback(sw_model, x, y, sketch_length, sketch_width, angle_deg)
    else:
        _create_rectangular_slot_fallback(sw_model, x, y, sketch_length, sketch_width, angle_deg)
    # 在退出草图前采集诊断(段数/线弧数)；退出后 ActiveSketch 可能为 None 无法读取。
    sketch_diag = _describe_active_sketch(sw_model)
    sw_model.SketchManager.InsertSketch(True)
    if through_all:
        from solidworks_api.features.hole import _through_all_cut_any

        feature = _through_all_cut_any(sw_model)
        if feature is None:
            raise RuntimeError(
                "cut_slot through_all failed: FeatureCut3 returned None"
                + _slot_error_context(plane, host, x, y, sketch_length, sketch_width, depth, direction)
                + sketch_diag
            )
    else:
        feature = _blind_cut(sw_model, depth)
        if feature is None:
            # blind 两个方向都失败：开边槽/贯通槽本应通切，自动回退 through_all 再试。
            # 开边槽轮廓的切除侧向不确定，_through_all_cut_any 会尝试正向/反向/双向贯通,
            # 直到 SW2019 找到有实体可切的方向为止。
            from solidworks_api.features.hole import _through_all_cut_any

            feature = _through_all_cut_any(sw_model)
        if feature is None:
            raise RuntimeError(
                "cut_slot failed: FeatureCut3 returned None (blind 与 through_all 均失败)"
                + _slot_error_context(plane, host, x, y, sketch_length, sketch_width, depth, direction)
                + sketch_diag
            )
    _record_pattern_seed_feature(
        state,
        feature,
        feature_type="slot",
        params={
            "plane": plane,
            "host": host,
            "center": [x, y],
            "length": length,
            "width": width,
            "depth": depth,
            "through_all": through_all,
            "direction": direction,
        },
    )


def _record_pattern_seed_feature(state: dict, feature: object, feature_type: str, params: dict) -> None:
    features = state.setdefault("feature_params", {})
    aliases: list[str] = []

    operation_id = str(state.get("current_operation_id", "")).strip()
    if operation_id:
        aliases.append(operation_id)
    feature_name = str(getattr(feature, "Name", "") or "").strip()
    if feature_name:
        aliases.append(feature_name)

    feature_data = {"type": feature_type, **dict(params)}
    for alias in dict.fromkeys(alias for alias in aliases if alias):
        features[alias] = feature_data
    state["last_pattern_seed_feature"] = feature_data


def _native_slot_api_enabled() -> bool:
    return os.environ.get("AI_SW_ENABLE_EXPERIMENTAL_SLOT_API", "0").strip() == "1"


def _create_native_slot(
    sw_model: object,
    x_mm: float,
    y_mm: float,
    length_mm: float,
    width_mm: float,
    angle_deg: float = 0,
) -> None:
    from solidworks_api.units import mm_to_m

    half_straight = (length_mm - width_mm) / 2
    angle_rad = math.radians(angle_deg)
    axis_dx = math.cos(angle_rad)
    axis_dy = math.sin(angle_rad)
    normal_dx = -math.sin(angle_rad)
    normal_dy = math.cos(angle_rad)

    # SOLIDWORKS native slot COM path is intentionally opt-in because SW2019 can
    # reject the signature with opaque COM errors such as "unable to read only-write property".
    sw_model.SketchManager.CreateSketchSlot(
        0,
        0,
        mm_to_m(width_mm),
        mm_to_m(x_mm - axis_dx * half_straight),
        mm_to_m(y_mm - axis_dy * half_straight),
        0,
        mm_to_m(x_mm + axis_dx * half_straight),
        mm_to_m(y_mm + axis_dy * half_straight),
        0,
        mm_to_m(x_mm + normal_dx * width_mm / 2),
        mm_to_m(y_mm + normal_dy * width_mm / 2),
        0,
    )


def _create_rectangular_slot_fallback(
    sw_model: object,
    x_mm: float,
    y_mm: float,
    length_mm: float,
    width_mm: float,
    angle_deg: float = 0,
) -> None:
    from solidworks_api.units import mm_to_m

    if round(angle_deg) % 180 == 90:
        length_mm, width_mm = width_mm, length_mm
    sw_model.SketchManager.CreateCenterRectangle(
        mm_to_m(x_mm),
        mm_to_m(y_mm),
        0,
        mm_to_m(x_mm + length_mm / 2),
        mm_to_m(y_mm + width_mm / 2),
        0,
    )


def build(*args, **kwargs) -> None:
    extrude_cut(*args, **kwargs)



