"""Aggregazioni del dominio entrate (simmetrico alle spese, semplificato)."""

from datetime import datetime

from Gestionale_Enums import DBIncomesColumns
from Utils.Controller_utils import ControllerUtils


class IncomeAnalyzerService:
    NUMERO_ENTRATE_KEY = "#ENTRATE"
    TOT_ENTRATE_KEY = "TOT. ENTRATE"

    def __init__(self, incomes_query_service):
        self.incomes_query_service = incomes_query_service

    def count_incomes(self, year=None, viewer_user_id=None) -> int:
        return len(self.incomes_query_service.retrieve_incomes_map_list(
            year=year, viewer_user_id=viewer_user_id
        ))

    def calculate_tot_incomes(self, year=None, viewer_user_id=None) -> float:
        return self._sum(self.incomes_query_service.retrieve_incomes_map_list(
            year=year, viewer_user_id=viewer_user_id
        ))

    def build_aggregate_data(self, year=None, viewer_user_id=None) -> dict:
        incomes = self.incomes_query_service.retrieve_incomes_map_list(
            year=year, viewer_user_id=viewer_user_id
        )
        return {
            self.NUMERO_ENTRATE_KEY: len(incomes),
            self.TOT_ENTRATE_KEY: f"{self._sum(incomes):.2f} €",
        }

    def annual_by_user_and_category(self, year=None, viewer_user_id=None) -> dict:
        incomes = self.incomes_query_service.retrieve_incomes_map_list(
            year=year, viewer_user_id=viewer_user_id
        )
        result = {}
        for i in incomes:
            user_id = i.get(DBIncomesColumns.USER_ID.value)
            category = i.get(DBIncomesColumns.CATEGORY.value)
            per_user = result.setdefault(user_id, {})
            per_user[category] = per_user.get(category, 0.0) + self._amount(i)
        return result

    @staticmethod
    def _amount(income) -> float:
        try:
            return float(income.get(DBIncomesColumns.AMOUNT.value) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _sum(self, incomes) -> float:
        return sum(self._amount(i) for i in incomes)
