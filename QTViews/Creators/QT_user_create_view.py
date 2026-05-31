"""Dialog di creazione di un nuovo utente (dalla tab Utenti).

Richiede una password (cosi' il nuovo utente puo' accedere); mostra il
recovery code generato una sola volta."""

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Gestionale_Enums import DBUsersColumns, Visibility
from Utils.Validation_utils import ValidationUtils

if TYPE_CHECKING:
    from App_context import AppContext


class QTUserCreateView(QDialog):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.user_controller = app_context.user_controller
        self.created_user_id = None

        self.setWindowTitle("Aggiungi utente")
        self.setModal(True)
        self.resize(460, 420)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        form = QFormLayout()
        form.setSpacing(8)
        root.addLayout(form)

        self.first_name_edit = QLineEdit()
        form.addRow("Nome:", self.first_name_edit)
        self.last_name_edit = QLineEdit()
        form.addRow("Cognome:", self.last_name_edit)
        self.email_edit = QLineEdit()
        form.addRow("Email (opzionale):", self.email_edit)
        self.telefono_edit = QLineEdit()
        form.addRow("Telefono (opzionale):", self.telefono_edit)

        self.visibility_combo = QComboBox()
        self.visibility_combo.addItems([v.value for v in Visibility])
        form.addRow("Visibilità predefinita:", self.visibility_combo)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("almeno 8 caratteri")
        form.addRow("Password:", self.password_edit)
        self.password_confirm_edit = QLineEdit()
        self.password_confirm_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Conferma password:", self.password_confirm_edit)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        save_btn = QPushButton("Crea utente")
        save_btn.setMinimumSize(140, 38)
        save_btn.clicked.connect(self._save)
        bottom.addWidget(save_btn)
        bottom.addStretch(1)
        root.addLayout(bottom)

    def _save(self):
        pwd = self.password_edit.text()
        if pwd != self.password_confirm_edit.text():
            QMessageBox.warning(self, "Validazione", "Le due password non coincidono.")
            return
        ok_pwd, _ = ValidationUtils.validate_password_strength(pwd)
        if not ok_pwd:
            QMessageBox.warning(self, "Validazione", "Password troppo debole (minimo 8 caratteri).")
            return

        user_data = {
            DBUsersColumns.FIRST_NAME.value: self.first_name_edit.text().strip(),
            DBUsersColumns.LAST_NAME.value: self.last_name_edit.text().strip(),
            DBUsersColumns.EMAIL.value: self.email_edit.text().strip(),
            DBUsersColumns.TELEFONO.value: self.telefono_edit.text().strip(),
            DBUsersColumns.DEFAULT_VISIBILITY.value: self.visibility_combo.currentText(),
            "_plain_password": pwd,
        }
        ok, msg, info = self.user_controller.save_user(user_data)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return

        recovery_code = (info or {}).get("recovery_code")
        if recovery_code:
            from QTViews.LoginViews.QT_recovery_code_show_dialog import QTRecoveryCodeShowDialog
            QTRecoveryCodeShowDialog(recovery_code, parent=self).exec()

        self.created_user_id = (info or {}).get("user_id")
        self.accept()
