"""Import 'a voci' dello scontrino Esselunga.

Mostra l'elenco degli articoli; l'utente assegna ciascuno a Cibo o
Consumabili Casa. Lo scontrino viene salvato come DUE spese separate (i due
totali = somma degli articoli di ciascuna categoria). In alto un selettore
dell'utente a cui riferire le spese (default l'utente loggato)."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import DBExpensesColumns as E, DBUsersColumns, ExpenseSource

if TYPE_CHECKING:
    from App_context import AppContext
    from ParserServices.esselunga_receipt import EsselungaReceipt

_CIBO = "CIBO"
_CONSUMABILI = "CONSUMABILI_CASA"
_SPLIT = [("Cibo", _CIBO), ("Consumabili Casa", _CONSUMABILI)]


class QTEsselungaImportDialog(QDialog):
    COL_ARTICLE, COL_PRICE, COL_CATEGORY = range(3)

    def __init__(self, app_context: "AppContext", owner_user_id: int,
                 receipt: "EsselungaReceipt", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.receipt = receipt
        self.saved_count = 0

        self.expense_controller = app_context.expense_controller
        self.app_settings = app_context.app_settings_manager
        self.users = app_context.users_query_service.retrieve_users_map_list()
        self._labels = dict(app_context.catalogs_manager.get_section("expense_categories"))
        self._combos = []
        self._loading = True

        self.setWindowTitle("Import scontrino Esselunga")
        self.setModal(True)
        self.resize(640, 640)
        self._build_ui(owner_user_id)
        self._populate()
        self._loading = False
        self._recompute_totals()

    def _user_name(self, user) -> str:
        return f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"

    # ------------------------------------------------------------------

    def _build_ui(self, owner_user_id):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Spese riferite a:"))
        self.user_combo = QComboBox()
        for user in self.users:
            self.user_combo.addItem(self._user_name(user), user[DBUsersColumns.ID.value])
        idx = self.user_combo.findData(owner_user_id)
        if idx >= 0:
            self.user_combo.setCurrentIndex(idx)
        top.addWidget(self.user_combo)
        top.addSpacing(20)
        top.addWidget(QLabel("Data:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setCalendarPopup(True)
        parsed = QDate.fromString(self.receipt.date, "yyyy-MM-dd")
        self.date_edit.setDate(parsed if parsed.isValid() else QDate.currentDate())
        top.addWidget(self.date_edit)
        top.addStretch(1)
        root.addLayout(top)

        info = QLabel(
            f"Totale scontrino: {self.receipt.total:.2f} € — assegna ogni articolo "
            "a Cibo o Consumabili Casa. Verranno create due spese separate."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Articolo", "Prezzo (€)", "Categoria"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_ARTICLE, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_PRICE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_CATEGORY, QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(lambda _i: self._recompute_totals())
        root.addWidget(self.table, stretch=1)

        bulk = QHBoxLayout()
        for label, key in _SPLIT:
            btn = QPushButton(f"Tutti → {label}")
            btn.clicked.connect(lambda _=False, k=key: self._set_all_category(k))
            bulk.addWidget(btn)
        bulk.addStretch(1)
        root.addLayout(bulk)

        self.totals_label = QLabel("")
        tf = self.totals_label.font()
        tf.setBold(True)
        self.totals_label.setFont(tf)
        root.addWidget(self.totals_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Salva le due spese")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _populate(self):
        items = self.receipt.items
        self.table.setRowCount(len(items))
        for r, item in enumerate(items):
            art = QTableWidgetItem(item.description)
            self.table.setItem(r, self.COL_ARTICLE, art)
            price = QTableWidgetItem(f"{item.price:.2f}")
            price.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
            self.table.setItem(r, self.COL_PRICE, price)
            combo = QComboBox()
            for label, key in _SPLIT:
                combo.addItem(label, key)
            ci = combo.findData(item.category_key)
            combo.setCurrentIndex(ci if ci >= 0 else 0)
            combo.currentIndexChanged.connect(self._recompute_totals)
            self.table.setCellWidget(r, self.COL_CATEGORY, combo)
            self._combos.append(combo)

    # ------------------------------------------------------------------

    def _set_all_category(self, key):
        for combo in self._combos:
            idx = combo.findData(key)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        self._recompute_totals()

    def _row_price(self, row):
        item = self.table.item(row, self.COL_PRICE)
        if item is None:
            return 0.0
        try:
            return float(item.text().strip().replace(",", "."))
        except ValueError:
            return 0.0

    def _totals_by_category(self) -> dict:
        totals = {_CIBO: 0.0, _CONSUMABILI: 0.0}
        for r in range(self.table.rowCount()):
            key = self._combos[r].currentData()
            totals[key] = totals.get(key, 0.0) + self._row_price(r)
        return {k: round(v, 2) for k, v in totals.items()}

    def _recompute_totals(self):
        if self._loading:
            return
        totals = self._totals_by_category()
        self.totals_label.setText(
            f"Totale Cibo: {totals[_CIBO]:.2f} €     ·     "
            f"Totale Consumabili Casa: {totals[_CONSUMABILI]:.2f} €"
        )

    def _save(self):
        owner = self.user_combo.currentData()
        if owner is None:
            QMessageBox.warning(self, "Import", "Seleziona un utente.")
            return
        date = self.date_edit.date().toString("yyyy-MM-dd")
        totals = self._totals_by_category()

        to_save = []
        for label, key in _SPLIT:
            total = totals.get(key, 0.0)
            if total <= 0:
                continue
            to_save.append({
                E.DESCRIPTION.value: f"Spesa Esselunga – {label}",
                E.USER_ID.value: owner,
                E.CATEGORY.value: key,
                E.MERCHANT.value: self.receipt.merchant,
                E.TOTAL_AMOUNT.value: f"{total:.2f}",
                E.DATE.value: date,
                E.VISIBILITY.value: self.app_settings.get_default_visibility(),
                E.SOURCE.value: ExpenseSource.SCONTRINO.value,
                "_iva_rate": self.app_settings.get_default_iva(),
            })

        if not to_save:
            QMessageBox.information(self, "Import", "Nessun articolo con importo positivo da salvare.")
            return

        n_ok, errors = self.expense_controller.save_parsed_expenses(to_save)
        self.saved_count = n_ok
        if errors:
            QMessageBox.warning(self, "Import parziale",
                                f"Salvate {n_ok} spese. Errori:\n- " + "\n- ".join(errors[:8]))
        else:
            QMessageBox.information(self, "Import", f"Salvate {n_ok} spese (Cibo / Consumabili Casa).")
        self.accept()
