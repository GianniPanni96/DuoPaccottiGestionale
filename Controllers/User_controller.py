"""Controller del dominio utenti: CRUD, password, recovery, visibilita'.

``user_data`` accetta la chiave speciale ``_plain_password`` (password in
chiaro da hashare): non e' una colonna del DB, viene rimossa prima
dell'insert.
"""

from datetime import datetime

from Event_bus import DATA_CHANGED
from Gestionale_Enums import DBUsersColumns, UserStatus, Visibility
from Utils.Controller_utils import ControllerUtils
from Utils.Validation_utils import ValidationUtils


class UserController:
    def __init__(self, db_model, users_query_service, event_bus=None):
        self.db_model = db_model
        self.users_query_service = users_query_service
        self.event_bus = event_bus

    def _notify(self):
        if self.event_bus is not None:
            self.event_bus.publish(DATA_CHANGED, {"domain": "users"})

    def save_user(self, user_data: dict):
        """Crea un utente. Returns (ok, msg, info{recovery_code?})."""
        first = (user_data.get(DBUsersColumns.FIRST_NAME.value) or "").strip()
        last = (user_data.get(DBUsersColumns.LAST_NAME.value) or "").strip()
        if not first or not last:
            return False, "Nome e cognome sono obbligatori.", None

        if self.users_query_service.retrieve_user_map_by_fullname(first, last):
            return False, f"Esiste gia' un utente '{first} {last}'.", None

        email = (user_data.get(DBUsersColumns.EMAIL.value) or "").strip()
        if email and not ValidationUtils.validate_email(email):
            return False, "Email non valida.", None

        record = {
            DBUsersColumns.FIRST_NAME.value: first,
            DBUsersColumns.LAST_NAME.value: last,
            DBUsersColumns.EMAIL.value: email,
            DBUsersColumns.TELEFONO.value: (user_data.get(DBUsersColumns.TELEFONO.value) or "").strip(),
            DBUsersColumns.PHOTO_PATH.value: user_data.get(DBUsersColumns.PHOTO_PATH.value) or "",
            DBUsersColumns.DEFAULT_VISIBILITY.value: user_data.get(
                DBUsersColumns.DEFAULT_VISIBILITY.value, Visibility.PUBBLICA.value
            ),
            DBUsersColumns.STATUS.value: user_data.get(
                DBUsersColumns.STATUS.value, UserStatus.ATTIVO.value
            ),
        }

        info = {}
        plain_password = user_data.get("_plain_password")
        if plain_password:
            ok, _ = ValidationUtils.validate_password_strength(plain_password)
            if not ok:
                return False, "Password non valida: almeno 8 caratteri.", None
            recovery_code = ControllerUtils.generate_recovery_code()
            record[DBUsersColumns.PASSWORD_LOGIN.value] = ControllerUtils.hash_password(plain_password)
            record[DBUsersColumns.RECOVERY_HASH.value] = ControllerUtils.hash_recovery_code(recovery_code)
            info["recovery_code"] = recovery_code

        try:
            user_id = self.db_model.add_user(**record)
            self._notify()
            return True, "Utente creato con successo.", {**info, "user_id": user_id}
        except Exception as exc:
            return False, f"Errore durante la creazione dell'utente: {exc}", None

    def update_user(self, user_id: int, updates: dict):
        try:
            updates = dict(updates)
            updates[DBUsersColumns.UPDATED_AT.value] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.db_model.update_user(user_id, **updates)
            self._notify()
            return True, "Utente aggiornato."
        except Exception as exc:
            return False, f"Errore durante l'aggiornamento: {exc}"

    def delete_user(self, user_id: int):
        try:
            self.db_model.remove_user(user_id)
            self._notify()
            return True, "Utente eliminato."
        except Exception as exc:
            return False, f"Errore durante l'eliminazione: {exc}"

    def set_password(self, user_id: int, new_plain_password: str):
        """Imposta/cambia la password di un utente. Returns (ok, msg, info)."""
        ok, _ = ValidationUtils.validate_password_strength(new_plain_password or "")
        if not ok:
            return False, "Password non valida: almeno 8 caratteri.", None
        recovery_code = ControllerUtils.generate_recovery_code()
        try:
            self.db_model.update_user(
                user_id,
                **{
                    DBUsersColumns.PASSWORD_LOGIN.value: ControllerUtils.hash_password(new_plain_password),
                    DBUsersColumns.RECOVERY_HASH.value: ControllerUtils.hash_recovery_code(recovery_code),
                },
            )
            return True, "Password impostata.", {"recovery_code": recovery_code}
        except Exception as exc:
            return False, f"Errore durante l'impostazione della password: {exc}", None

    def reset_password_via_recovery(self, user_id: int, recovery_code: str, new_password: str):
        user = self.users_query_service.retrieve_user_map_by_id(user_id)
        if not user:
            return False, "Utente non trovato.", None
        stored = user.get(DBUsersColumns.RECOVERY_HASH.value)
        if not ControllerUtils.verify_recovery_code(recovery_code, stored):
            return False, "Recovery code errato.", None
        return self.set_password(user_id, new_password)

    def set_default_visibility(self, user_id: int, visibility: str):
        return self.update_user(user_id, {DBUsersColumns.DEFAULT_VISIBILITY.value: visibility})
