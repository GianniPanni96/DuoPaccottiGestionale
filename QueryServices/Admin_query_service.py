from Gestionale_Enums import DBAdminColumns
from Utils.Controller_utils import ControllerUtils


class AdminQueryService:
    """Letture per il singolo admin di sistema."""

    def __init__(self, db_model):
        self.db_model = db_model

    def admin_exists(self) -> bool:
        return self.db_model.count_admin() > 0

    def retrieve_admin_map(self):
        row = self.db_model.fetch_admin()
        if not row:
            return None
        return ControllerUtils.row_to_map(row, DBAdminColumns)
