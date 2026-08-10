"""Bottom natural language input bar."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ui_desktop.services.i18n import LABELS, MESSAGES, tr_button


class NaturalLanguageInput(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Composer")

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setObjectName("PromptEdit")
        self.prompt_edit.setPlaceholderText(MESSAGES["input_placeholder"])
        self.prompt_edit.setMinimumHeight(86)
        self.prompt_edit.setMaximumHeight(132)

        self.provider_combo = QComboBox()
        self.provider_combo.setObjectName("ModeCombo")
        self.provider_combo.addItem(LABELS["local"], "local")
        self.provider_combo.addItem(LABELS["openai"], "openai")
        self.provider_combo.addItem(LABELS["rule_based"], "rule_based")
        self.provider_combo.setCurrentIndex(0)

        self.executor_combo = QComboBox()
        self.executor_combo.setObjectName("ModeCombo")
        self.executor_combo.addItem(LABELS["api_executor"], "api_executor")
        self.executor_combo.addItem(LABELS["legacy_vba"], "legacy_vba")
        self.executor_combo.setCurrentIndex(0)

        self.send_button = QPushButton(tr_button("send"))
        self.send_button.setObjectName("PrimaryButton")
        self.generate_button = self.send_button
        self.clear_button = QPushButton(tr_button("clear_input"))

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(LABELS["provider_mode"]))
        mode_row.addWidget(self.provider_combo)
        mode_row.addWidget(QLabel(LABELS["executor_mode"]))
        mode_row.addWidget(self.executor_combo)
        mode_row.addStretch(1)

        action_row = QHBoxLayout()
        action_row.addWidget(self.prompt_edit, 1)
        button_col = QVBoxLayout()
        button_col.addWidget(self.send_button)
        button_col.addWidget(self.clear_button)
        button_col.addStretch(1)
        action_row.addLayout(button_col)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addLayout(mode_row)
        layout.addLayout(action_row)

    def text(self) -> str:
        return self.prompt_edit.toPlainText()

    def provider(self) -> str:
        return str(self.provider_combo.currentData())

    def executor_mode(self) -> str:
        return str(self.executor_combo.currentData())

    def clear(self) -> None:
        self.prompt_edit.clear()
