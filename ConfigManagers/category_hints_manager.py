from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import CATEGORY_HINTS_DEFAULT


class CategoryHintsManager(BaseJsonConfigManager):
    """Mapping parola-chiave -> chiave categoria, usato dai parser PDF per
    dedurre la categoria di un movimento dalla descrizione/esercente."""

    file_name = "category_hints.json"
    default_data = CATEGORY_HINTS_DEFAULT

    def get_expense_hints(self) -> dict:
        return self.load().get("expense_hints", {})

    def suggest_category(self, text: str, fallback: str = "ALTRO") -> str:
        """Restituisce la chiave categoria suggerita cercando una parola
        chiave (case-insensitive) dentro ``text``."""
        if not text:
            return fallback
        lowered = text.lower()
        for keyword, category_key in self.get_expense_hints().items():
            if keyword.lower() in lowered:
                return category_key
        return fallback
