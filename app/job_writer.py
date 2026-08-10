import json
from pathlib import Path

from app.config import JOBS_DIR, ensure_dirs


def _bool_text(value) -> str:
    return "true" if bool(value) else "false"


def _num_text(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _assert_workspace_path(path: Path) -> None:
    resolved = path.resolve()
    jobs = JOBS_DIR.resolve()
    if resolved != jobs and jobs not in resolved.parents:
        raise ValueError("写入路径必须位于 workspace/jobs 中")


def _reject_output_dir(cadplan: dict) -> None:
    if isinstance(cadplan, dict):
        for key, value in cadplan.items():
            if key == "output_dir":
                raise ValueError("不接受用户自定义 output_dir")
            _reject_output_dir(value)
    elif isinstance(cadplan, list):
        for value in cadplan:
            _reject_output_dir(value)


def write_cadplan_json(cadplan: dict) -> Path:
    _reject_output_dir(cadplan)
    ensure_dirs()
    target = JOBS_DIR / "current_cadplan.json"
    _assert_workspace_path(target)
    target.write_text(json.dumps(cadplan, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def write_job_ini(cadplan: dict) -> Path:
    _reject_output_dir(cadplan)
    ensure_dirs()
    target = JOBS_DIR / "current_job.ini"
    _assert_workspace_path(target)

    base = cadplan["base"]
    corner = cadplan.get("corner_holes", {})
    boss = cadplan.get("center_boss", {})
    center_hole = cadplan.get("center_hole", {})
    fillet = cadplan.get("fillet", {})
    outputs = cadplan.get("outputs", {})

    lines = [
        "template=mounting_plate",
        "unit=mm",
        f"part_name={cadplan.get('part_name', 'ai_mounting_plate')}",
        "",
        f"base_shape={base.get('shape', 'rectangle')}",
        f"base_diameter={_num_text(base.get('diameter', 0))}",
        f"base_length={_num_text(base['length'])}",
        f"base_width={_num_text(base['width'])}",
        f"base_thickness={_num_text(base['thickness'])}",
        "",
        f"corner_holes_enabled={_bool_text(corner.get('enabled', False))}",
        f"corner_hole_diameter={_num_text(corner.get('diameter', 0))}",
        f"corner_hole_offset_x={_num_text(corner.get('offset_x', 0))}",
        f"corner_hole_offset_y={_num_text(corner.get('offset_y', 0))}",
        "",
        f"center_boss_enabled={_bool_text(boss.get('enabled', False))}",
        f"center_boss_diameter={_num_text(boss.get('diameter', 0))}",
        f"center_boss_height={_num_text(boss.get('height', 0))}",
        "",
        f"center_hole_enabled={_bool_text(center_hole.get('enabled', False))}",
        f"center_hole_diameter={_num_text(center_hole.get('diameter', 0))}",
        "",
        f"fillet_enabled={_bool_text(fillet.get('enabled', False))}",
        f"fillet_radius={_num_text(fillet.get('radius', 0))}",
        "",
        f"save_sldprt={_bool_text(outputs.get('save_sldprt', True))}",
        f"export_step={_bool_text(outputs.get('export_step', True))}",
        f"capture_png={_bool_text(outputs.get('capture_png', True))}",
        "",
    ]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target
