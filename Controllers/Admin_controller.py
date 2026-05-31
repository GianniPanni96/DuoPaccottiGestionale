"""Controller per il singolo admin di sistema (uno solo)."""

from Gestionale_Enums import ADMIN_FIXED_NAME, DBAdminColumns
from Utils.Controller_utils import ControllerUtils
from Utils.Validation_utils import ValidationUtils


class AdminController:
    def __init__(self, db_model, admin_query_service):
        self.db_model = db_model
        self.admin_query_service = admin_query_service

    def save_admin(self, plain_password: str):
        """Crea il singolo admin. Returns (ok, msg, info{recovery_code})."""
        if not plain_password:
            return False, "La password e' obbligatoria.", None
        ok, _ = ValidationUtils.validate_password_strength(plain_password)
        if not ok:
            return False, "Password non valida: almeno 8 caratteri.", None
        if self.admin_query_service.admin_exists():
            return False, "Esiste gia' un amministratore di sistema.", None

        recovery_code = ControllerUtils.generate_recovery_code()
        fields = {
            DBAdminColumns.NAME.value: ADMIN_FIXED_NAME,
            DBAdminColumns.PASSWORD_LOGIN.value: ControllerUtils.hash_password(plain_password),
            DBAdminColumns.RECOVERY_HASH.value: ControllerUtils.hash_recovery_code(recovery_code),
        }
        try:
            self.db_model.add_admin(**fields)
            return True, "Amministratore creato con successo.", {"recovery_code": recovery_code}
        except Exception as exc:
            return False, f"Errore durante la creazione dell'admin: {exc}", None

    def update_admin_password(self, new_plain_password: str):
        ok, _ = ValidationUtils.validate_password_strength(new_plain_password or "")
        if not ok:
            return False, "Password non valida: almeno 8 caratteri.", None
        admin = self.admin_query_service.retrieve_admin_map()
        if not admin:
            return False, "Nessun amministratore presente.", None

        recovery_code = ControllerUtils.generate_recovery_code()
        try:
            self.db_model.update_admin(
                int(admin[DBAdminColumns.ID.value]),
                **{
                    DBAdminColumns.PASSWORD_LOGIN.value: ControllerUtils.hash_password(new_plain_password),
                    DBAdminColumns.RECOVERY_HASH.value: ControllerUtils.hash_recovery_code(recovery_code),
                },
            )
            return True, "Password admin aggiornata.", {"recovery_code": recovery_code}
        except Exception as exc:
            return False, f"Errore durante l'aggiornamento admin: {exc}", None

    def reset_password_via_recovery(self, recovery_code: str, new_password: str):
        admin = self.admin_query_service.retrieve_admin_map()
        if not admin:
            return False, "Nessun amministratore presente.", None
        stored = admin.get(DBAdminColumns.RECOVERY_HASH.value)
        if not ControllerUtils.verify_recovery_code(recovery_code, stored):
            return False, "Recovery code errato.", None
        return self.update_admin_password(new_password)
