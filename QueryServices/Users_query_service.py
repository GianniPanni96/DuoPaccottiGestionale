from Gestionale_Enums import DBUsersColumns
from Utils.Controller_utils import ControllerUtils


class UsersQueryService:
    """Letture del dominio utenti."""

    def __init__(self, db_model):
        self.db_model = db_model

    def retrieve_users_map_list(self):
        rows = self.db_model.fetch_users()
        return [ControllerUtils.row_to_map(r, DBUsersColumns) for r in rows]

    def retrieve_user_map_by_id(self, user_id):
        return ControllerUtils.row_to_map(self.db_model.fetch_user_by_id(user_id), DBUsersColumns)

    def retrieve_user_by_fullname(self, first_name, last_name):
        """Riga grezza (tupla)."""
        return self.db_model.fetch_user_by_fullname(first_name, last_name)

    def retrieve_user_map_by_fullname(self, first_name, last_name):
        return ControllerUtils.row_to_map(
            self.db_model.fetch_user_by_fullname(first_name, last_name), DBUsersColumns
        )

    def retrieve_user_map_by_extended_name(self, full_name):
        """Trova l'utente il cui 'Nome Cognome' coincide con ``full_name``.
        Robusto a nomi/cognomi composti (match sulla lista, non split)."""
        if not full_name:
            return None
        target = full_name.strip()
        for user in self.retrieve_users_map_list():
            composed = (
                f"{user[DBUsersColumns.FIRST_NAME.value]} "
                f"{user[DBUsersColumns.LAST_NAME.value]}"
            )
            if composed == target:
                return user
        return None

    def user_exists(self) -> bool:
        return self.db_model.count_users() > 0
