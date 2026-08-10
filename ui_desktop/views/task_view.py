"""Task history placeholder view."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TaskView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("任务历史"))
        layout.addWidget(QLabel("第一批实现使用本地 JSON JobStore，后续批次接入历史浏览。"))
