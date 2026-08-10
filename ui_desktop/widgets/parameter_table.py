"""Editable parameter table."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


class ParameterTable(QTableWidget):
    parameter_changed = Signal()

    def __init__(self) -> None:
        super().__init__(0, 3)
        self.setHorizontalHeaderLabels(["Parameter", "Value", "Unit"])
        self.itemChanged.connect(lambda _item: self.parameter_changed.emit())

    def load_parameters(self, parameters: dict) -> None:
        self.blockSignals(True)
        self.setRowCount(0)
        for name, payload in parameters.items():
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, QTableWidgetItem(str(name)))
            self.setItem(row, 1, QTableWidgetItem(str(payload.get("value", ""))))
            self.setItem(row, 2, QTableWidgetItem(str(payload.get("unit", ""))))
        self.resizeColumnsToContents()
        self.blockSignals(False)
