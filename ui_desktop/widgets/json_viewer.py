"""Read-only JSON viewer."""

from __future__ import annotations

import json

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit


class JsonViewer(QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))

    def set_json(self, payload: dict) -> None:
        self.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))
