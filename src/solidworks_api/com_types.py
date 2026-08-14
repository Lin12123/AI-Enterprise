"""Small COM argument helpers for pywin32/SOLIDWORKS calls."""

from __future__ import annotations


def dispatch_none():
    """Return a COM Dispatch Nothing value when pywin32 is available.

    Some SOLIDWORKS methods accept VBA `Nothing` for callout/dispatch
    parameters. Passing plain Python `None` can raise type mismatch on older
    SOLIDWORKS/pywin32 combinations.
    """

    try:
        import pythoncom  # type: ignore[import-not-found]
        import win32com.client  # type: ignore[import-not-found]
    except ImportError:
        return None
    return win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)


def variant_empty_array():
    """Return an empty COM variant array when pywin32 is available."""

    try:
        import pythoncom  # type: ignore[import-not-found]
        import win32com.client  # type: ignore[import-not-found]
    except ImportError:
        return []
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, [])


def byref_int(value: int = 0):
    """Return a by-reference COM int when pywin32 is available."""

    try:
        import pythoncom  # type: ignore[import-not-found]
        import win32com.client  # type: ignore[import-not-found]
    except ImportError:
        return value
    return win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, value)


def get_doc_type(model: object):
    """Read a SOLIDWORKS document type (swDocumentTypes_e) robustly.

    Depending on the pywin32 dispatch mode, ``IModelDoc2.GetType`` can surface
    either as a callable method or as an already-evaluated integer property.
    Calling an int raises "'int' object is not callable"; treating a method as
    an int fails too. This helper handles both, returning an int, or None when
    the type cannot be determined.
    """

    getter = getattr(model, "GetType", None)
    if getter is None:
        return None
    value = getter() if callable(getter) else getter
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

