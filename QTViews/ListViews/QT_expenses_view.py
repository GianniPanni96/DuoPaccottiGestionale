"""Tab Spese: lista con card aggregate, filtro per anno, ricerca,
inserimento manuale, import (step 4), eliminazione, apertura dettaglio."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from Gestionale_Enums import DBExpensesColumns as E
from QTViews.CustomWidgets.QT_dict_table_model import Column
from QTViews.ListViews.QT_base_list_view import QTBaseListView

if TYPE_CHECKING:
    from App_context import AppContext

_RIGHT = int(Qt.AlignRight | Qt.AlignVCenter)


class QTExpensesView(QTBaseListView):
    AGGREGATE_KEYS = ("#SPESE", "TOT. SPESE")
    SEARCH_PLACEHOLDER = "Cerca una spesa…"
    ADD_BUTTON_TEXT = "Aggiungi spesa manuale"
    ITEM_LABEL_PLURAL = "spese"

    COLUMNS = (
        Column("Data", "_date_label", sort_key=lambda v: v or ""),
        Column("Descrizione", E.DESCRIPTION.value),
        Column("Categoria", "_category_label"),
        Column("Esercente", E.MERCHANT.value),
        Column("Importo", "_amount", formatter=lambda v: f"{v:.2f} €", align=_RIGHT, sort_key=lambda v: v),
        Column("Metodo", E.PAYMENT_METHOD.value),
        Column("Condivisa", "_shared_label"),
        Column("Saldo", "_settled_label"),
        Column("Visibilità", E.VISIBILITY.value),
    )

    def _setup_services(self, app_context: "AppContext"):
        self.expenses_query_service = app_context.expenses_query_service
        self.expense_analyzer_service = app_context.expense_analyzer_service
        self.expense_controller = app_context.expense_controller
        self.session_context = app_context.session_context
        self._catalogs_manager = app_context.catalogs_manager
        self._category_label_map = dict(self._catalogs_manager.get_section("expense_categories"))

    def fetch_items(self, year):
        return self.expenses_query_service.retrieve_expenses_map_list(year=year)

    def build_rows(self, items):
        # Rilegge le etichette categoria a ogni reload, cosi' le modifiche dal
        # menu 'Categorie' sono visibili senza riavviare.
        self._category_label_map = dict(self._catalogs_manager.get_section("expense_categories"))
        rows = []
        for raw in items:
            e = dict(raw)
            e["_category_label"] = self._category_label_map.get(
                e.get(E.CATEGORY.value), e.get(E.CATEGORY.value)
            )
            e["_date_label"] = (e.get(E.DATE.value) or "")[:10]
            try:
                e["_amount"] = float(e.get(E.TOTAL_AMOUNT.value) or 0.0)
            except (TypeError, ValueError):
                e["_amount"] = 0.0
            shared = bool(e.get(E.IS_SHARED.value))
            e["_shared_label"] = "Condivisa" if shared else "—"
            if shared:
                e["_settled_label"] = "Saldata" if e.get(E.IS_SETTLED.value) else "Da saldare"
            else:
                e["_settled_label"] = "—"
            rows.append(e)
        return rows

    def compute_aggregates(self, year):
        return self.expense_analyzer_service.build_aggregate_data(year=year)

    def open_creator_dialog(self):
        from QTViews.Creators.QT_expense_create_view import QTExpenseCreateView
        owner_id = self.session_context.current_user_id
        if owner_id < 0:
            QMessageBox.warning(self, "Spesa", "Devi essere loggato come utente per aggiungere una spesa.")
            return None
        dialog = QTExpenseCreateView(app_context=self.app_context, owner_user_id=owner_id, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.created_expense_id

    def extra_action_buttons(self):
        return [
            ("Importa da estratto conto", self._import_bank),
            ("Importa da scontrino Esselunga", self._import_receipt),
        ]

    def _import_bank(self):
        from Gestionale_Enums import ExpenseSource
        from PySide6.QtWidgets import QFileDialog
        from QTViews.Imports.QT_import_preview_dialog import QTImportPreviewDialog

        owner_id = self._import_owner()
        if owner_id is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona la lista movimenti (PDF)", "", "PDF (*.pdf)")
        if not path:
            return
        try:
            movements = self.app_context.bank_parser.parse(path)
        except Exception as exc:
            QMessageBox.critical(self, "Errore di lettura", f"Impossibile leggere il PDF:\n{exc}")
            return
        if not movements:
            QMessageBox.information(self, "Import", "Nessun movimento riconosciuto nel PDF selezionato.")
            return
        dialog = QTImportPreviewDialog(
            app_context=self.app_context, owner_user_id=owner_id, movements=movements,
            source=ExpenseSource.ESTRATTO_BANCA.value,
            title="Import estratto conto IntesaSanpaolo", parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_count:
            self._reload_data()

    def _import_receipt(self):
        from PySide6.QtWidgets import QFileDialog
        from ParserServices.esselunga_receipt_parser import ReceiptParseError
        from QTViews.Imports.QT_esselunga_import_dialog import QTEsselungaImportDialog

        owner_id = self._import_owner()
        if owner_id is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona lo scontrino Esselunga (PDF)", "", "PDF (*.pdf)")
        if not path:
            return
        try:
            receipt = self.app_context.esselunga_parser.parse_receipt(path)
        except ReceiptParseError as exc:
            QMessageBox.critical(self, "Scontrino non riconosciuto", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Errore di lettura", f"Impossibile leggere il PDF:\n{exc}")
            return
        dialog = QTEsselungaImportDialog(
            app_context=self.app_context, owner_user_id=owner_id, receipt=receipt, parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_count:
            self._reload_data()

    def _import_owner(self):
        owner_id = self.session_context.current_user_id
        if owner_id < 0:
            QMessageBox.warning(self, "Import", "Devi essere loggato come utente per importare spese.")
            return None
        return owner_id

    def context_menu_actions(self, row):
        expense_id = row.get(E.ID.value)
        return [("Elimina spesa", lambda: self._delete(expense_id))]

    def _delete(self, expense_id):
        confirm = QMessageBox.question(
            self, "Elimina", "Eliminare questa spesa?", QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        ok, msg = self.expense_controller.delete_expense(expense_id)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
        self._reload_data()
