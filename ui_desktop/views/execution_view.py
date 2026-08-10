"""Conversation-style execution feedback and controls."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui_desktop.services.i18n import MESSAGES, SECTIONS, tr_button
from ui_desktop.widgets.execution_log_panel import ExecutionLogPanel


class ExecutionView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ConversationPanel")

        title = QLabel(SECTIONS["feedback"])
        title.setObjectName("PanelTitle")
        subtitle = QLabel(MESSAGES["welcome"])
        subtitle.setObjectName("PanelSubtitle")
        subtitle.setWordWrap(True)

        self.log_panel = ExecutionLogPanel()
        self.log_panel.setObjectName("ConversationLog")
        self.log_panel.append_log("[系统] " + MESSAGES["welcome"])

        # Internal action hooks. The new task page auto-advances through
        # validation and dry_run, so these buttons are not shown to users.
        self.validate_button = QPushButton(tr_button("validate"))
        self.dry_run_button = QPushButton(tr_button("dry_run"))
        self.real_run_button = QPushButton(tr_button("real_run"))
        self.validate_button.hide()
        self.dry_run_button.hide()
        self.real_run_button.hide()

        self.cancel_button = QPushButton(tr_button("cancel"))
        self.cancel_button.setObjectName("ActionButton")

        self.confirm_panel = QWidget()
        self.confirm_panel.setObjectName("ConfirmPanel")
        confirm_label = QLabel(MESSAGES["real_run_confirmation"])
        confirm_label.setObjectName("ConfirmPrompt")
        confirm_label.setWordWrap(True)
        self.confirm_button = QPushButton("确认执行")
        self.confirm_button.setObjectName("PrimaryButton")
        self.regenerate_button = QPushButton(tr_button("regenerate"))
        self.regenerate_button.setObjectName("ActionButton")

        confirm_row = QHBoxLayout(self.confirm_panel)
        confirm_row.setContentsMargins(12, 10, 12, 10)
        confirm_row.addWidget(confirm_label, 1)
        confirm_row.addWidget(self.confirm_button)
        confirm_row.addWidget(self.regenerate_button)
        self.confirm_panel.hide()

        action_row = QHBoxLayout()
        action_row.addWidget(self.cancel_button)
        action_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.log_panel, 1)
        layout.addWidget(self.confirm_panel)
        layout.addLayout(action_row)

    def show_real_run_confirmation(self, visible: bool = True) -> None:
        self.confirm_panel.setVisible(visible)
