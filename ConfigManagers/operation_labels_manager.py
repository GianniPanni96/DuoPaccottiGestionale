"""Mappa operazione-PDF → {category, description} per il parser dell'estratto conto.

Quando una spesa viene salvata dal dialog di preview, la voce viene registrata
qui (chiave = testo OPERAZIONE grezzo dal PDF). Al prossimo parsing la stessa
operazione riceve automaticamente la categoria e la descrizione già usate
dall'utente in precedenza.
"""

import json

from ConfigManagers.base_json_manager import BaseJsonConfigManager


_SECTION = "expense_operations"
_DEFAULT: dict = {_SECTION: {}}


class OperationLabelsManager(BaseJsonConfigManager):
    file_name = "operation_labels.json"
    default_data = _DEFAULT

    # Senza merge: le voci salvate sono verità assoluta, nessun default
    # da sovrapporre.
    def load(self) -> dict:
        self.ensure_exists()
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, data: dict) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------

    def get_entry(self, operation: str) -> dict | None:
        """Restituisce {category, description} per l'operazione, o None."""
        if not operation:
            return None
        return self.load().get(_SECTION, {}).get(operation)

    def set_entry(self, operation: str, category: str, description: str) -> None:
        """Salva/aggiorna la voce per l'operazione data."""
        if not operation:
            return
        data = self.load()
        data.setdefault(_SECTION, {})[operation] = {
            "category": category,
            "description": description,
        }
        self.save(data)
