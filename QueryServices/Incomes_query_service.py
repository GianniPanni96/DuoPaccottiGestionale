from Gestionale_Enums import DBIncomesColumns
from Utils.Controller_utils import ControllerUtils


class IncomesQueryService:
    """Letture del dominio entrate, con filtro di visibilita' opzionale."""

    def __init__(self, db_model, visibility_service=None):
        self.db_model = db_model
        self.visibility_service = visibility_service

    def _all_maps(self):
        rows = self.db_model.fetch_incomes()
        return [ControllerUtils.row_to_map(r, DBIncomesColumns) for r in rows]

    def retrieve_incomes_map_list(self, year=None, apply_visibility=True, viewer_user_id=None):
        incomes = self._all_maps()
        incomes = ControllerUtils.filter_by_year(incomes, DBIncomesColumns.DATE.value, year)
        if apply_visibility and self.visibility_service is not None:
            incomes = self.visibility_service.filter_incomes(incomes, viewer_user_id)
        return incomes

    def retrieve_income_map_by_id(self, income_id):
        return ControllerUtils.row_to_map(
            self.db_model.fetch_income_by_id(income_id), DBIncomesColumns
        )

    def retrieve_incomes_map_list_by_user(self, user_id, year=None):
        rows = self.db_model.fetch_incomes_by_user_id(user_id)
        incomes = [ControllerUtils.row_to_map(r, DBIncomesColumns) for r in rows]
        return ControllerUtils.filter_by_year(incomes, DBIncomesColumns.DATE.value, year)

    def retrieve_last_income_insert_map(self):
        return ControllerUtils.row_to_map(
            self.db_model.fetch_last_income_insert(), DBIncomesColumns
        )
