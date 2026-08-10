"""FeaturePlan step preview table."""

from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


class PlanStepList(QTableWidget):
    def __init__(self) -> None:
        super().__init__(0, 6)
        self.setHorizontalHeaderLabels(["#", "op", "name", "depends_on", "produces", "status"])

    def load_operations(self, operations: list[dict]) -> None:
        self.setRowCount(0)
        for operation in operations:
            row = self.rowCount()
            self.insertRow(row)
            values = [
                operation.get("index", row + 1),
                operation.get("op", ""),
                operation.get("name", ""),
                ", ".join(operation.get("depends_on", [])),
                ", ".join(operation.get("produces", [])),
                operation.get("status", ""),
            ]
            for column, value in enumerate(values):
                self.setItem(row, column, QTableWidgetItem(str(value)))
        self.resizeColumnsToContents()
