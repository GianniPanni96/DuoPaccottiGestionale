"""Autenticazione utenti e admin.

Verifica la password (hash PBKDF2) e, in caso di successo, imposta lo
stato in ``SessionContext``. Privacy con Opzione A: nessuna crypto
session da sbloccare (i dati non sono cifrati at-rest)."""

from Gestionale_Enums import DBAdminColumns, DBUsersColumns
from Utils.Controller_utils import ControllerUtils


class UserAuthService:
    def __init__(self, users_query_service, db_model, admin_query_service, session_context):
        self.users_query_service = users_query_service
        self.db_model = db_model
        self.admin_query_service = admin_query_service
        self.session_context = session_context

    @property
    def is_admin(self) -> bool:
        return self.session_context.is_admin

    def check_password_for_login(self, username: str, password: str):
        """Returns (success, message, user_id)."""
        user = self.users_query_service.retrieve_user_map_by_extended_name(username)
        if not user:
            return False, "Utente selezionato non trovato.", -1

        db_hash = user.get(DBUsersColumns.PASSWORD_LOGIN.value)
        if not db_hash:
            return False, (
                "L'utente selezionato non ha una password di login.\n"
                "Chiedi all'amministratore di impostarne una."
            ), -1

        if not ControllerUtils.verify_password(password, db_hash):
            return False, "Password errata!", -1

        user_id = int(user[DBUsersColumns.ID.value])
        self.session_context.set_user(user_id)
        return True, "Login effettuato.", user_id

    def check_admin_password_for_login(self, password: str):
        """Returns (success, message)."""
        admin = self.admin_query_service.retrieve_admin_map()
        if not admin:
            return False, "Nessun amministratore presente nel sistema."
        db_hash = admin.get(DBAdminColumns.PASSWORD_LOGIN.value)
        if not db_hash:
            return False, "L'amministratore non ha una password impostata."
        if not ControllerUtils.verify_password(password, db_hash):
            return False, "Password admin errata."
        self.session_context.set_admin()
        return True, "Login admin effettuato."

    def logout(self) -> None:
        self.session_context.clear()
