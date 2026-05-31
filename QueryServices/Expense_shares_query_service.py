from Gestionale_Enums import DBExpenseSharesColumns
from Utils.Controller_utils import ControllerUtils


class ExpenseSharesQueryService:
    """Letture delle quote di condivisione delle spese."""

    def __init__(self, db_model):
        self.db_model = db_model

    def retrieve_all_shares(self):
        rows = self.db_model.fetch_expense_shares()
        return [ControllerUtils.row_to_map(r, DBExpenseSharesColumns) for r in rows]

    def retrieve_shares_for_expense(self, expense_id):
        rows = self.db_model.fetch_shares_by_expense_id(expense_id)
        return [ControllerUtils.row_to_map(r, DBExpenseSharesColumns) for r in rows]

    def retrieve_share_map_by_id(self, share_id):
        return ControllerUtils.row_to_map(
            self.db_model.fetch_share_by_id(share_id), DBExpenseSharesColumns
        )

    def expense_ids_for_user(self, user_id) -> set:
        """Insieme degli expense_id in cui ``user_id`` compare come
        partecipante (usato dal filtro di visibilita')."""
        ids = set()
        for share in self.retrieve_all_shares():
            if share.get(DBExpenseSharesColumns.USER_ID.value) == user_id:
                ids.add(share.get(DBExpenseSharesColumns.EXPENSE_ID.value))
        return ids
