"""Entry-point UI (PySide6).

Bootstrap (config + schema + AppContext), poi autenticazione obbligatoria
prima di mostrare la finestra principale:
1. se non esiste l'admin -> dialog di creazione admin;
2. se non esistono utenti -> onboarding (crea il primo utente);
3. altrimenti -> login utente obbligatorio (con opzione admin).
"""

import sys

# Patch difensiva per shibokensupport sotto debugger PyCharm (come Willow):
# rende resiliente l'hook che ispeziona i moduli importati.
try:
    import shibokensupport.feature as _sbk_feature  # type: ignore[import]
    _orig_mod_uses = _sbk_feature._mod_uses_pyside

    def _safe_mod_uses_pyside(mod):  # noqa: ANN001,ANN201
        try:
            return _orig_mod_uses(mod)
        except (TypeError, AttributeError, OSError):
            return False

    _sbk_feature._mod_uses_pyside = _safe_mod_uses_pyside
except (ImportError, AttributeError):
    pass

from Main_bootstrap import build_app_context


def _ensure_admin_exists(app_context) -> bool:
    if app_context.admin_query_service.admin_exists():
        return True
    from PySide6.QtWidgets import QMessageBox
    from QTViews.LoginViews.QT_admin_create_dialog import QTAdminCreateDialog

    dialog = QTAdminCreateDialog(app_context=app_context)
    if dialog.exec() != QTAdminCreateDialog.Accepted or not dialog.created:
        if not dialog.exit_requested:
            QMessageBox.critical(None, "Avvio interrotto", "Creazione amministratore annullata.")
        return False
    return True


def _force_authentication(app_context):
    """Returns (success, user_id, is_admin). success=False -> esci."""
    from PySide6.QtWidgets import QMessageBox
    from QTViews.LoginViews.QT_admin_login_dialog import QTAdminLoginDialog
    from QTViews.LoginViews.QT_login_dialog import QTLoginDialog
    from QTViews.LoginViews.QT_onboarding_dialog import QTOnboardingDialog

    users = app_context.users_query_service.retrieve_users_map_list()

    if not users:
        onboarding = QTOnboardingDialog(app_context=app_context)
        if onboarding.exec() != QTOnboardingDialog.Accepted or onboarding.created_user_id is None:
            if not onboarding.exit_requested:
                QMessageBox.critical(None, "Avvio interrotto", "Configurazione iniziale annullata.")
            return False, -1, False
        ok, _msg, user_id = app_context.user_auth_service.check_password_for_login(
            onboarding.created_user_name, onboarding.created_user_password
        )
        if not ok:
            QMessageBox.critical(None, "Errore", "Impossibile autenticare il nuovo utente.")
            return False, -1, False
        return True, user_id, False

    login = QTLoginDialog(app_context=app_context, mandatory=True)
    if login.exec() != QTLoginDialog.Accepted or not login.success:
        if not login.exit_requested:
            QMessageBox.critical(None, "Avvio interrotto", "Login obbligatorio non completato.")
        return False, -1, False

    if login.logged_as_admin:
        return True, -1, True
    return True, login.user_id, False


def main():
    app_context = build_app_context()

    from PySide6.QtWidgets import QApplication

    from QTViews.QT_main_view import QTMainWindow
    from QTViews.QT_palette_Manager import QTPaletteManager

    qt_app = QApplication.instance() or QApplication(sys.argv)
    _f = qt_app.font()
    _f.setPointSize(_f.pointSize() + 2)
    qt_app.setFont(_f)
    QTPaletteManager.install(qt_app)

    if not _ensure_admin_exists(app_context):
        sys.exit(1)

    ok, user_id, is_admin = _force_authentication(app_context)
    if not ok:
        sys.exit(1)

    window = QTMainWindow(app_context=app_context)
    window.apply_session_state(True, user_id, is_admin)
    window.show()

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
