"""Reset password utente tramite recovery code."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Gestionale_Enums import DBUsersColumns

if TYPE_CHECKING:
    from App_context import AppContext


class QTRecoveryResetDialog(QDialog):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.users_query_service = app_context.users_query_service
        self.user_controller = app_context.user_controller

        self.success = False
        self.reset_username = None
        self.reset_password = None

        self.setWindowTitle("Reimposta password")
        self.setModal(True)
        self.resize(440, 320)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        root.addWidget(QLabel("Reimposta la password con il recovery code."))

        form = QFormLayout()
        self._users = self.users_query_service.retrieve_users_map_list()
        self.user_combo = QComboBox()
        self.user_combo.addItems([
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in self._users
        ])
        form.addRow("Utente:", self.user_combo)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        form.addRow("Recovery code:", self.code_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Nuova password:", self.password_edit)
        self.password_confirm_edit = QLineEdit()
        self.password_confirm_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Conferma password:", self.password_confirm_edit)
        root.addLayout(form)

        root.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        reset_btn = QPushButton("Reimposta password")
        reset_btn.clicked.connect(self._on_reset)
        buttons.addWidget(reset_btn)
        root.addLayout(buttons)

    def _on_reset(self):
        idx = self.user_combo.currentIndex()
        if idx < 0 or idx >= len(self._users):
            QMessageBox.warning(self, "Errore", "Seleziona un utente.")
            return
        user = self._users[idx]
        pwd = self.password_edit.text()
        if pwd != self.password_confirm_edit.text():
            QMessageBox.warning(self, "Validazione", "Le due password non coincidono.")
            return

        ok, msg, _ = self.user_controller.reset_password_via_recovery(
            int(user[DBUsersColumns.ID.value]), self.code_edit.text().strip(), pwd
        )
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return

        self.success = True
        self.reset_username = self.user_combo.currentText()
        self.reset_password = pwd
        QMessageBox.information(self, "Fatto", "Password reimpostata con successo.")
        self.accept()
