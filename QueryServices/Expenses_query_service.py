from Gestionale_Enums import DBExpensesColumns
from Utils.Controller_utils import ControllerUtils


class ExpensesQueryService:
    """Letture del dominio spese, con filtro di visibilita' opzionale."""

    def __init__(self, db_model, visibility_service=None):
        self.db_model = db_model
        self.visibility_service = visibility_service

    def _all_maps(self):
        rows = self.db_model.fetch_expenses()
        return [ControllerUtils.row_to_map(r, DBExpensesColumns) for r in rows]

    def retrieve_expenses_map_list(self, year=None, apply_visibility=True, viewer_user_id=None):
        expenses = self._all_maps()
        expenses = ControllerUtils.filter_by_year(expenses, DBExpensesColumns.DATE.value, year)
        if apply_visibility and self.visibility_service is not None:
            expenses = self.visibility_service.filter_expenses(expenses, viewer_user_id)
        return expenses

    def retrieve_expense_map_by_id(self, expense_id):
        return ControllerUtils.row_to_map(
            self.db_model.fetch_expense_by_id(expense_id), DBExpensesColumns
        )

    def retrieve_expenses_map_list_by_user(self, user_id, year=None):
        rows = self.db_model.fetch_expenses_by_user_id(user_id)
        expenses = [ControllerUtils.row_to_map(r, DBExpensesColumns) for r in rows]
        return ControllerUtils.filter_by_year(expenses, DBExpensesColumns.DATE.value, year)

    def retrieve_shared_expenses(self, year=None):
        """Tutte le spese condivise (no filtro visibilita': servono al
        calcolo dei rimborsi, e una spesa condivisa e' nota ai partecipanti)."""
        expenses = self._all_maps()
        expenses = [e for e in expenses if e.get(DBExpensesColumns.IS_SHARED.value)]
        return ControllerUtils.filter_by_year(expenses, DBExpensesColumns.DATE.value, year)

    def retrieve_last_expense_insert_map(self):
        return ControllerUtils.row_to_map(
            self.db_model.fetch_last_expense_insert(), DBExpensesColumns
        )
