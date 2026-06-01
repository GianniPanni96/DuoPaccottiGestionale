"""Tab Entrate: lista con filtro per anno, ricerca, inserimento manuale,
eliminazione, apertura dettaglio."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from Gestionale_Enums import DBIncomesColumns as I
from QTViews.CustomWidgets.QT_dict_table_model import Column
from QTViews.ListViews.QT_base_list_view import QTBaseListView

if TYPE_CHECKING:
    from App_context import AppContext

_RIGHT = int(Qt.AlignRight | Qt.AlignVCenter)


class QTIncomesView(QTBaseListView):
    AGGREGATE_KEYS = ("#ENTRATE", "TOT. ENTRATE")
    SEARCH_PLACEHOLDER = "Cerca un'entrata…"
    ADD_BUTTON_TEXT = "Aggiungi entrata manuale"
    ITEM_LABEL_PLURAL = "entrate"

    COLUMNS = (
        Column("Data", "_date_label", sort_key=lambda v: v or ""),
        Column("Descrizione", I.DESCRIPTION.value),
        Column("Categoria", "_category_label"),
        Column("Importo", "_amount", formatter=lambda v: f"{v:.2f} €", align=_RIGHT, sort_key=lambda v: v),
        Column("Visibilità", I.VISIBILITY.value),
    )

    def _setup_services(self, app_context: "AppContext"):
        self.incomes_query_service = app_context.incomes_query_service
        self.income_analyzer_service = app_context.income_analyzer_service
        self.income_controller = app_context.income_controller
        self.session_context = app_context.session_context
        self._catalogs_manager = app_context.catalogs_manager
        self._category_label_map = dict(self._catalogs_manager.get_section("income_categories"))

    def fetch_items(self, year):
        return self.incomes_query_service.retrieve_incomes_map_list(year=year)

    def build_rows(self, items):
        self._category_label_map = dict(self._catalogs_manager.get_section("income_categories"))
        rows = []
        for raw in items:
            inc = dict(raw)
            inc["_category_label"] = self._category_label_map.get(
                inc.get(I.CATEGORY.value), inc.get(I.CATEGORY.value)
            )
            inc["_date_label"] = (inc.get(I.DATE.value) or "")[:10]
            try:
                inc["_amount"] = float(inc.get(I.AMOUNT.value) or 0.0)
            except (TypeError, ValueError):
                inc["_amount"] = 0.0
            rows.append(inc)
        return rows

    def compute_aggregates(self, year):
        return self.income_analyzer_service.build_aggregate_data(year=year)

    def open_creator_dialog(self):
        from QTViews.Creators.QT_income_create_view import QTIncomeCreateView
        owner_id = self.session_context.current_user_id
        if owner_id < 0:
            QMessageBox.warning(self, "Entrata", "Devi essere loggato come utente per aggiungere un'entrata.")
            return None
        dialog = QTIncomeCreateView(app_context=self.app_context, owner_user_id=owner_id, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.created_income_id

    def context_menu_actions(self, row):
        income_id = row.get(I.ID.value)
        return [("Elimina entrata", lambda: self._delete(income_id))]

    def _delete(self, income_id):
        confirm = QMessageBox.question(
            self, "Elimina", "Eliminare questa entrata?", QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        ok, msg = self.income_controller.delete_income(income_id)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
        self._reload_data()
