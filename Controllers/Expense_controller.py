"""Controller del dominio spese: validazione, scorporo IVA, creazione
quote di condivisione, salvataggio singolo e batch (dai parser PDF).

``expense_data`` usa i nomi colonna del DB piu' alcune chiavi speciali
(prefisso ``_``) non persistite:
- ``_iva_rate``: aliquota per scorporare netto/IVA (default da app_settings);
- ``_shares``: dict {user_id: percentuale 0..1} per le quote condivise;
- ``_participants``: lista user_id per quote eque (alternativa a _shares).
"""

from Gestionale_Enums import (
    DBExpensesColumns,
    ExpenseSource,
    Visibility,
)


class ExpenseController:
    REQUIRED_FIELDS = (
        DBExpensesColumns.DESCRIPTION.value,
        DBExpensesColumns.USER_ID.value,
        DBExpensesColumns.CATEGORY.value,
        DBExpensesColumns.TOTAL_AMOUNT.value,
        DBExpensesColumns.DATE.value,
    )

    def __init__(self, db_model, users_query_service, refund_controller, app_settings_manager):
        self.db_model = db_model
        self.users_query_service = users_query_service
        self.refund_controller = refund_controller
        self.app_settings_manager = app_settings_manager

    def save_expense(self, expense_data: dict):
        """Returns (ok, msg, expense_id)."""
        for field in self.REQUIRED_FIELDS:
            if expense_data.get(field) in (None, ""):
                return False, f"Campo obbligatorio mancante: {field}.", None

        try:
            total = float(expense_data[DBExpensesColumns.TOTAL_AMOUNT.value])
        except (TypeError, ValueError):
            return False, "Importo totale non valido.", None
        if total < 0:
            return False, "L'importo non puo' essere negativo.", None

        net, iva = self._split_net_iva(total, expense_data.get("_iva_rate"))

        is_shared = bool(expense_data.get(DBExpensesColumns.IS_SHARED.value))
        advancer = expense_data.get(DBExpensesColumns.ADVANCED_BY_USER_ID.value) if is_shared else None

        record = {
            DBExpensesColumns.DESCRIPTION.value: expense_data[DBExpensesColumns.DESCRIPTION.value],
            DBExpensesColumns.USER_ID.value: int(expense_data[DBExpensesColumns.USER_ID.value]),
            DBExpensesColumns.CATEGORY.value: expense_data[DBExpensesColumns.CATEGORY.value],
            DBExpensesColumns.MERCHANT.value: expense_data.get(DBExpensesColumns.MERCHANT.value) or "",
            DBExpensesColumns.TOTAL_AMOUNT.value: total,
            DBExpensesColumns.NET_AMOUNT.value: net,
            DBExpensesColumns.IVA_AMOUNT.value: iva,
            DBExpensesColumns.DATE.value: expense_data[DBExpensesColumns.DATE.value],
            DBExpensesColumns.PAYMENT_METHOD.value: expense_data.get(DBExpensesColumns.PAYMENT_METHOD.value)
            or self.app_settings_manager.get_default_payment_method(),
            DBExpensesColumns.IS_SHARED.value: 1 if is_shared else 0,
            DBExpensesColumns.ADVANCED_BY_USER_ID.value: int(advancer) if advancer else None,
            DBExpensesColumns.VISIBILITY.value: expense_data.get(DBExpensesColumns.VISIBILITY.value)
            or self.app_settings_manager.get_default_visibility(),
            DBExpensesColumns.SOURCE.value: expense_data.get(DBExpensesColumns.SOURCE.value)
            or ExpenseSource.MANUALE.value,
            DBExpensesColumns.NOTE.value: expense_data.get(DBExpensesColumns.NOTE.value) or "",
        }

        try:
            expense_id = self.db_model.add_expense(**record)
        except Exception as exc:
            return False, f"Errore durante il salvataggio: {exc}", None

        if is_shared:
            ok, msg = self._create_shares(expense_id, expense_data, total)
            if not ok:
                # La spesa e' salvata ma senza quote valide: lo segnaliamo.
                return True, f"Spesa salvata, ma quote non impostate: {msg}", expense_id

        return True, "Spesa salvata con successo!", expense_id

    def save_parsed_expenses(self, expenses_data: list):
        """Salvataggio batch dal preview dei parser. Returns (n_ok, errors)."""
        n_ok = 0
        errors = []
        for data in expenses_data:
            ok, msg, _ = self.save_expense(data)
            if ok:
                n_ok += 1
            else:
                errors.append(msg)
        return n_ok, errors

    def update_expense(self, expense_id: int, updates: dict):
        try:
            self.db_model.update_expense(expense_id, **updates)
            return True, "Spesa aggiornata."
        except Exception as exc:
            return False, f"Errore durante l'aggiornamento: {exc}"

    def delete_expense(self, expense_id: int):
        try:
            self.db_model.remove_shares_for_expense(expense_id)
            self.db_model.remove_expense(expense_id)
            return True, "Spesa eliminata."
        except Exception as exc:
            return False, f"Errore durante l'eliminazione: {exc}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _split_net_iva(self, total: float, iva_rate):
        if iva_rate is None:
            iva_rate = self.app_settings_manager.get_default_iva()
        try:
            rate = float(iva_rate)
        except (TypeError, ValueError):
            rate = 0.0
        if rate <= 0:
            return round(total, 2), 0.0
        net = round(total / (1 + rate), 2)
        return net, round(total - net, 2)

    def _create_shares(self, expense_id, expense_data, total):
        shares = expense_data.get("_shares")
        if shares:
            return self.refund_controller.set_shares(expense_id, shares, total)
        participants = expense_data.get("_participants")
        if participants:
            return self.refund_controller.generate_equal_shares(expense_id, participants, total)
        return False, "spesa condivisa senza partecipanti."
