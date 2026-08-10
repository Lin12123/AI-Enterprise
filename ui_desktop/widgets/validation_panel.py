"""Validation status panel."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

from ui_desktop.services.i18n import MESSAGES


class ValidationPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.labels = {
            "Dependency Resolver": QLabel(MESSAGES["not_run"]),
            "Constraint Validator": QLabel(MESSAGES["not_run"]),
            "Schema Validator": QLabel(MESSAGES["not_run"]),
            "Policy Engine": QLabel(MESSAGES["not_run"]),
        }
        layout = QFormLayout(self)
        for name, label in self.labels.items():
            layout.addRow(name, label)

    def set_all(self, status: str) -> None:
        for label in self.labels.values():
            label.setText(status)

    def load_result(self, result: dict) -> None:
        mapping = {
            "Dependency Resolver": result.get("dependency_result", {}),
            "Constraint Validator": result.get("constraint_result", {}),
            "Schema Validator": result.get("schema_result", {}),
            "Policy Engine": result.get("policy_result", {}),
        }
        for name, payload in mapping.items():
            if not isinstance(payload, dict):
                self.labels[name].setText(MESSAGES["failed"])
                continue
            status = MESSAGES["passed"] if payload.get("passed") else MESSAGES["failed"]
            errors = payload.get("errors") or []
            if errors:
                status += f" ({len(errors)} 个阻塞错误)"
            self.labels[name].setText(status)
