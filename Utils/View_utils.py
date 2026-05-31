"""Utility condivise lato view, neutre rispetto al framework UI.

``ViewUtils.EventBusKeys`` enumera le chiavi degli eventi pubblicati
sull'event bus dell'app (login/logout, richieste di apertura dettaglio
cross-tab). Nessuna dipendenza da PySide6: importabile ovunque.
"""

from enum import Enum


class ViewUtils:

    class EventBusKeys(Enum):
        LOGIN_STATUS_CHANGED = "LOGIN_STATUS_CHANGED"
        SHOW_EXPENSE_DETAIL = "SHOW_EXPENSE_DETAIL"
        SHOW_INCOME_DETAIL = "SHOW_INCOME_DETAIL"
        SHOW_USER_DETAIL = "SHOW_USER_DETAIL"
        DATA_CHANGED = "DATA_CHANGED"

    @staticmethod
    def split_string_by_length(text: str, max_length: int) -> str:
        """Inserisce un newline vicino alla meta' di ``text`` (solo tra
        parole) se eccede ``max_length``."""
        if len(text) <= max_length:
            return text

        words = text.split()
        current_length = 0
        split_index = -1
        for i, word in enumerate(words):
            current_length += len(word) + 1
            if current_length >= max_length // 2:
                split_index = i
                break

        if split_index == -1 or split_index == len(words) - 1:
            return text

        return " ".join(words[: split_index + 1]) + "\n" + " ".join(words[split_index + 1:])
