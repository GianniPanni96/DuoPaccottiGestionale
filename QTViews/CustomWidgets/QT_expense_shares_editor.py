"""Editor delle quote di una spesa condivisa (usato nel dettaglio spesa).

Due sezioni:
- Composizione: anticipatore + partecipanti con percentuali (default equo);
- Saldi: per ogni partecipante diverso dall'anticipatore, lo stato della
  quota con il pulsante 'segna come saldata'.
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import (
    DBExpensesColumns,
    DBExpenseSharesColumns,
    DBUsersColumns,
)

if TYPE_CHECKING:
    from App_context import AppContext


class QTExpenseSharesEditor(QWidget):
    def __init__(self, app_context: "AppContext", expense: dict, on_changed=None, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.expense = expense
        self.expense_id = expense[DBExpensesColumns.ID.value]
        self.on_changed = on_changed

        self.refund_controller = app_context.refund_controller
        self.shares_query = app_context.expense_shares_query_service
        self.expense_controller = app_context.expense_controller

        self.users = app_context.users_query_service.retrieve_users_map_list()
        self._participant_widgets = {}  # user_id -> (checkbox, pct_spin, amount_label)

        self._build_ui()
        self.load()

    # ------------------------------------------------------------------

    def _total(self) -> float:
        try:
            return float(self.expense.get(DBExpensesColumns.TOTAL_AMOUNT.value) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _user_name(self, user) -> str:
        return f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # Anticipatore
        advancer_row = QHBoxLayout()
        advancer_row.addWidget(QLabel("Anticipata da:"))
        self.advancer_combo = QComboBox()
        for user in self.users:
            self.advancer_combo.addItem(self._user_name(user), user[DBUsersColumns.ID.value])
        advancer_row.addWidget(self.advancer_combo, stretch=1)
        root.addLayout(advancer_row)

        # Partecipanti
        root.addWidget(self._header("Partecipanti e quote"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.addWidget(QLabel("Partecipa"), 0, 0)
        grid.addWidget(QLabel("Utente"), 0, 1)
        grid.addWidget(QLabel("Quota %"), 0, 2)
        grid.addWidget(QLabel("Importo"), 0, 3)

        for i, user in enumerate(self.users, start=1):
            uid = user[DBUsersColumns.ID.value]
            check = QCheckBox()
            check.toggled.connect(self._recompute_amounts)
            grid.addWidget(check, i, 0, alignment=Qt.AlignCenter)
            grid.addWidget(QLabel(self._user_name(user)), i, 1)

            pct = QDoubleSpinBox()
            pct.setRange(0.0, 100.0)
            pct.setDecimals(1)
            pct.setSuffix(" %")
            pct.valueChanged.connect(self._recompute_amounts)
            grid.addWidget(pct, i, 2)

            amount_label = QLabel("0.00 €")
            grid.addWidget(amount_label, i, 3)

            self._participant_widgets[uid] = (check, pct, amount_label)
        root.addLayout(grid)

        btn_row = QHBoxLayout()
        equal_btn = QPushButton("Dividi equamente tra i selezionati")
        equal_btn.clicked.connect(self._on_equal_split)
        btn_row.addWidget(equal_btn)
        save_btn = QPushButton("Salva quote")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        # Saldi
        root.addWidget(self._header("Saldi (rimborsi verso l'anticipatore)"))
        self.settle_container = QVBoxLayout()
        self.settle_container.setSpacing(6)
        root.addLayout(self.settle_container)

    @staticmethod
    def _header(text: str) -> QLabel:
        lbl = QLabel(text)
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
        lbl.setStyleSheet("margin-top: 6px;")
        return lbl

    # ------------------------------------------------------------------
    # Caricamento stato dal DB
    # ------------------------------------------------------------------

    def load(self):
        shares = self.shares_query.retrieve_shares_for_expense(self.expense_id)
        shares_by_user = {s[DBExpenseSharesColumns.USER_ID.value]: s for s in shares}

        advancer = self.expense.get(DBExpensesColumns.ADVANCED_BY_USER_ID.value)
        if advancer is not None:
            idx = self.advancer_combo.findData(advancer)
            if idx >= 0:
                self.advancer_combo.setCurrentIndex(idx)

        for uid, (check, pct, _amount) in self._participant_widgets.items():
            share = shares_by_user.get(uid)
            check.blockSignals(True)
            pct.blockSignals(True)
            if share:
                check.setChecked(True)
                pct.setValue(float(share[DBExpenseSharesColumns.PERCENTAGE.value]) * 100.0)
            else:
                check.setChecked(False)
                pct.setValue(0.0)
            check.blockSignals(False)
            pct.blockSignals(False)

        self._recompute_amounts()
        self._rebuild_settle_area(shares)

    def _recompute_amounts(self):
        total = self._total()
        for _uid, (check, pct, amount_label) in self._participant_widgets.items():
            pct.setEnabled(check.isChecked())
            value = total * (pct.value() / 100.0) if check.isChecked() else 0.0
            amount_label.setText(f"{value:.2f} €")

    def _rebuild_settle_area(self, shares):
        while self.settle_container.count():
            item = self.settle_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        advancer = self.expense.get(DBExpensesColumns.ADVANCED_BY_USER_ID.value)
        names = {u[DBUsersColumns.ID.value]: self._user_name(u) for u in self.users}

        debtor_shares = [
            s for s in shares
            if s[DBExpenseSharesColumns.USER_ID.value] != advancer
        ]
        if not debtor_shares:
            hint = QLabel("Salva le quote per gestire i rimborsi.")
            hint.setStyleSheet("color: palette(mid);")
            self.settle_container.addWidget(hint)
            return

        for share in debtor_shares:
            self.settle_container.addWidget(self._settle_row(share, names))

    def _settle_row(self, share, names) -> QFrame:
        row = QFrame()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        uid = share[DBExpenseSharesColumns.USER_ID.value]
        amount = share[DBExpenseSharesColumns.AMOUNT.value]
        settled = bool(share[DBExpenseSharesColumns.IS_SETTLED.value])
        share_id = share[DBExpenseSharesColumns.ID.value]

        text = f"{names.get(uid, 'Utente')} deve {amount:.2f} €"
        label = QLabel(text)
        if settled:
            label.setText(f"{names.get(uid, 'Utente')} — {amount:.2f} € · SALDATO")
            label.setStyleSheet("color: #2e7d57;")
        layout.addWidget(label, stretch=1)

        btn = QPushButton("Segna non saldata" if settled else "Segna saldata")
        btn.clicked.connect(lambda _=False, sid=share_id, st=settled: self._toggle_settle(sid, st))
        layout.addWidget(btn)
        return row

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _on_equal_split(self):
        selected = [uid for uid, (c, _p, _a) in self._participant_widgets.items() if c.isChecked()]
        if not selected:
            QMessageBox.warning(self, "Quote", "Seleziona almeno un partecipante.")
            return
        pct = 100.0 / len(selected)
        for uid, (check, spin, _a) in self._participant_widgets.items():
            spin.blockSignals(True)
            spin.setValue(pct if check.isChecked() else 0.0)
            spin.blockSignals(False)
        self._recompute_amounts()

    def _on_save(self):
        shares = {
            uid: spin.value() / 100.0
            for uid, (check, spin, _a) in self._participant_widgets.items()
            if check.isChecked()
        }
        if not shares:
            QMessageBox.warning(self, "Quote", "Seleziona almeno un partecipante.")
            return

        advancer_id = self.advancer_combo.currentData()
        if advancer_id not in shares:
            QMessageBox.warning(self, "Quote", "L'anticipatore deve essere tra i partecipanti.")
            return

        ok, msg = self.refund_controller.set_shares(self.expense_id, shares, self._total())
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return

        self.expense_controller.update_expense(self.expense_id, {
            DBExpensesColumns.IS_SHARED.value: 1,
            DBExpensesColumns.ADVANCED_BY_USER_ID.value: int(advancer_id),
        })
        self.expense[DBExpensesColumns.ADVANCED_BY_USER_ID.value] = int(advancer_id)
        self.expense[DBExpensesColumns.IS_SHARED.value] = 1

        self.load()
        if self.on_changed:
            self.on_changed()

    def _toggle_settle(self, share_id, currently_settled):
        if currently_settled:
            ok, msg = self.refund_controller.mark_share_unsettled(share_id)
        else:
            ok, msg = self.refund_controller.mark_share_settled(share_id)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return
        self.load()
        if self.on_changed:
            self.on_changed()
