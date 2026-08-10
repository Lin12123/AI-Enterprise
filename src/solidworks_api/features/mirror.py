"""Mirror feature implementation for fixed API executor."""

OPERATION_TYPE = "mirror"
STATUS = "implemented"


def mirror_feature(sw_model: object, params: dict, state: dict) -> None:
    from cad_dsl.feature_references import normalize_feature_reference
    from solidworks_api.features.pattern import _select_feature_by_name

    seed_feature = normalize_feature_reference(params["seed_feature"])
    mirror_plane = str(params["mirror_plane"])
    _select_feature_by_name(sw_model, seed_feature)
    if not sw_model.Extension.SelectByID2(mirror_plane, "PLANE", 0, 0, 0, True, 1, None, 0):
        raise RuntimeError(f"无法选择 mirror_plane: {mirror_plane}")
    if hasattr(sw_model.FeatureManager, "InsertMirrorFeature2"):
        feature = sw_model.FeatureManager.InsertMirrorFeature2(False, False, False, False)
    elif hasattr(sw_model.FeatureManager, "InsertMirrorFeature"):
        feature = sw_model.FeatureManager.InsertMirrorFeature(False, False, False, False)
    else:
        raise RuntimeError("Mirror feature API is unavailable")
    if feature is None:
        raise RuntimeError("Mirror feature API returned None")


def build(*_args, **_kwargs) -> None:
    mirror_feature(*_args, **_kwargs)
