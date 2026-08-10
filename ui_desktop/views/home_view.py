"""New task composer view."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ui_desktop.widgets.natural_language_input import NaturalLanguageInput


class HomeView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.input_widget = NaturalLanguageInput()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.input_widget)
