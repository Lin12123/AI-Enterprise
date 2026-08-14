from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
JOBS_DIR = WORKSPACE_DIR / "jobs"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"
PARTS_DIR = OUTPUTS_DIR / "parts"
EXPORTS_DIR = OUTPUTS_DIR / "exports"
PREVIEWS_DIR = OUTPUTS_DIR / "previews"
DRAWINGS_DIR = OUTPUTS_DIR / "drawings"
LOGS_DIR = WORKSPACE_DIR / "logs"


def ensure_dirs() -> None:
    """Create required project-local workspace directories."""
    for directory in (
        WORKSPACE_DIR,
        JOBS_DIR,
        OUTPUTS_DIR,
        PARTS_DIR,
        EXPORTS_DIR,
        PREVIEWS_DIR,
        DRAWINGS_DIR,
        LOGS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
