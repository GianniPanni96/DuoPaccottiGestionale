"""Creazione dell'amministratore di sistema (primo avvio).

Mandatory: non chiudibile con X/ESC. Dopo la creazione mostra il recovery
code una sola volta."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
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


class QTAdminCreateDialog(QDialog):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.admin_controller = app_context.admin_controller
        self._created = False
        self.exit_requested = False

        self.setWindowTitle("Crea amministratore di sistema")
        self.setModal(True)
        self.resize(480, 360)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Amministratore di sistema")
        f = title.font()
        f.setBold(True)
        f.setPointSize(16)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        info = QLabel(
            "Prima di procedere crea l'amministratore. Esiste un solo admin: "
            "potra' creare/eliminare utenti e reimpostare le loro password. "
            "L'admin NON ha accesso ai dati finanziari degli utenti."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("almeno 8 caratteri")
        form.addRow("Password admin:", self.password_edit)
        self.password_confirm_edit = QLineEdit()
        self.password_confirm_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Conferma password:", self.password_confirm_edit)
        root.addLayout(form)

        warning = QLabel(
            "Dopo la creazione ti verra' mostrato un recovery code: conservalo, "
            "e' l'unico modo per recuperare l'accesso admin."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b97a00;")
        root.addWidget(warning)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        create_btn = QPushButton("Crea amministratore")
        create_btn.setMinimumSize(180, 38)
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

    def _on_create(self):
        pwd = self.password_edit.text()
        if pwd != self.password_confirm_edit.text():
            QMessageBox.warning(self, "Validazione", "Le due password non coincidono.")
            return
        ok, msg, info = self.admin_controller.save_admin(pwd)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return
        recovery_code = (info or {}).get("recovery_code")
        if recovery_code:
            from QTViews.LoginViews.QT_recovery_code_show_dialog import QTRecoveryCodeShowDialog
            QTRecoveryCodeShowDialog(recovery_code, parent=self).exec()
        self._created = True
        self.accept()

    @property
    def created(self) -> bool:
        return self._created
