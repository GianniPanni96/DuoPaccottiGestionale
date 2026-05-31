"""Gestione delle quote di condivisione e dei saldi.

Una spesa condivisa ha N partecipanti con percentuali (somma = 1.0).
L'anticipatore (``advanced_by_user_id``) ha pagato il totale; gli altri
partecipanti gli devono la propria quota finche' non e' ``settled``.
"""

from datetime import datetime

from Gestionale_Enums import DBExpenseSharesColumns, DBExpensesColumns
from Utils.Controller_utils import ControllerUtils


_PCT_TOLERANCE = 0.01


class RefundController:
    def __init__(self, db_model, expense_shares_query_service):
        self.db_model = db_model
        self.expense_shares_query_service = expense_shares_query_service

    # ------------------------------------------------------------------
    # Creazione/aggiornamento quote
    # ------------------------------------------------------------------

    def generate_equal_shares(self, expense_id, participant_ids, total_amount):
        """Quote eque tra i partecipanti (default richiesto dal SCOPO)."""
        participant_ids = [int(p) for p in participant_ids if p is not None]
        if not participant_ids:
            return False, "Nessun partecipante indicato."
        pct = 1.0 / len(participant_ids)
        shares = {uid: pct for uid in participant_ids}
        return self.set_shares(expense_id, shares, total_amount)

    def set_shares(self, expense_id, shares: dict, total_amount):
        """Sostituisce le quote di una spesa. ``shares`` = {user_id: pct}
        con pct in [0,1] e somma ~1.0."""
        if not shares:
            return False, "Nessuna quota fornita."
        total_pct = sum(float(p) for p in shares.values())
        if abs(total_pct - 1.0) > _PCT_TOLERANCE:
            return False, f"La somma delle percentuali deve essere 100% (attuale: {total_pct * 100:.1f}%)."

        try:
            total = float(total_amount)
        except (TypeError, ValueError):
            return False, "Importo totale non valido."

        try:
            self.db_model.remove_shares_for_expense(expense_id)
            for user_id, pct in shares.items():
                self.db_model.add_expense_share(**{
                    DBExpenseSharesColumns.EXPENSE_ID.value: expense_id,
                    DBExpenseSharesColumns.USER_ID.value: int(user_id),
                    DBExpenseSharesColumns.PERCENTAGE.value: float(pct),
                    DBExpenseSharesColumns.AMOUNT.value: round(total * float(pct), 2),
                    DBExpenseSharesColumns.IS_SETTLED.value: 0,
                })
            self.sync_expense_settled_flag(expense_id)
            return True, "Quote aggiornate."
        except Exception as exc:
            return False, f"Errore durante l'aggiornamento delle quote: {exc}"

    def clear_shares(self, expense_id):
        self.db_model.remove_shares_for_expense(expense_id)

    # ------------------------------------------------------------------
    # Saldo quote
    # ------------------------------------------------------------------

    def mark_share_settled(self, share_id):
        try:
            self.db_model.update_expense_share(share_id, **{
                DBExpenseSharesColumns.IS_SETTLED.value: 1,
                DBExpenseSharesColumns.SETTLED_AT.value: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            self._sync_from_share(share_id)
            return True, "Quota segnata come saldata."
        except Exception as exc:
            return False, f"Errore: {exc}"

    def mark_share_unsettled(self, share_id):
        try:
            self.db_model.update_expense_share(share_id, **{
                DBExpenseSharesColumns.IS_SETTLED.value: 0,
                DBExpenseSharesColumns.SETTLED_AT.value: None,
            })
            self._sync_from_share(share_id)
            return True, "Quota segnata come non saldata."
        except Exception as exc:
            return False, f"Errore: {exc}"

    def _sync_from_share(self, share_id):
        share = self.expense_shares_query_service.retrieve_share_map_by_id(share_id)
        if share:
            self.sync_expense_settled_flag(share[DBExpenseSharesColumns.EXPENSE_ID.value])

    def sync_expense_settled_flag(self, expense_id):
        """Aggiorna ``expenses.is_settled``: la spesa e' saldata quando
        tutte le quote dei partecipanti diversi dall'anticipatore lo sono."""
        expense = ControllerUtils.row_to_map(
            self.db_model.fetch_expense_by_id(expense_id), DBExpensesColumns
        )
        if not expense:
            return
        advancer = expense.get(DBExpensesColumns.ADVANCED_BY_USER_ID.value)
        shares = self.expense_shares_query_service.retrieve_shares_for_expense(expense_id)

        debtor_shares = [
            s for s in shares
            if s.get(DBExpenseSharesColumns.USER_ID.value) != advancer
        ]
        all_settled = bool(debtor_shares) and all(
            s.get(DBExpenseSharesColumns.IS_SETTLED.value) for s in debtor_shares
        )
        self.db_model.update_expense(
            expense_id, **{DBExpensesColumns.IS_SETTLED.value: 1 if all_settled else 0}
        )
