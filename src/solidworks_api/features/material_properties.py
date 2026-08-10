"""Material and custom-property feature implementations."""

from __future__ import annotations

from cad_dsl.material_catalog import MaterialRecord, resolve_material


OPERATION_TYPE = "material_properties"
STATUS = "implemented"


def set_material(sw_model: object, params: dict, state: dict) -> None:
    material_value = params.get("material_id", params.get("material"))
    record = resolve_material(material_value)
    if record is None:
        raise RuntimeError(f"Material {material_value} is not present in the project official SOLIDWORKS material catalog index")

    setter = _material_setter(sw_model)
    if setter is None:
        raise RuntimeError("SetMaterialPropertyName API is unavailable")

    attempts: list[str] = []
    empty_verification_candidate: tuple[str, str] | None = None
    for database, material_name in record.solidworks_candidates:
        label = f"{database or '<default>'}/{material_name}"
        try:
            result = setter("", database, material_name)
        except Exception as exc:
            attempts.append(f"{label}: {exc}")
            continue

        if result is False:
            attempts.append(f"{label}: rejected by SOLIDWORKS")
            continue

        if not _material_getter_available(sw_model):
            _store_material_state(state, record, database, material_name, unverified_reason="material getter API unavailable")
            return

        matches, actual_values = _material_matches(sw_model, database, record)
        if matches:
            _store_material_state(state, record, database, material_name)
            return
        if not actual_values:
            attempts.append(f"{label}: applied but SOLIDWORKS material getter returned <empty>")
            if empty_verification_candidate is None:
                empty_verification_candidate = (database, material_name)
            continue
        attempts.append(f"{label}: SOLIDWORKS returned {', '.join(actual_values)}")

    if empty_verification_candidate is not None:
        database, material_name = empty_verification_candidate
        _store_material_state(
            state,
            record,
            database,
            material_name,
            unverified_reason="SOLIDWORKS material getter returned <empty> after setter did not reject the catalog candidate",
        )
        return

    raise RuntimeError(
        f"Material {record.material_id} could not be applied or verified from project catalog candidates. "
        f"Tried: {' | '.join(attempts) or '<none>'}. "
        "Update resources/materials/material_catalog.json with official SOLIDWORKS material database/name candidates."
    )


def _store_material_state(
    state: dict,
    record: MaterialRecord,
    database: str,
    material_name: str,
    unverified_reason: str = "",
) -> None:
    state["material"] = record.material_id
    state["solidworks_material"] = _record_state(record, database, material_name)
    if unverified_reason:
        state["material_unverified"] = True
        state["material_unverified_reason"] = unverified_reason


def _record_state(record: MaterialRecord, database: str | None = None, material_name: str | None = None) -> dict[str, str]:
    return {
        "material_id": record.material_id,
        "database": record.solidworks_database if database is None else database,
        "name": record.solidworks_material_name if material_name is None else material_name,
    }


def _material_setter(sw_model: object):
    if hasattr(sw_model, "SetMaterialPropertyName2"):
        return sw_model.SetMaterialPropertyName2
    if hasattr(sw_model, "SetMaterialPropertyName"):
        return sw_model.SetMaterialPropertyName
    return None


def _material_getter_available(sw_model: object) -> bool:
    return hasattr(sw_model, "GetMaterialPropertyName2") or hasattr(sw_model, "GetMaterialPropertyName")


def _material_matches(sw_model: object, database: str, record: MaterialRecord) -> tuple[bool, tuple[str, ...]]:
    actual_values = []
    if hasattr(sw_model, "GetMaterialPropertyName2"):
        for args in (("", database), ("", ""), ("",)):
            try:
                actual_values.append(sw_model.GetMaterialPropertyName2(*args))
            except Exception:
                continue
    if hasattr(sw_model, "GetMaterialPropertyName"):
        for args in (("", database), ("", ""), ("",)):
            try:
                actual_values.append(sw_model.GetMaterialPropertyName(*args))
            except Exception:
                continue

    actual_texts = tuple(_material_text(value) for value in actual_values if _material_text(value))
    if not actual_texts:
        return False, actual_texts

    expected_values = (
        record.material_id,
        record.display_name,
        record.solidworks_material_name,
        *(name for _, name in record.solidworks_candidates),
        *record.search_terms,
    )
    expected_texts = tuple(_normalize_material_text(value) for value in expected_values if str(value or "").strip())
    for actual in actual_texts:
        normalized_actual = _normalize_material_text(actual)
        for expected in expected_texts:
            if normalized_actual == expected or expected in normalized_actual or normalized_actual in expected:
                return True, actual_texts
    return False, actual_texts


def _material_text(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value if item is not None).strip().lower()
    return str(value or "").strip().lower()


def _normalize_material_text(value: object) -> str:
    text = _material_text(value)
    for char in (" ", "_", "-", "(", ")", "[", "]"):
        text = text.replace(char, "")
    return text


def set_custom_property(sw_model: object, params: dict, state: dict) -> None:
    key = str(params["key"])
    value = str(params["value"])
    extension = getattr(sw_model, "Extension", None)
    if extension is None or not hasattr(extension, "CustomPropertyManager"):
        raise RuntimeError("CustomPropertyManager API is unavailable")
    manager = extension.CustomPropertyManager("")
    if hasattr(manager, "Add3"):
        manager.Add3(key, 30, value, 2)
    elif hasattr(manager, "Set2"):
        manager.Set2(key, value)
    elif hasattr(manager, "Add2"):
        manager.Add2(key, 30, value)
    else:
        raise RuntimeError("Custom property write API is unavailable")
    state.setdefault("custom_properties", {})[key] = value
