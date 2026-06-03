"""Import 'a voci' dello scontrino Esselunga.

Mostra l'elenco degli articoli; l'utente assegna ciascuno a Cibo o
Consumabili Casa. In presenza di piu' metodi di pagamento (es. carta +
buoni pasto) viene mostrata una sezione che permette di indicare quale
utente ha pagato con ciascun metodo.

I buoni pasto, per legge, coprono solo generi alimentari: se i buoni pasto
risultano pagati da un utente diverso da quello che ha pagato con la carta,
la spesa «Cibo» viene divisa in due — la quota coperta dai buoni pasto
attribuita a chi li ha usati, il resto a chi ha pagato con la carta. I
«Consumabili Casa» (non alimentari) restano sempre a carico di chi ha pagato
con la carta."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
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
_LABEL_BY_KEY = {key: label for label, key in _SPLIT}
_EURO_TOLERANCE = 0.01


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
        self._payment_combos = []   # allineati a self.receipt.payments
        self._loading = True

        self.setWindowTitle("Import scontrino Esselunga")
        self.setModal(True)
        self.resize(680, 680)
        self._build_ui(owner_user_id)
        self._populate()
        self._loading = False
        self._recompute_totals()

    def _user_name(self, user) -> str:
        return f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"

    def _user_combo(self, selected_id) -> QComboBox:
        combo = QComboBox()
        for user in self.users:
            combo.addItem(self._user_name(user), user[DBUsersColumns.ID.value])
        idx = combo.findData(selected_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        return combo

    # ------------------------------------------------------------------

    def _build_ui(self, owner_user_id):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Spese riferite a:"))
        self.user_combo = self._user_combo(owner_user_id)
        self.user_combo.currentIndexChanged.connect(self._on_owner_changed)
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
            "a Cibo o Consumabili Casa."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        # Sezione metodi di pagamento (solo se piu' di uno).
        if self.receipt.has_multiple_payments():
            root.addWidget(self._build_payments_section(owner_user_id))

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

        self.split_hint_label = QLabel("")
        self.split_hint_label.setWordWrap(True)
        self.split_hint_label.setStyleSheet("color: palette(mid);")
        root.addWidget(self.split_hint_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Salva le spese")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _build_payments_section(self, owner_user_id) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(frame)
        header = QLabel("Metodi di pagamento — indica chi ha pagato con ciascuno:")
        hf = header.font()
        hf.setBold(True)
        header.setFont(hf)
        lay.addWidget(header)

        for payment in self.receipt.payments:
            row = QHBoxLayout()
            tag = " (buoni pasto)" if payment.is_meal_voucher else ""
            label = QLabel(f"{payment.method}{tag}: {payment.amount:.2f} €")
            label.setMinimumWidth(320)
            row.addWidget(label)
            combo = self._user_combo(owner_user_id)
            combo.currentIndexChanged.connect(self._recompute_totals)
            row.addWidget(combo)
            row.addStretch(1)
            lay.addLayout(row)
            self._payment_combos.append(combo)

        note = QLabel(
            "I buoni pasto coprono solo generi alimentari: se pagati da un utente "
            "diverso da chi ha usato la carta, la spesa «Cibo» verra' divisa."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        lay.addWidget(note)
        return frame

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

    def _on_owner_changed(self, _idx=None):
        # Riallinea i selettori di pagamento all'owner finche' l'utente non li
        # personalizza esplicitamente (comportamento intuitivo: cambiando il
        # pagatore principale cambiano i default).
        if self._loading:
            return
        self._recompute_totals()

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

    def _payment_assignment(self):
        """(card_user_id, meal_user_id, meal_amount) dall'assegnazione corrente.

        card_user = utente del primo metodo non-buono-pasto (fallback: owner).
        meal_user = utente dell'ultimo buono pasto (None se assente).
        meal_amount = somma dei buoni pasto."""
        owner = self.user_combo.currentData()
        card_user = owner
        meal_user = None
        meal_amount = 0.0
        card_seen = False
        for payment, combo in zip(self.receipt.payments, self._payment_combos):
            assigned = combo.currentData()
            if payment.is_meal_voucher:
                meal_amount += payment.amount
                meal_user = assigned
            elif not card_seen:
                card_user = assigned
                card_seen = True
        return card_user, meal_user, round(meal_amount, 2)

    def _recompute_totals(self):
        if self._loading:
            return
        totals = self._totals_by_category()
        self.totals_label.setText(
            f"Totale Cibo: {totals[_CIBO]:.2f} €     ·     "
            f"Totale Consumabili Casa: {totals[_CONSUMABILI]:.2f} €"
        )

        card_user, meal_user, meal_amount = self._payment_assignment()
        if meal_amount > 0 and meal_user is not None and meal_user != card_user:
            cibo = totals[_CIBO]
            if meal_amount > cibo + _EURO_TOLERANCE:
                self.split_hint_label.setText(
                    f"⚠ I buoni pasto ({meal_amount:.2f} €) superano il totale Cibo "
                    f"({cibo:.2f} €): sposta gli alimentari sotto «Cibo» prima di salvare."
                )
            else:
                card_food = round(cibo - meal_amount, 2)
                self.split_hint_label.setText(
                    f"Cibo diviso: {meal_amount:.2f} € → {self._name_of(meal_user)} (buoni pasto), "
                    f"{card_food:.2f} € → {self._name_of(card_user)} (carta)."
                )
        else:
            self.split_hint_label.setText("")

    def _name_of(self, user_id):
        for user in self.users:
            if user[DBUsersColumns.ID.value] == user_id:
                return self._user_name(user)
        return f"Utente {user_id}"

    # ------------------------------------------------------------------

    def _make_expense(self, user_id, key, label, amount, date) -> dict:
        return {
            E.DESCRIPTION.value: f"Spesa Esselunga – {label}",
            E.USER_ID.value: user_id,
            E.CATEGORY.value: key,
            E.MERCHANT.value: self.receipt.merchant,
            E.TOTAL_AMOUNT.value: f"{amount:.2f}",
            E.DATE.value: date,
            E.VISIBILITY.value: self.app_settings.get_default_visibility(),
            E.SOURCE.value: ExpenseSource.SCONTRINO.value,
            "_iva_rate": self.app_settings.get_default_iva(),
        }

    def _save(self):
        owner = self.user_combo.currentData()
        if owner is None:
            QMessageBox.warning(self, "Import", "Seleziona un utente.")
            return
        date = self.date_edit.date().toString("yyyy-MM-dd")
        totals = self._totals_by_category()
        cibo = totals.get(_CIBO, 0.0)
        consumabili = totals.get(_CONSUMABILI, 0.0)

        card_user, meal_user, meal_amount = self._payment_assignment()
        split_food = meal_amount > 0 and meal_user is not None and meal_user != card_user

        if split_food and meal_amount > cibo + _EURO_TOLERANCE:
            QMessageBox.warning(
                self, "Buoni pasto",
                f"L'importo dei buoni pasto ({meal_amount:.2f} €) supera il totale "
                f"assegnato a «Cibo» ({cibo:.2f} €).\n\nI buoni pasto possono pagare "
                "solo generi alimentari: sposta gli articoli alimentari sotto «Cibo» "
                "e riprova.",
            )
            return

        to_save = []
        # Non alimentari: sempre a carico di chi ha pagato con la carta.
        if consumabili > 0:
            to_save.append(self._make_expense(
                card_user, _CONSUMABILI, _LABEL_BY_KEY[_CONSUMABILI], consumabili, date))

        # Alimentari: split solo se i buoni pasto sono di un altro utente.
        if cibo > 0:
            if split_food:
                voucher_food = min(meal_amount, cibo)
                card_food = round(cibo - voucher_food, 2)
                if voucher_food > 0:
                    to_save.append(self._make_expense(
                        meal_user, _CIBO, "Cibo (buoni pasto)", voucher_food, date))
                if card_food > 0:
                    to_save.append(self._make_expense(
                        card_user, _CIBO, "Cibo (carta)", card_food, date))
            else:
                to_save.append(self._make_expense(
                    card_user, _CIBO, _LABEL_BY_KEY[_CIBO], cibo, date))

        if not to_save:
            QMessageBox.information(self, "Import", "Nessun articolo con importo positivo da salvare.")
            return

        n_ok, errors = self.expense_controller.save_parsed_expenses(to_save)
        self.saved_count = n_ok
        if errors:
            QMessageBox.warning(self, "Import parziale",
                                f"Salvate {n_ok} spese. Errori:\n- " + "\n- ".join(errors[:8]))
        else:
            QMessageBox.information(self, "Import", f"Salvate {n_ok} spese dallo scontrino.")
        self.accept()
