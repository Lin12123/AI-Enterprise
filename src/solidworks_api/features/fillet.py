"""Fillet feature implementation for the fixed API executor."""

from __future__ import annotations

OPERATION_TYPE = "add_fillet"
STATUS = "implemented"


def add_fillet(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.com_types import variant_empty_array
    from solidworks_api.units import mm_to_m

    radius = float(params["radius"])
    target = params.get("target", "outer_edges")
    if target != "outer_edges":
        raise RuntimeError("add_fillet currently supports only target=outer_edges")

    try:
        sw_model.ClearSelection2(True)
    except Exception as exc:
        raise RuntimeError(f"Failed to clear SolidWorks selection before fillet: {exc}") from exc

    base = state.get("base", {})
    length = float(base.get("length", 0))
    width = float(base.get("width", 0))
    thickness = float(base.get("thickness", 0))
    try:
        selected = _select_outer_edges(sw_model, length, width, thickness)
    except Exception as exc:
        raise RuntimeError(f"Failed to select outer_edges for fillet: {exc}") from exc
    if selected < 4:
        raise RuntimeError(f"Unable to stably select base outer_edges; selected {selected} edges, fillet was not executed")

    empty = variant_empty_array()
    try:
        feature = sw_model.FeatureManager.FeatureFillet3(
            195,
            mm_to_m(radius),
            mm_to_m(radius * 2),
            0,
            0,
            0,
            0,
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
        )
    except Exception as exc:
        raise RuntimeError(f"FeatureFillet3 call failed: {exc}") from exc
    if feature is None:
        raise RuntimeError("FeatureFillet3 returned None; fillet feature was not created")


def _select_outer_edges(sw_model: object, length_mm: float, width_mm: float, thickness_mm: float) -> int:
    top_loop_errors: list[str] = []
    try:
        selected = _select_outer_top_perimeter_edges(sw_model, length_mm, width_mm, thickness_mm)
        if selected >= 4:
            return selected
        top_loop_errors.append(f"top perimeter selected {selected} edges")
    except Exception as exc:
        top_loop_errors.append(str(exc))

    try:
        selected = _select_outer_vertical_edges(sw_model, length_mm, width_mm, thickness_mm)
    except Exception as exc:
        detail = " | ".join(top_loop_errors) if top_loop_errors else "no top-loop detail"
        raise RuntimeError(f"top perimeter fallback failed: {detail}; vertical fallback: {exc}") from exc

    if selected < 4 and top_loop_errors:
        return selected
    return selected


def _select_outer_top_perimeter_edges(sw_model: object, length_mm: float, width_mm: float, thickness_mm: float) -> int:
    from solidworks_api.units import mm_to_m

    bodies = _get_bodies(sw_model)
    if not bodies:
        return 0

    half_length = mm_to_m(length_mm) / 2
    half_width = mm_to_m(width_mm) / 2
    top_z = mm_to_m(thickness_mm)
    tol = mm_to_m(0.35)

    best_face = None
    best_score = None
    errors: list[str] = []
    for body_index, body in enumerate(bodies):
        try:
            faces = _body_faces(body)
        except Exception as exc:
            errors.append(f"body[{body_index}].GetFaces: {exc}")
            continue
        for face_index, face in enumerate(faces):
            try:
                box = _face_box(face)
            except Exception as exc:
                errors.append(f"body[{body_index}].face[{face_index}].GetBox: {exc}")
                continue
            if box is None:
                continue
            min_x, min_y, min_z, max_x, max_y, max_z = box
            if abs(min_z - top_z) > tol or abs(max_z - top_z) > tol:
                continue
            span_x = max_x - min_x
            span_y = max_y - min_y
            score = abs(span_x - half_length * 2) + abs(span_y - half_width * 2)
            if best_score is None or score < best_score:
                best_score = score
                best_face = face

    if best_face is None:
        detail = " | ".join(errors) if errors else "no horizontal top face matched base top z"
        raise RuntimeError(f"Could not resolve the top outer loop for base perimeter selection: {detail}")

    outer_loop = _face_outer_loop(best_face)
    if outer_loop is None:
        raise RuntimeError("Top face outer loop is unavailable")
    edges = _loop_edges(outer_loop)
    if not edges:
        raise RuntimeError("Top face outer loop contains no selectable edges")

    select_data = _try_create_select_data(sw_model)
    count = 0
    for edge in edges:
        if _select_edge(edge, count > 0, select_data):
            count += 1
    return count


def _get_bodies(sw_model: object) -> object:
    try:
        bodies = sw_model.GetBodies2(0, True)
    except Exception as exc:
        raise RuntimeError(f"GetBodies2 ????????: {exc}") from exc
    return bodies or []


def _body_faces(body: object) -> list[object]:
    for method_name in ("GetFaces", "IGetFaces2"):
        method = getattr(body, method_name, None)
        if method is None:
            continue
        faces = method() if callable(method) else method
        if faces:
            return list(faces)
    return []


def _face_box(face: object) -> tuple[float, float, float, float, float, float] | None:
    method = getattr(face, "GetBox", None)
    if method is None:
        return None
    box = method() if callable(method) else method
    if not isinstance(box, (list, tuple)) or len(box) < 6:
        return None
    return tuple(float(value) for value in box[:6])


def _face_outer_loop(face: object) -> object | None:
    loop = _call_or_value(face, "GetOuterLoop")
    if loop is not None:
        return loop
    loops = _call_or_value(face, "GetLoops")
    if loops:
        for candidate in loops:
            is_outer = getattr(candidate, "IsOuter", None)
            try:
                outer_flag = is_outer() if callable(is_outer) else is_outer
            except Exception:
                outer_flag = None
            if outer_flag:
                return candidate
        return loops[0]
    return None


def _loop_edges(loop: object) -> list[object]:
    edges = _call_or_value(loop, "GetEdges")
    if not edges:
        return []
    return list(edges)


def _call_or_value(obj: object, member_name: str) -> object:
    member = getattr(obj, member_name, None)
    if member is None:
        return None
    return member() if callable(member) else member


def _select_outer_vertical_edges(sw_model: object, length_mm: float, width_mm: float, thickness_mm: float) -> int:
    from solidworks_api.units import mm_to_m

    bodies = _get_bodies(sw_model)
    if not bodies:
        return 0

    select_data = _try_create_select_data(sw_model)
    count = 0
    geometry_error_count = 0
    half_length = mm_to_m(length_mm) / 2
    half_width = mm_to_m(width_mm) / 2
    thickness = mm_to_m(thickness_mm)
    tol = mm_to_m(0.35)

    for body_index, body in enumerate(bodies):
        try:
            edges = body.GetEdges
            edges = edges() if callable(edges) else edges
        except Exception as exc:
            raise RuntimeError(f"body[{body_index}].GetEdges ????????: {exc}") from exc
        if not edges:
            continue
        for edge_index, edge in enumerate(edges):
            try:
                is_target = _is_outer_vertical_edge(edge, half_length, half_width, thickness, tol)
            except Exception:
                geometry_error_count += 1
                continue
            if not is_target:
                continue
            try:
                if _select_edge(edge, count > 0, select_data):
                    count += 1
            except Exception as exc:
                raise RuntimeError(f"edge[{edge_index}] ????: {exc}") from exc

    if count < 4 and geometry_error_count:
        raise RuntimeError(
            f"???????? outer_edges???? {count} ???"
            f"{geometry_error_count} ??????????"
        )
    return count


def _try_create_select_data(sw_model: object) -> object | None:
    try:
        selection_manager = sw_model.SelectionManager
        create_select_data = selection_manager.CreateSelectData
        return create_select_data() if callable(create_select_data) else create_select_data
    except Exception:
        return None


def _select_edge(edge: object, append: bool, select_data: object | None) -> bool:
    from solidworks_api.com_types import dispatch_none

    errors: list[str] = []
    if select_data is not None:
        try:
            return bool(edge.Select4(append, select_data))
        except Exception as exc:
            errors.append(f"Select4(select_data): {exc}")

    for label, fallback_data in (("Select4(None)", None), ("Select4(Dispatch Nothing)", dispatch_none())):
        try:
            return bool(edge.Select4(append, fallback_data))
        except Exception as exc:
            errors.append(f"{label}: {exc}")

    try:
        return bool(edge.Select2(append, 0))
    except Exception as exc:
        errors.append(f"Select2: {exc}")

    raise RuntimeError("; ".join(errors))


def _is_outer_vertical_edge(edge: object, half_length: float, half_width: float, thickness: float, tol: float) -> bool:
    p1, p2 = _edge_points(edge)
    return _matches_z_extrusion_outer_edge(p1, p2, half_length, half_width, thickness, tol) or _matches_y_extrusion_outer_edge(
        p1,
        p2,
        half_length,
        half_width,
        thickness,
        tol,
    )


def _matches_z_extrusion_outer_edge(
    p1: object,
    p2: object,
    half_length: float,
    half_width: float,
    thickness: float,
    tol: float,
) -> bool:
    if abs(p1[0] - p2[0]) > tol:
        return False
    if abs(p1[1] - p2[1]) > tol:
        return False
    if abs(abs(p1[2] - p2[2]) - thickness) > tol:
        return False

    mid_x = (p1[0] + p2[0]) / 2
    mid_y = (p1[1] + p2[1]) / 2
    min_z = min(p1[2], p2[2])
    max_z = max(p1[2], p2[2])
    return (
        abs(abs(mid_x) - half_length) <= tol
        and abs(abs(mid_y) - half_width) <= tol
        and abs(min_z) <= tol
        and abs(max_z - thickness) <= tol
    )


def _matches_y_extrusion_outer_edge(
    p1: object,
    p2: object,
    half_length: float,
    half_width: float,
    thickness: float,
    tol: float,
) -> bool:
    if abs(p1[0] - p2[0]) > tol:
        return False
    if abs(p1[2] - p2[2]) > tol:
        return False
    if abs(abs(p1[1] - p2[1]) - thickness) > tol:
        return False

    mid_x = (p1[0] + p2[0]) / 2
    mid_z = (p1[2] + p2[2]) / 2
    min_y = min(p1[1], p2[1])
    max_y = max(p1[1], p2[1])
    return (
        abs(abs(mid_x) - half_length) <= tol
        and abs(abs(mid_z) - half_width) <= tol
        and abs(min_y) <= tol
        and abs(max_y - thickness) <= tol
    )


def _edge_points(edge: object) -> tuple[object, object]:
    errors: list[str] = []

    try:
        start = _com_value(edge, "GetStartVertex")
        end = _com_value(edge, "GetEndVertex")
        if start is not None and end is not None:
            return _com_value(start, "GetPoint"), _com_value(end, "GetPoint")
    except Exception as exc:
        errors.append(f"vertex endpoints: {exc}")

    for method_name in ("GetCurveParams3", "GetCurveParams2"):
        try:
            params = _com_value(edge, method_name)
            if params is not None and len(params) >= 6:
                return params[0:3], params[3:6]
        except Exception as exc:
            errors.append(f"{method_name}: {exc}")

    raise RuntimeError("; ".join(errors))


def _com_value(obj: object, member_name: str) -> object:
    member = getattr(obj, member_name)
    return member() if callable(member) else member


def build(*args, **kwargs) -> None:
    add_fillet(*args, **kwargs)
