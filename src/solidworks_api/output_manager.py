"""Controlled output path planning for API executor."""

from __future__ import annotations

from pathlib import Path

from app.config import EXPORTS_DIR, OUTPUTS_DIR, PARTS_DIR, PREVIEWS_DIR, ensure_dirs


def _assert_inside(child: Path, parent: Path) -> None:
    child_resolved = child.resolve()
    parent_resolved = parent.resolve()
    if child_resolved != parent_resolved and parent_resolved not in child_resolved.parents:
        raise ValueError("输出路径必须位于项目 workspace/outputs 内")


def next_versioned_path(folder: Path, part_name: str, suffix: str) -> Path:
    ensure_dirs()
    _assert_inside(folder, OUTPUTS_DIR)
    safe_name = "".join(ch for ch in part_name if ch.isalnum() or ch in {"_", "-"}).strip("_-")
    if not safe_name:
        safe_name = "ai_part"
    for index in range(1, 1000):
        candidate = folder / f"{safe_name}_v{index:03d}{suffix}"
        _assert_inside(candidate, folder)
        _assert_inside(candidate, OUTPUTS_DIR)
        if not candidate.exists():
            return candidate
    raise ValueError("无法生成安全的版本化输出文件名")


def plan_output_paths(part_name: str, outputs: dict) -> dict[str, Path]:
    planned: dict[str, Path] = {}
    if outputs.get("save_sldprt", True):
        planned["sldprt"] = next_versioned_path(PARTS_DIR, part_name, ".SLDPRT")
    if outputs.get("export_step", True):
        planned["step"] = next_versioned_path(EXPORTS_DIR, part_name, ".STEP")
    if outputs.get("capture_png", True):
        planned["png"] = next_versioned_path(PREVIEWS_DIR, part_name, ".PNG")
    return planned
