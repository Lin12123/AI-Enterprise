"""Resource path helpers for source and PyInstaller runtime."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative_path: str) -> str:
    """Return an absolute resource path for source or PyInstaller runtime."""

    relative = Path(relative_path)
    if relative.is_absolute():
        relative = Path(*relative.parts[1:])
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return str(base / relative)
