"""Unit conversion helpers for SOLIDWORKS API boundaries."""


def mm_to_m(value_mm: float) -> float:
    return float(value_mm) / 1000.0


def ensure_mm(unit: str) -> None:
    if unit != "mm":
        raise ValueError("Only mm FeaturePlans are allowed")
