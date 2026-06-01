"""Controller del dominio entrate (semplice: niente condivisione)."""

from Event_bus import DATA_CHANGED
from Gestionale_Enums import DBIncomesColumns, IncomeSource


class IncomeController:
    REQUIRED_FIELDS = (
        DBIncomesColumns.DESCRIPTION.value,
        DBIncomesColumns.USER_ID.value,
        DBIncomesColumns.CATEGORY.value,
        DBIncomesColumns.AMOUNT.value,
        DBIncomesColumns.DATE.value,
    )

    def __init__(self, db_model, app_settings_manager, event_bus=None):
        self.db_model = db_model
        self.app_settings_manager = app_settings_manager
        self.event_bus = event_bus

    def _notify(self):
        if self.event_bus is not None:
            self.event_bus.publish(DATA_CHANGED, {"domain": "incomes"})

    def save_income(self, income_data: dict):
        """Returns (ok, msg, income_id)."""
        for field in self.REQUIRED_FIELDS:
            if income_data.get(field) in (None, ""):
                return False, f"Campo obbligatorio mancante: {field}.", None

        try:
            amount = float(income_data[DBIncomesColumns.AMOUNT.value])
        except (TypeError, ValueError):
            return False, "Importo non valido.", None
        if amount < 0:
            return False, "L'importo non puo' essere negativo.", None

        record = {
            DBIncomesColumns.DESCRIPTION.value: income_data[DBIncomesColumns.DESCRIPTION.value],
            DBIncomesColumns.USER_ID.value: int(income_data[DBIncomesColumns.USER_ID.value]),
            DBIncomesColumns.CATEGORY.value: income_data[DBIncomesColumns.CATEGORY.value],
            DBIncomesColumns.AMOUNT.value: amount,
            DBIncomesColumns.DATE.value: income_data[DBIncomesColumns.DATE.value],
            DBIncomesColumns.VISIBILITY.value: income_data.get(DBIncomesColumns.VISIBILITY.value)
            or self.app_settings_manager.get_default_visibility(),
            DBIncomesColumns.SOURCE.value: income_data.get(DBIncomesColumns.SOURCE.value)
            or IncomeSource.MANUALE.value,
            DBIncomesColumns.NOTE.value: income_data.get(DBIncomesColumns.NOTE.value) or "",
        }

        try:
            income_id = self.db_model.add_income(**record)
            self._notify()
            return True, "Entrata salvata con successo!", income_id
        except Exception as exc:
            return False, f"Errore durante il salvataggio: {exc}", None

    def save_parsed_incomes(self, incomes_data: list):
        n_ok = 0
        errors = []
        for data in incomes_data:
            ok, msg, _ = self.save_income(data)
            if ok:
                n_ok += 1
            else:
                errors.append(msg)
        return n_ok, errors

    def update_income(self, income_id: int, updates: dict):
        try:
            self.db_model.update_income(income_id, **updates)
            self._notify()
            return True, "Entrata aggiornata."
        except Exception as exc:
            return False, f"Errore durante l'aggiornamento: {exc}"

    def delete_income(self, income_id: int):
        try:
            self.db_model.remove_income(income_id)
            self._notify()
            return True, "Entrata eliminata."
        except Exception as exc:
            return False, f"Errore durante l'eliminazione: {exc}"
