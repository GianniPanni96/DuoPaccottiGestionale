"""Login utente. ``mandatory=True`` (login forzato all'avvio) impedisce la
chiusura via X/ESC. Su successo pubblica LOGIN_STATUS_CHANGED."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Gestionale_Enums import DBUsersColumns
from Utils.View_utils import ViewUtils

if TYPE_CHECKING:
    from App_context import AppContext


class QTLoginDialog(QDialog):
    def __init__(self, app_context: "AppContext", parent=None, mandatory: bool = False):
        super().__init__(parent)
        self.app_context = app_context
        self.users_query_service = app_context.users_query_service
        self.user_auth_service = app_context.user_auth_service
        self.event_bus = app_context.event_bus

        self.success = False
        self.user_id = -1
        self.logged_as_admin = False
        self.exit_requested = False
        self._mandatory = mandatory

        self.setWindowTitle("Esegui il login")
        self.resize(420, 320)
        self.setModal(True)
        if mandatory:
            self.setWindowFlag(Qt.WindowCloseButtonHint, False)
            self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Scegli l'utente e inserisci la password"))

        users = self.users_query_service.retrieve_users_map_list()
        self.username_combo = QComboBox()
        self.username_combo.addItems([
            f"{u[DBUsersColumns.FIRST_NAME.value]} {u[DBUsersColumns.LAST_NAME.value]}"
            for u in users
        ])
        layout.addWidget(self.username_combo)

        layout.addWidget(QLabel("Password:"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.returnPressed.connect(self._try_login)
        layout.addWidget(self.password_edit)

        layout.addStretch(1)

        login_btn = QPushButton("Esegui il login")
        login_btn.clicked.connect(self._try_login)
        layout.addWidget(login_btn)

        forgot_btn = QPushButton("Password dimenticata?")
        forgot_btn.setFlat(True)
        forgot_btn.setStyleSheet("text-align: center; color: palette(highlight);")
        forgot_btn.clicked.connect(self._open_recovery_reset)
        layout.addWidget(forgot_btn)

        admin_btn = QPushButton("Accedi come amministratore")
        admin_btn.setFlat(True)
        admin_btn.setStyleSheet("text-align: center; color: palette(mid);")
        admin_btn.clicked.connect(self._open_admin_login)
        layout.addWidget(admin_btn)

        if self._mandatory:
            exit_btn = QPushButton("Esci dall'app")
            exit_btn.setFlat(True)
            exit_btn.setStyleSheet("text-align: center; color: palette(mid);")
            exit_btn.clicked.connect(self._exit_app)
            layout.addWidget(exit_btn)

    def keyPressEvent(self, event: QKeyEvent):
        if self._mandatory and event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def reject(self):
        if self._mandatory:
            return
        super().reject()

    def _exit_app(self):
        self.exit_requested = True
        self.done(QDialog.Rejected)

    def _open_recovery_reset(self):
        from QTViews.LoginViews.QT_recovery_reset_dialog import QTRecoveryResetDialog
        dialog = QTRecoveryResetDialog(app_context=self.app_context, parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.success:
            return
        if dialog.reset_username:
            idx = self.username_combo.findText(dialog.reset_username)
            if idx >= 0:
                self.username_combo.setCurrentIndex(idx)
        self.password_edit.setText(dialog.reset_password or "")
        self.password_edit.setFocus()

    def _open_admin_login(self):
        from QTViews.LoginViews.QT_admin_login_dialog import QTAdminLoginDialog
        admin_login = QTAdminLoginDialog(app_context=self.app_context, mandatory=False, parent=self)
        if admin_login.exec() != QDialog.Accepted or not admin_login.success:
            return
        self.logged_as_admin = True
        self.success = True
        self.accept()

    def _try_login(self):
        username = self.username_combo.currentText()
        password = self.password_edit.text()
        success, message, user_id = self.user_auth_service.check_password_for_login(username, password)
        if success:
            self.success = True
            self.user_id = user_id
            self.event_bus.publish(
                ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value,
                {"login_status": True, "logged_user_id": user_id, "is_admin": False},
            )
            self.accept()
        else:
            QMessageBox.warning(self, "Login", message)
