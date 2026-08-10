"""Selector value objects for future stable geometry selection."""

from __future__ import annotations

from dataclasses import dataclass

from solidworks_api.com_types import dispatch_none
from solidworks_api.com_compat import safe_select_by_id
from solidworks_api.version_profile import DEFAULT_PROFILE


@dataclass(frozen=True)
class FaceSelector:
    strategy: str
    parameters: dict


@dataclass(frozen=True)
class EdgeSelector:
    strategy: str
    parameters: dict


def top_plane_name_zh() -> str:
    return "".join(chr(code) for code in (0x4E0A, 0x89C6, 0x57FA, 0x51C6, 0x9762))


def select_top_plane(sw_model: object) -> None:
    sw_model.ClearSelection2(True)
    callout = dispatch_none()
    errors: list[str] = []
    for plane_name in DEFAULT_PROFILE.top_plane_aliases:
        try:
            if sw_model.Extension.SelectByID2(plane_name, "PLANE", 0.0, 0.0, 0.0, False, 0, callout, 0):
                return
            errors.append(f"SelectByID2({plane_name}): returned false")
        except Exception as exc:
            errors.append(f"SelectByID2({plane_name}): {exc}")

    for plane_name in DEFAULT_PROFILE.top_plane_aliases:
        try:
            feature = sw_model.FeatureByName(plane_name)
            if feature is not None and feature.Select2(False, 0):
                return
            errors.append(f"FeatureByName({plane_name}).Select2: returned false")
        except Exception as exc:
            errors.append(f"FeatureByName({plane_name}): {exc}")

    raise RuntimeError("无法选择 Top Plane / 上视基准面。详情: " + " | ".join(errors))


def select_feature_by_name(sw_model: object, feature_name: str) -> None:
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
    raise RuntimeError(f"Unable to select feature: {feature_name}")


def select_feature_top_face(sw_model: object, feature: object, fallback_z_m: float | None = None) -> None:
    errors: list[str] = []
    top_face = _top_face_of_feature(feature, errors)
    if top_face is not None and _select_face_object(sw_model, top_face):
        return
    if fallback_z_m is not None:
        try:
            select_face_by_z(sw_model, fallback_z_m)
            return
        except Exception as exc:
            errors.append(str(exc))
    detail = " | ".join(errors) if errors else "feature does not expose selectable faces"
    raise RuntimeError(f"Unable to select feature top face: {detail}")


def _top_face_of_feature(feature: object, errors: list[str]) -> object | None:
    faces = None
    for method_name in ("GetFaces", "IGetFaces2"):
        try:
            method = getattr(feature, method_name, None)
        except Exception as exc:
            errors.append(f"{method_name}: {exc}")
            continue
        if method is None:
            continue
        try:
            faces = method()
            if faces:
                break
            errors.append(f"{method_name}: returned empty")
        except Exception as exc:
            errors.append(f"{method_name}: {exc}")
    if not faces:
        return None

    best_face = None
    best_z = None
    for face in faces:
        z_value = _face_top_z(face, errors)
        if z_value is None:
            continue
        if best_z is None or z_value > best_z:
            best_z = z_value
            best_face = face
    if best_face is None:
        errors.append("feature faces do not expose bounding boxes")
    return best_face


def feature_z_range(feature: object) -> tuple[float, float] | None:
    errors: list[str] = []
    faces = None
    for method_name in ("GetFaces", "IGetFaces2"):
        try:
            method = getattr(feature, method_name, None)
        except Exception:
            continue
        if method is None:
            continue
        try:
            faces = method()
            if faces:
                break
            errors.append(f"{method_name}: returned empty")
        except Exception:
            faces = None
    if not faces:
        return None

    min_z = None
    max_z = None
    for face in faces:
        box = _face_box(face)
        if box is None:
            continue
        try:
            face_min_z = float(box[2])
            face_max_z = float(box[5])
        except Exception:
            continue
        if min_z is None or face_min_z < min_z:
            min_z = face_min_z
        if max_z is None or face_max_z > max_z:
            max_z = face_max_z
    if min_z is None or max_z is None:
        return None
    return min_z, max_z


def _face_box(face: object) -> tuple[float, float, float, float, float, float] | None:
    try:
        get_box = getattr(face, "GetBox", None)
    except Exception:
        return None
    if get_box is None:
        return None
    try:
        box = get_box()
    except Exception:
        return None
    if not isinstance(box, (list, tuple)) or len(box) < 6:
        return None
    return tuple(box[:6])


def _face_top_z(face: object, errors: list[str]) -> float | None:
    box = _face_box(face)
    if box is None:
        errors.append("face.GetBox: invalid box")
        return None
    try:
        return float(box[5])
    except Exception as exc:
        errors.append(f"face.GetBox z: {exc}")
        return None


def _select_face_object(sw_model: object, face: object) -> bool:
    sw_model.ClearSelection2(True)
    for method_name in ("Select4", "Select2"):
        method = getattr(face, method_name, None)
        if method is None:
            continue
        try:
            if method_name == "Select4":
                if bool(method(False, dispatch_none())):
                    return True
            else:
                if bool(method(False, 0)):
                    return True
        except Exception:
            continue
    return False



def select_face_by_point_candidates(sw_model: object, candidates: list[tuple[float, float, float]]) -> None:
    errors: list[str] = []

    def _try_once() -> bool:
        sw_model.ClearSelection2(True)
        for x_m, y_m, z_m in candidates:
            try:
                if sw_model.Extension.SelectByID2("", "FACE", float(x_m), float(y_m), float(z_m), False, 0, dispatch_none(), 0):
                    return True
                errors.append(f"SelectByID2(FACE @ {x_m},{y_m},{z_m}): returned false")
            except Exception as exc:
                errors.append(f"SelectByID2(FACE @ {x_m},{y_m},{z_m}): {exc}")
        return False

    if _try_once():
        return

    try:
        sw_model.ForceRebuild3(False)
    except Exception as exc:
        errors.append(f"ForceRebuild3: {exc}")

    if _try_once():
        return

    raise RuntimeError("Unable to select FACE from candidate points after rebuild/retry: " + " | ".join(errors))

def select_face_by_z(sw_model: object, z_m: float) -> None:
    sw_model.ClearSelection2(True)
    # TODO: Coordinate face selection should be replaced by stable topology selectors.
    if sw_model.Extension.SelectByID2("", "FACE", 0.0, 0.0, float(z_m), False, 0, dispatch_none(), 0):
        return

    try:
        sw_model.ForceRebuild3(False)
    except Exception:
        pass

    sw_model.ClearSelection2(True)
    if not sw_model.Extension.SelectByID2("", "FACE", 0.0, 0.0, float(z_m), False, 0, dispatch_none(), 0):
        raise RuntimeError(f"Unable to select FACE at z={float(z_m)} m after rebuild/retry")
