"""Onboarding al primo avvio: crea il primo utente con password.

Si attiva quando il DB non contiene utenti. Mandatory: senza un utente
l'app non puo' funzionare."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
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

from Gestionale_Enums import DBUsersColumns, Visibility
from Utils.Validation_utils import ValidationUtils

if TYPE_CHECKING:
    from App_context import AppContext


class QTOnboardingDialog(QDialog):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.user_controller = app_context.user_controller
        self.users_query_service = app_context.users_query_service

        self.created_user_id: int | None = None
        self.created_user_name: str | None = None
        self.created_user_password: str | None = None
        self.exit_requested = False

        self.setWindowTitle("Configurazione iniziale - DuoPaccotti")
        self.setModal(True)
        self.resize(520, 560)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Benvenuto in DuoPaccotti")
        f = title.font()
        f.setBold(True)
        f.setPointSize(15)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("Crea il primo utente con una password di accesso.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: palette(mid);")
        root.addWidget(subtitle)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        self.collective_name_edit = QLineEdit()
        self.collective_name_edit.setText(self.app_context.app_settings_manager.get_collective_name())
        form.addRow("Nome del nucleo:", self.collective_name_edit)

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
        form.addRow("Visibilita' predefinita:", self.visibility_combo)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("almeno 8 caratteri")
        form.addRow("Password di login:", self.password_edit)
        self.password_confirm_edit = QLineEdit()
        self.password_confirm_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Conferma password:", self.password_confirm_edit)

        root.addLayout(form)

        warning = QLabel(
            "Conserva la password. Dopo la creazione ti verra' mostrato un "
            "recovery code per reimpostarla in caso di smarrimento."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b97a00;")
        root.addWidget(warning)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        create_btn = QPushButton("Crea e accedi")
        create_btn.setMinimumSize(160, 38)
        create_btn.clicked.connect(self._on_create)
        buttons.addWidget(create_btn)
        buttons.addStretch(1)
        root.addLayout(buttons)

        exit_btn = QPushButton("Esci dall'app")
        exit_btn.setFlat(True)
        exit_btn.setStyleSheet("text-align: center; color: palette(mid);")
        exit_btn.clicked.connect(self._exit_app)
        root.addWidget(exit_btn)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def reject(self):
        return

    def _exit_app(self):
        self.exit_requested = True
        self.done(QDialog.Rejected)

    def _validate(self) -> bool:
        if not self.first_name_edit.text().strip():
            QMessageBox.warning(self, "Validazione", "Il nome e' obbligatorio.")
            return False
        if not self.last_name_edit.text().strip():
            QMessageBox.warning(self, "Validazione", "Il cognome e' obbligatorio.")
            return False
        email = self.email_edit.text().strip()
        if email and not ValidationUtils.validate_email(email):
            QMessageBox.warning(self, "Validazione", "Email non valida.")
            return False
        pwd = self.password_edit.text()
        if pwd != self.password_confirm_edit.text():
            QMessageBox.warning(self, "Validazione", "Le due password non coincidono.")
            return False
        ok, _ = ValidationUtils.validate_password_strength(pwd)
        if not ok:
            QMessageBox.warning(self, "Validazione", "Password troppo debole (minimo 8 caratteri).")
            return False
        return True

    def _on_create(self):
        if not self._validate():
            return

        try:
            name = self.collective_name_edit.text().strip() or "DuoPaccotti"
            self.app_context.app_settings_manager.set_collective_name(name)
        except Exception as exc:
            print(f"[onboarding] errore salvataggio nome nucleo: {exc}")

        first = self.first_name_edit.text().strip()
        last = self.last_name_edit.text().strip()
        password = self.password_edit.text()

        user_data = {
            DBUsersColumns.FIRST_NAME.value: first,
            DBUsersColumns.LAST_NAME.value: last,
            DBUsersColumns.EMAIL.value: self.email_edit.text().strip(),
            DBUsersColumns.TELEFONO.value: self.telefono_edit.text().strip(),
            DBUsersColumns.DEFAULT_VISIBILITY.value: self.visibility_combo.currentText(),
            "_plain_password": password,
        }
        ok, msg, info = self.user_controller.save_user(user_data)
        if not ok:
            QMessageBox.critical(self, "Errore creazione utente", msg)
            return

        recovery_code = (info or {}).get("recovery_code")
        if recovery_code:
            from QTViews.LoginViews.QT_recovery_code_show_dialog import QTRecoveryCodeShowDialog
            QTRecoveryCodeShowDialog(recovery_code, parent=self).exec()

        self.created_user_id = (info or {}).get("user_id")
        self.created_user_name = f"{first} {last}"
        self.created_user_password = password
        self.accept()
