"""Status badge widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel


class StatusBadge(QLabel):
    def __init__(self, text: str = "created", level: str = "neutral") -> None:
        super().__init__(text)
        self.setProperty("badgeLevel", level)
        self.setObjectName("StatusBadge")

    def set_status(self, text: str, level: str = "neutral") -> None:
        self.setText(text)
        self.setProperty("badgeLevel", level)
        self.style().unpolish(self)
        self.style().polish(self)
