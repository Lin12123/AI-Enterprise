"""Settings view."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLineEdit, QWidget

from ui_desktop.services.settings_store import SettingsStore


class SettingsView(QWidget):
    def __init__(self, settings_store: SettingsStore | None = None) -> None:
        super().__init__()
        self.settings_store = settings_store or SettingsStore()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["local", "openai", "rule_based"])
        self.base_url_edit = QLineEdit()
        self.model_edit = QLineEdit()
        self.executor_mode_combo = QComboBox()
        self.executor_mode_combo.addItems(["api_executor", "legacy_vba"])
        self.dry_run_check = QCheckBox()
        self.output_root_edit = QLineEdit()
        self.output_root_edit.setReadOnly(True)

        layout = QFormLayout(self)
        layout.addRow("default_provider", self.provider_combo)
        layout.addRow("local_llm_base_url", self.base_url_edit)
        layout.addRow("local_llm_model", self.model_edit)
        layout.addRow("executor_mode", self.executor_mode_combo)
        layout.addRow("dry_run_default", self.dry_run_check)
        layout.addRow("output_root", self.output_root_edit)
        self.load()

    def load(self) -> None:
        settings = self.settings_store.load()
        self.provider_combo.setCurrentText(settings["default_provider"])
        self.base_url_edit.setText(settings["local_llm_base_url"])
        self.model_edit.setText(settings["local_llm_model"])
        self.executor_mode_combo.setCurrentText(settings["executor_mode"])
        self.dry_run_check.setChecked(bool(settings["dry_run_default"]))
        self.output_root_edit.setText(settings["output_root"])
