"""Entry point for AI-SW Workbench."""

from __future__ import annotations

import faulthandler
import os
import sys
import traceback
from pathlib import Path


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _looks_like_project_root(path: Path) -> bool:
    return (path / "app").is_dir() and (path / "src").is_dir() and (path / "ui_desktop").is_dir()


def _discover_project_root() -> Path:
    env_root = os.environ.get("AI_SW_PROJECT_ROOT", "").strip()
    if env_root:
        candidate = Path(env_root)
        if _looks_like_project_root(candidate):
            return candidate.resolve()

    candidates: list[Path] = []
    for base in (Path.cwd(), _runtime_root(), Path(__file__).resolve().parents[1]):
        try:
            resolved = base.resolve()
        except Exception:
            continue
        candidates.append(resolved)
        candidates.extend(resolved.parents)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if _looks_like_project_root(candidate):
            return candidate

    return _runtime_root()


def _ensure_project_root() -> None:
    project_root = _discover_project_root()
    os.environ["AI_SW_PROJECT_ROOT"] = str(project_root)
    for path in (project_root, project_root / "src"):
        path_text = str(path)
        if path_text in sys.path:
            sys.path.remove(path_text)
        sys.path.insert(0, path_text)


def _crash_log_path() -> Path:
    output_dir = _runtime_root() / "outputs" / "jobs"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / "workbench_crash.log"


def _install_crash_logging() -> None:
    crash_log = _crash_log_path()
    crash_file = crash_log.open("a", encoding="utf-8")
    faulthandler.enable(file=crash_file, all_threads=True)

    def excepthook(exc_type, exc_value, exc_traceback):
        with crash_log.open("a", encoding="utf-8") as handle:
            handle.write("\n=== Unhandled Workbench Exception ===\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=handle)
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = excepthook


def main() -> int:
    _ensure_project_root()
    _install_crash_logging()
    from PySide6.QtWidgets import QApplication

    from ui_desktop.app_window import WorkbenchWindow

    app = QApplication(sys.argv)
    window = WorkbenchWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
