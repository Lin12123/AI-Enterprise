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
