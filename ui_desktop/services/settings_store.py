"""Settings storage for AI-SW Workbench."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ui_desktop.services.job_store import OUTPUT_ROOT, PROJECT_ROOT, _resolve_inside_root


SETTINGS_PATH = PROJECT_ROOT / "outputs" / "jobs" / "workbench_settings.json"
SENSITIVE_TOKENS = ("api_key", "apikey", "openai_api_key", "secret", "token")


DEFAULT_SETTINGS = {
    "default_provider": "local",
    "local_llm_base_url": "http://localhost:11434/v1",
    "local_llm_model": "qwen2.5-coder:7b",
    "executor_mode": "api_executor",
    "dry_run_default": True,
    "output_root": str(OUTPUT_ROOT),
}


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = _resolve_inside_root(path or SETTINGS_PATH, OUTPUT_ROOT)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return dict(DEFAULT_SETTINGS)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        settings = dict(DEFAULT_SETTINGS)
        settings.update(_sanitize_settings(data))
        return settings

    def save(self, settings: dict[str, Any]) -> None:
        safe_settings = dict(DEFAULT_SETTINGS)
        safe_settings.update(_sanitize_settings(settings))
        self.path.write_text(json.dumps(safe_settings, ensure_ascii=False, indent=2), encoding="utf-8")


def _sanitize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in settings.items():
        lowered = str(key).lower()
        if any(token in lowered for token in SENSITIVE_TOKENS):
            continue
        safe[key] = value
    return safe
