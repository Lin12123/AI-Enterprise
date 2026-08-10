"""Plan preview view."""

from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout, QWidget

from ui_desktop.services.i18n import SECTIONS
from ui_desktop.widgets.json_viewer import JsonViewer
from ui_desktop.widgets.parameter_table import ParameterTable
from ui_desktop.widgets.plan_step_list import PlanStepList


class PlanView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.intent_label = QLabel("暂无设计意图")
        self.parameter_table = ParameterTable()
        self.step_list = PlanStepList()
        self.json_viewer = JsonViewer()

        layout = QVBoxLayout(self)
        layout.addWidget(_box(SECTIONS["design_intent"], self.intent_label))
        layout.addWidget(_box(SECTIONS["parameters"], self.parameter_table))
        layout.addWidget(_box(SECTIONS["operations"], self.step_list))
        layout.addWidget(_box(SECTIONS["featureplan_json"], self.json_viewer), 1)

    def load_candidate(self, candidate: dict) -> None:
        intent = candidate.get("intent", {})
        self.intent_label.setText(
            "\n".join(
                [
                    f"零件类型: {intent.get('part_type', '')}",
                    f"主要结构: {intent.get('main_structure', '')}",
                    f"单位: {candidate.get('unit', '')}",
                    f"坐标基准: {intent.get('coordinate_basis', '')}",
                    f"assumptions: {', '.join(intent.get('assumptions', []))}",
                    f"missing_info: {', '.join(intent.get('missing_info', []))}",
                ]
            )
        )
        self.parameter_table.load_parameters(candidate.get("parameters", {}))
        self.step_list.load_operations(candidate.get("operations", []))
        self.json_viewer.set_json(candidate)


def _box(title: str, child: QWidget) -> QGroupBox:
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    layout.addWidget(child)
    return box
