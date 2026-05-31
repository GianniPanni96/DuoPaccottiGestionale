"""Aggregazioni e metriche del dominio spese (analisi 1/2/3 del SCOPO).

Tutte le letture passano dal query service e quindi rispettano il filtro
di visibilita': un utente vede aggregati calcolati sul proprio insieme
visibile (proprie + pubbliche altrui + condivise di cui partecipa).
"""

from datetime import datetime

from Gestionale_Enums import DBExpensesColumns
from Utils.Controller_utils import ControllerUtils


class ExpenseAnalyzerService:
    NUMERO_SPESE_KEY = "#SPESE"
    TOT_SPESE_KEY = "TOT. SPESE"

    def __init__(self, expenses_query_service):
        self.expenses_query_service = expenses_query_service

    # ------------------------------------------------------------------
    # Card aggregate
    # ------------------------------------------------------------------

    def count_expenses(self, year=None, viewer_user_id=None) -> int:
        return len(self.expenses_query_service.retrieve_expenses_map_list(
            year=year, viewer_user_id=viewer_user_id
        ))

    def calculate_tot_expenses(self, year=None, viewer_user_id=None) -> float:
        return self._sum(self.expenses_query_service.retrieve_expenses_map_list(
            year=year, viewer_user_id=viewer_user_id
        ))

    def build_aggregate_data(self, year=None, viewer_user_id=None) -> dict:
        expenses = self.expenses_query_service.retrieve_expenses_map_list(
            year=year, viewer_user_id=viewer_user_id
        )
        return {
            self.NUMERO_SPESE_KEY: len(expenses),
            self.TOT_SPESE_KEY: f"{self._sum(expenses):.2f} €",
        }

    # ------------------------------------------------------------------
    # Analisi 1: annuale per utente x categoria
    # ------------------------------------------------------------------

    def annual_by_user_and_category(self, year=None, viewer_user_id=None) -> dict:
        expenses = self.expenses_query_service.retrieve_expenses_map_list(
            year=year, viewer_user_id=viewer_user_id
        )
        return self._group_by_user_and_category(expenses)

    # ------------------------------------------------------------------
    # Analisi 2: mensile per utente x categoria (anno corrente)
    # ------------------------------------------------------------------

    def monthly_by_user_and_category(self, month: int, year=None, viewer_user_id=None) -> dict:
        target_year = year if year not in (None, -1) else datetime.now().year
        expenses = self.expenses_query_service.retrieve_expenses_map_list(
            year=target_year, viewer_user_id=viewer_user_id
        )
        month_expenses = [
            e for e in expenses
            if self._month_of(e) == month
        ]
        return self._group_by_user_and_category(month_expenses)

    # ------------------------------------------------------------------
    # Analisi 3: media mensile per categoria (anno corrente)
    # ------------------------------------------------------------------

    def monthly_average_by_category(self, year=None, viewer_user_id=None) -> dict:
        target_year = year if year not in (None, -1) else datetime.now().year
        expenses = self.expenses_query_service.retrieve_expenses_map_list(
            year=target_year, viewer_user_id=viewer_user_id
        )
        months_elapsed = self._months_elapsed(target_year)
        totals_by_category = {}
        for e in expenses:
            category = e.get(DBExpensesColumns.CATEGORY.value)
            totals_by_category[category] = totals_by_category.get(category, 0.0) + self._amount(e)
        return {cat: tot / months_elapsed for cat, tot in totals_by_category.items()}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _group_by_user_and_category(self, expenses) -> dict:
        result = {}
        for e in expenses:
            user_id = e.get(DBExpensesColumns.USER_ID.value)
            category = e.get(DBExpensesColumns.CATEGORY.value)
            per_user = result.setdefault(user_id, {})
            per_user[category] = per_user.get(category, 0.0) + self._amount(e)
        return result

    @staticmethod
    def _amount(expense) -> float:
        try:
            return float(expense.get(DBExpensesColumns.TOTAL_AMOUNT.value) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _sum(self, expenses) -> float:
        return sum(self._amount(e) for e in expenses)

    @staticmethod
    def _month_of(expense):
        dt = ControllerUtils._parse_datetime(expense.get(DBExpensesColumns.DATE.value))
        return dt.month if dt else None

    @staticmethod
    def _months_elapsed(year: int) -> int:
        now = datetime.now()
        if year == now.year:
            return max(1, now.month)
        return 12
