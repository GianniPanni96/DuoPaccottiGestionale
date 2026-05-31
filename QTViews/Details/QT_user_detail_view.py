"""Dettaglio utente: modifica profilo, cambio password, eliminazione
(solo admin)."""

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import DBUsersColumns, UserStatus, Visibility
from Utils.Validation_utils import ValidationUtils

if TYPE_CHECKING:
    from App_context import AppContext


class QTUserDetailView(QWidget):
    def __init__(self, app_context: "AppContext", user_id: int, on_back=None, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.user_id = user_id
        self.on_back = on_back
        self.user_controller = app_context.user_controller
        self.session_context = app_context.session_context

        self.user = app_context.users_query_service.retrieve_user_map_by_id(user_id)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        self.back_button = QPushButton("← Torna agli utenti")
        self.back_button.clicked.connect(lambda: self.on_back() if self.on_back else None)
        header.addWidget(self.back_button)
        header.addStretch(1)
        if self.session_context.is_admin:
            delete_btn = QPushButton("Elimina utente")
            delete_btn.clicked.connect(self._delete)
            header.addWidget(delete_btn)
        root.addLayout(header)

        if not self.user:
            root.addWidget(QLabel("Utente non trovato."))
            return

        form = QFormLayout()
        self.first_name_edit = QLineEdit(self.user.get(DBUsersColumns.FIRST_NAME.value, ""))
        form.addRow("Nome:", self.first_name_edit)
        self.last_name_edit = QLineEdit(self.user.get(DBUsersColumns.LAST_NAME.value, ""))
        form.addRow("Cognome:", self.last_name_edit)
        self.email_edit = QLineEdit(self.user.get(DBUsersColumns.EMAIL.value) or "")
        form.addRow("Email:", self.email_edit)
        self.telefono_edit = QLineEdit(self.user.get(DBUsersColumns.TELEFONO.value) or "")
        form.addRow("Telefono:", self.telefono_edit)

        self.visibility_combo = QComboBox()
        self.visibility_combo.addItems([v.value for v in Visibility])
        if self.user.get(DBUsersColumns.DEFAULT_VISIBILITY.value):
            self.visibility_combo.setCurrentText(self.user[DBUsersColumns.DEFAULT_VISIBILITY.value])
        form.addRow("Visibilità predefinita:", self.visibility_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems([s.value for s in UserStatus])
        if self.user.get(DBUsersColumns.STATUS.value):
            self.status_combo.setCurrentText(self.user[DBUsersColumns.STATUS.value])
        form.addRow("Stato:", self.status_combo)
        root.addLayout(form)

        save_btn = QPushButton("Salva modifiche")
        save_btn.clicked.connect(self._save)
        root.addWidget(save_btn)

        # Cambio password
        pwd_title = QLabel("Cambia password")
        f = pwd_title.font()
        f.setBold(True)
        pwd_title.setFont(f)
        pwd_title.setStyleSheet("margin-top: 10px;")
        root.addWidget(pwd_title)

        pwd_form = QFormLayout()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        pwd_form.addRow("Nuova password:", self.password_edit)
        self.password_confirm_edit = QLineEdit()
        self.password_confirm_edit.setEchoMode(QLineEdit.Password)
        pwd_form.addRow("Conferma password:", self.password_confirm_edit)
        root.addLayout(pwd_form)

        pwd_btn = QPushButton("Imposta nuova password")
        pwd_btn.clicked.connect(self._change_password)
        root.addWidget(pwd_btn)
        root.addStretch(1)

    def _save(self):
        first = self.first_name_edit.text().strip()
        last = self.last_name_edit.text().strip()
        if not first or not last:
            QMessageBox.warning(self, "Validazione", "Nome e cognome sono obbligatori.")
            return
        email = self.email_edit.text().strip()
        if email and not ValidationUtils.validate_email(email):
            QMessageBox.warning(self, "Validazione", "Email non valida.")
            return

        updates = {
            DBUsersColumns.FIRST_NAME.value: first,
            DBUsersColumns.LAST_NAME.value: last,
            DBUsersColumns.EMAIL.value: email,
            DBUsersColumns.TELEFONO.value: self.telefono_edit.text().strip(),
            DBUsersColumns.DEFAULT_VISIBILITY.value: self.visibility_combo.currentText(),
            DBUsersColumns.STATUS.value: self.status_combo.currentText(),
        }
        ok, msg = self.user_controller.update_user(self.user_id, updates)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return
        QMessageBox.information(self, "Salvato", "Profilo aggiornato.")

    def _change_password(self):
        pwd = self.password_edit.text()
        if pwd != self.password_confirm_edit.text():
            QMessageBox.warning(self, "Validazione", "Le due password non coincidono.")
            return
        ok, msg, info = self.user_controller.set_password(self.user_id, pwd)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return
        recovery_code = (info or {}).get("recovery_code")
        if recovery_code:
            from QTViews.LoginViews.QT_recovery_code_show_dialog import QTRecoveryCodeShowDialog
            QTRecoveryCodeShowDialog(recovery_code, parent=self).exec()
        self.password_edit.clear()
        self.password_confirm_edit.clear()
        QMessageBox.information(self, "Fatto", "Password aggiornata.")

    def _delete(self):
        confirm = QMessageBox.question(
            self, "Elimina", "Eliminare questo utente?", QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        ok, msg = self.user_controller.delete_user(self.user_id)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return
        if self.on_back:
            self.on_back()
