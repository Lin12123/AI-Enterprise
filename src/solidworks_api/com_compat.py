"""Compatibility helpers for version-sensitive SOLIDWORKS COM calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class ComAttempt:
    name: str
    args: tuple[Any, ...]


class ComCompatibilityError(RuntimeError):
    def __init__(self, operation: str, errors: Iterable[str]) -> None:
        self.operation = operation
        self.errors = tuple(errors)
        super().__init__(f"{operation} failed for all supported COM signatures: " + " | ".join(self.errors))


def call_first_available(target: object, method_names: Iterable[str], attempts_by_method: Callable[[str], Iterable[ComAttempt]]) -> object:
    """Try supported method/signature candidates and return the first non-None result."""

    errors: list[str] = []
    for method_name in method_names:
        method = getattr(target, method_name, None)
        if method is None:
            errors.append(f"{method_name}: unavailable")
            continue
        for attempt in attempts_by_method(method_name):
            try:
                result = method(*attempt.args)
            except Exception as exc:
                errors.append(f"{method_name}/{attempt.name}: {exc}")
                continue
            if result is not None:
                return result
            errors.append(f"{method_name}/{attempt.name}: returned None")
    raise ComCompatibilityError("/".join(method_names), errors)


def safe_select_by_id(sw_model: object, name: str, object_type: str, append: bool = False, mark: int = 0) -> bool:
    extension = getattr(sw_model, "Extension", None)
    if extension is None or not hasattr(extension, "SelectByID2"):
        return False
    try:
        return bool(extension.SelectByID2(name, object_type, 0, 0, 0, append, mark, None, 0))
    except Exception:
        return False
