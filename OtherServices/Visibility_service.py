"""Filtro di visibilita' applicativo (privacy "globale vs privato").

Regola per l'utente che guarda (viewer):
- vede tutte le proprie righe (``user_id == viewer``);
- vede le righe altrui marcate ``PUBBLICA``;
- vede le spese condivise di cui e' partecipante (sempre, perche' coinvolto
  nel rimborso).

L'admin e' puramente amministrativo: non ha accesso ai dati finanziari,
quindi i filtri ritornano sempre lista vuota in sessione admin.
"""

from Gestionale_Enums import (
    DBExpensesColumns,
    DBIncomesColumns,
    Visibility,
)


class VisibilityService:
    def __init__(self, session_context, expense_shares_query_service):
        self.session_context = session_context
        self.expense_shares_query_service = expense_shares_query_service

    def _viewer(self, viewer_user_id):
        if viewer_user_id is not None:
            return viewer_user_id
        return self.session_context.current_user_id

    def filter_expenses(self, expenses, viewer_user_id=None):
        if self.session_context.is_admin:
            return []
        viewer = self._viewer(viewer_user_id)
        if viewer is None or viewer < 0:
            return []

        participant_ids = self.expense_shares_query_service.expense_ids_for_user(viewer)
        result = []
        for e in expenses:
            owner = e.get(DBExpensesColumns.USER_ID.value)
            if owner == viewer:
                result.append(e)
            elif e.get(DBExpensesColumns.VISIBILITY.value) == Visibility.PUBBLICA.value:
                result.append(e)
            elif e.get(DBExpensesColumns.ID.value) in participant_ids:
                result.append(e)
        return result

    def filter_incomes(self, incomes, viewer_user_id=None):
        if self.session_context.is_admin:
            return []
        viewer = self._viewer(viewer_user_id)
        if viewer is None or viewer < 0:
            return []
        return [
            i for i in incomes
            if i.get(DBIncomesColumns.USER_ID.value) == viewer
            or i.get(DBIncomesColumns.VISIBILITY.value) == Visibility.PUBBLICA.value
        ]
