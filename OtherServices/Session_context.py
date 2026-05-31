"""Stato della sessione corrente: chi e' loggato (utente o admin).

Fonte di verita' consultata dal ``VisibilityService`` per filtrare i dati
in base a chi sta guardando. Sessioni mutuamente esclusive: o un utente o
l'admin."""


class SessionContext:
    def __init__(self):
        self.current_user_id: int = -1
        self.is_admin: bool = False

    @property
    def is_logged_in(self) -> bool:
        return self.is_admin or self.current_user_id != -1

    def set_user(self, user_id: int) -> None:
        self.current_user_id = int(user_id)
        self.is_admin = False

    def set_admin(self) -> None:
        self.current_user_id = -1
        self.is_admin = True

    def clear(self) -> None:
        self.current_user_id = -1
        self.is_admin = False
