"""Mock result view."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QWidget

from ui_desktop.services.i18n import tr_button
from ui_desktop.services.job_store import OUTPUT_ROOT


class ResultView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.labels = {name: QLabel("-") for name in ("SLDPRT", "STEP", "PNG", "LOG", "OUTPUTS_JSON")}
        self.job_dir = ""
        self.open_button = QPushButton(tr_button("open_output_folder"))
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_job_folder)
        layout = QFormLayout(self)
        for name, label in self.labels.items():
            layout.addRow(name, label)
        layout.addRow("Folder", self.open_button)

    def set_outputs(self, outputs: dict[str, str]) -> None:
        for name, label in self.labels.items():
            label.setText(outputs.get(name, "-"))
        job_dir = outputs.get("JOB_DIR", "")
        self.job_dir = job_dir if _is_inside_outputs_jobs(job_dir) else ""
        self.open_button.setEnabled(bool(self.job_dir))

    def open_job_folder(self) -> None:
        if not self.job_dir or not _is_inside_outputs_jobs(self.job_dir):
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.job_dir))


def _is_inside_outputs_jobs(path: str) -> bool:
    if not path:
        return False
    resolved = Path(path).resolve()
    root = OUTPUT_ROOT.resolve()
    return resolved == root or root in resolved.parents
