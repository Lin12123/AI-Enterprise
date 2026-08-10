"""File and text safety rules for declarative CAD plans."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


FORBIDDEN_KEYS = {
    "output_dir",
    "path",
    "file_path",
    "save_path",
    "absolute_path",
    "system_path",
    "script",
    "macro",
    "command",
    "python_code",
    "vba_code",
    "powershell",
    "powershell_code",
    "shell",
    "shell_code",
    "subprocess",
    "delete",
    "remove",
    "overwrite",
    "csharp_code",
    "cs_code",
}

FORBIDDEN_TEXT = {
    "vba",
    "python",
    "powershell",
    "shell",
    "cmd.exe",
    "c#",
    "csharp",
    "subprocess",
    "os.system",
    "macro",
    "script",
    "registry",
    "delete",
    "remove-item",
}

_TOKEN_FORBIDDEN_TEXT = {
    "vba",
    "python",
    "powershell",
    "shell",
    "c#",
    "csharp",
    "subprocess",
    "macro",
    "script",
    "registry",
    "delete",
}

_LITERAL_FORBIDDEN_TEXT = {
    "cmd.exe",
    "os.system",
    "remove-item",
}


def is_project_local(path: Path, project_root: Path) -> bool:
    resolved = path.resolve()
    root = project_root.resolve()
    return resolved == root or root in resolved.parents


def validate_no_dangerous_fields(value: Any, location: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_location = f"{location}.{key_text}"
            if key_text.lower() in FORBIDDEN_KEYS:
                errors.append(f"禁止字段: {child_location}")
            errors.extend(validate_no_dangerous_fields(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(validate_no_dangerous_fields(child, f"{location}[{index}]"))
    elif isinstance(value, str):
        lower = value.lower()
        for token in _TOKEN_FORBIDDEN_TEXT:
            if re.search(rf"(?<![a-z0-9_]){re.escape(token)}(?![a-z0-9_])", lower):
                errors.append(f"禁止运行时代码或命令文本: {location}: {token}")
        for token in _LITERAL_FORBIDDEN_TEXT:
            if token in lower:
                errors.append(f"禁止运行时代码或命令文本: {location}: {token}")
    return errors


def validate_outputs(outputs: Any) -> list[str]:
    if outputs is None:
        return []
    if not isinstance(outputs, dict):
        return ["outputs 必须是对象"]
    allowed = {"save_sldprt", "export_step", "capture_png"}
    errors: list[str] = []
    for key, value in outputs.items():
        if key not in allowed:
            errors.append(f"outputs 包含不允许的字段: {key}")
        if not isinstance(value, bool):
            errors.append(f"outputs.{key} 必须是布尔值")
    return errors
