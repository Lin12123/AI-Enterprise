"""Validation view."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ui_desktop.widgets.validation_panel import ValidationPanel


class ValidationView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.panel = ValidationPanel()
        layout = QVBoxLayout(self)
        layout.addWidget(self.panel)
