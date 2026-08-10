"""Project-local index of official SOLIDWORKS material entries."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def catalog_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    return base / "resources" / "materials" / "material_catalog.json"


@dataclass(frozen=True)
class MaterialRecord:
    material_id: str
    display_name: str
    solidworks_database: str
    solidworks_material_name: str
    solidworks_candidates: tuple[tuple[str, str], ...]
    search_terms: tuple[str, ...]
    status: str = "implemented"
    notes: str = ""


@lru_cache(maxsize=1)
def load_material_catalog() -> tuple[MaterialRecord, ...]:
    data = json.loads(catalog_path().read_text(encoding="utf-8"))
    records: list[MaterialRecord] = []
    for item in data.get("materials", []):
        primary_database = str(item.get("solidworks_database", ""))
        primary_name = str(item["solidworks_material_name"])
        candidates = [(primary_database, primary_name)]
        for candidate in item.get("solidworks_candidates", ()):
            if isinstance(candidate, dict):
                database = str(candidate.get("database", primary_database))
                name = str(candidate.get("name", "")).strip()
            elif isinstance(candidate, (list, tuple)) and len(candidate) >= 2:
                database = str(candidate[0])
                name = str(candidate[1]).strip()
            else:
                continue
            if name:
                candidates.append((database, name))
        records.append(
            MaterialRecord(
                material_id=str(item["material_id"]),
                display_name=str(item.get("display_name", item["solidworks_material_name"])),
                solidworks_database=primary_database,
                solidworks_material_name=primary_name,
                solidworks_candidates=tuple(dict.fromkeys(candidates)),
                search_terms=tuple(str(alias) for alias in item.get("search_terms", item.get("aliases", ()))),
                status=str(item.get("status", "implemented")),
                notes=str(item.get("notes", "")),
            )
        )
    return tuple(records)


def material_ids() -> set[str]:
    return {record.material_id for record in load_material_catalog() if record.status == "implemented"}


def resolve_material(value: Any) -> MaterialRecord | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = _normalize(text)
    for record in load_material_catalog():
        candidates = (
            record.material_id,
            record.display_name,
            record.solidworks_material_name,
            *(name for _, name in record.solidworks_candidates),
            *record.search_terms,
        )
        if normalized in {_normalize(candidate) for candidate in candidates}:
            return record
    return None


def prompt_material_lines() -> tuple[str, ...]:
    lines: list[str] = []
    for record in load_material_catalog():
        search_terms = ", ".join(record.search_terms[:8])
        candidates = ", ".join(f"{database or '<default>'}/{name}" for database, name in record.solidworks_candidates[:5])
        lines.append(
            f"- material_id={record.material_id}; output material='{record.solidworks_material_name}'; "
            f"solidworks_database='{record.solidworks_database}'; candidates=[{candidates}]; "
            f"search_terms=[{search_terms}]"
        )
    return tuple(lines)


def _normalize(value: str) -> str:
    return value.strip().lower().replace("_", " ").replace("-", " ").replace(" ", "")
