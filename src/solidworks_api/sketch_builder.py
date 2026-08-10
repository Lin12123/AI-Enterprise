"""Sketch helpers for fixed SOLIDWORKS API operations."""

from __future__ import annotations


def _select_base_top_face(sw_model: object, state: dict) -> None:
    from solidworks_api.com_types import dispatch_none
    from solidworks_api.selectors import select_face_by_point_candidates, select_face_by_z, select_feature_top_face, select_top_plane
    from solidworks_api.units import mm_to_m

    base = state.get("base", {})
    base_thickness = float(base.get("thickness", 0) or 0)
    base_top_z_m = base.get("top_z_m")
    if base_thickness <= 0 and base_top_z_m is None:
        select_top_plane(sw_model)
        return

    target_z_m = float(base_top_z_m) if base_top_z_m is not None else mm_to_m(base_thickness)
    base_feature = base.get("feature")
    if base_feature is not None:
        try:
            select_feature_top_face(sw_model, base_feature, target_z_m)
            return
        except Exception:
            pass

    length = float(base.get("length", 0) or 0)
    width = float(base.get("width", 0) or 0)
    if length > 0 and width > 0:
        inset = min(max(5.0, min(length, width) * 0.125), max(length / 2 - 1.0, 1.0), max(width / 2 - 1.0, 1.0))
        candidate_points_mm = [
            (0.0, width / 2 - inset),
            (0.0, -width / 2 + inset),
            (length / 2 - inset, 0.0),
            (-length / 2 + inset, 0.0),
            (length * 0.25, width * 0.25),
            (-length * 0.25, -width * 0.25),
        ]
        filtered = [(mm_to_m(x_mm), mm_to_m(y_mm), target_z_m) for x_mm, y_mm in candidate_points_mm]
        select_face_by_point_candidates(sw_model, filtered)
        return

    select_face_by_z(sw_model, target_z_m)


def _select_boss_top_face(sw_model: object, state: dict) -> None:
    from solidworks_api.selectors import select_face_by_z, select_feature_top_face

    boss = state.get("boss", {})
    boss_top_z_m = boss.get("top_z_m")
    boss_feature = boss.get("feature")
    if boss_top_z_m is None:
        raise RuntimeError("Boss top face is not available for host=boss")

    if boss_feature is not None:
        try:
            select_feature_top_face(sw_model, boss_feature, float(boss_top_z_m))
            return
        except Exception:
            pass

    select_face_by_z(sw_model, float(boss_top_z_m))


def _select_sketch_plane(sw_model: object, plane: str, state: dict, host: str = "base") -> None:
    from solidworks_api.com_types import dispatch_none
    from solidworks_api.selectors import select_top_plane

    normalized_host = str(host or "base").strip().lower()
    if plane in {"Top", ""}:
        select_top_plane(sw_model)
        return
    if plane in {"Front", "Right"}:
        sw_model.ClearSelection2(True)
        callout = dispatch_none()
        for plane_name in (plane, f"{plane} Plane"):
            if sw_model.Extension.SelectByID2(plane_name, "PLANE", 0.0, 0.0, 0.0, False, 0, callout, 0):
                return
        raise RuntimeError(f"Unable to select standard plane: {plane}")
    if plane == "top_face":
        if normalized_host == "boss":
            _select_boss_top_face(sw_model, state)
            return
        _select_base_top_face(sw_model, state)
        return
    raise RuntimeError(f"Unsupported sketch plane selector: {plane}")


def create_sketch(sw_model: object, params: dict, state: dict) -> None:
    name = str(params["name"])
    plane = str(params.get("plane", "Top"))
    host = str(params.get("host", "base"))
    _select_sketch_plane(sw_model, plane, state, host=host)
    sw_model.SketchManager.InsertSketch(True)
    state["active_sketch"] = name
    state.setdefault("sketches", {})[name] = {"plane": plane, "host": host, "entities": []}


def _require_active_sketch(params: dict, state: dict) -> str:
    sketch_name = str(params["sketch"])
    if state.get("active_sketch") != sketch_name:
        raise RuntimeError(f"Sketch is not active: {sketch_name}")
    return sketch_name


def sketch_center_rectangle(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.units import mm_to_m

    sketch_name = _require_active_sketch(params, state)
    center = params["center"]
    length = float(params["length"])
    width = float(params["width"])
    cx = float(center[0])
    cy = float(center[1])
    sw_model.SketchManager.CreateCenterRectangle(
        mm_to_m(cx),
        mm_to_m(cy),
        0.0,
        mm_to_m(cx + length / 2),
        mm_to_m(cy + width / 2),
        0.0,
    )
    state["sketches"][sketch_name]["entities"].append(
        {"type": "center_rectangle", "center": [cx, cy], "length": length, "width": width}
    )


def sketch_circle(sw_model: object, params: dict, state: dict) -> None:
    from solidworks_api.features.hole import _add_circle

    sketch_name = _require_active_sketch(params, state)
    center = params["center"]
    diameter = float(params["diameter"])
    cx = float(center[0])
    cy = float(center[1])
    _add_circle(sw_model, cx, cy, diameter)
    state["sketches"][sketch_name]["entities"].append(
        {"type": "circle", "center": [cx, cy], "diameter": diameter}
    )


class SketchBuilder:
    def create_sketch(self, plane_selector: object) -> None:
        raise NotImplementedError("Use fixed operation functions instead of dynamic sketch builder dispatch.")
