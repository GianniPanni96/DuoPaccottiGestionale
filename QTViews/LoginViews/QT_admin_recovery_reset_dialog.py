"""Reset password admin tramite recovery code."""

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from App_context import AppContext


class QTAdminRecoveryResetDialog(QDialog):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.admin_controller = app_context.admin_controller

        self.success = False
        self.new_password = None

        self.setWindowTitle("Reimposta password admin")
        self.setModal(True)
        self.resize(440, 280)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        root.addWidget(QLabel("Reimposta la password admin con il recovery code."))

        form = QFormLayout()
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
        pwd = self.password_edit.text()
        if pwd != self.password_confirm_edit.text():
            QMessageBox.warning(self, "Validazione", "Le due password non coincidono.")
            return
        ok, msg, _ = self.admin_controller.reset_password_via_recovery(
            self.code_edit.text().strip(), pwd
        )
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return
        self.success = True
        self.new_password = pwd
        QMessageBox.information(self, "Fatto", "Password admin reimpostata.")
        self.accept()
