"""Dettaglio spesa: modifica campi + editor delle quote condivise +
eliminazione. Mostrato in uno stack dentro la tab Spese."""

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import (
    DBExpensesColumns as E,
    PaymentMethod,
    Visibility,
)
from QTViews.CustomWidgets.QT_expense_shares_editor import QTExpenseSharesEditor

if TYPE_CHECKING:
    from App_context import AppContext

_AMOUNT_RE = re.compile(r"^\d+(\.\d{1,2})?$")


class QTExpenseDetailView(QWidget):
    def __init__(self, app_context: "AppContext", expense_id: int, on_back=None, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.expense_id = expense_id
        self.on_back = on_back
        self.expense_controller = app_context.expense_controller

        self.expense = app_context.expenses_query_service.retrieve_expense_map_by_id(expense_id)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        self.back_button = QPushButton("← Torna alla lista")
        self.back_button.clicked.connect(lambda: self.on_back() if self.on_back else None)
        header.addWidget(self.back_button)
        header.addStretch(1)
        delete_btn = QPushButton("Elimina spesa")
        delete_btn.clicked.connect(self._delete)
        header.addWidget(delete_btn)
        root.addLayout(header)

        if not self.expense:
            root.addWidget(QLabel("Spesa non trovata."))
            return

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, stretch=1)
        container = QWidget()
        scroll.setWidget(container)
        body = QVBoxLayout(container)
        body.setContentsMargins(8, 8, 8, 8)
        body.setSpacing(14)

        form = QFormLayout()
        self.description_edit = QLineEdit(self.expense.get(E.DESCRIPTION.value, ""))
        form.addRow("Descrizione:", self.description_edit)

        self.category_combo = QComboBox()
        for key, label in self.app_context.catalogs_manager.get_section("expense_categories").items():
            if key == "ADD_CATEGORY":
                continue
            self.category_combo.addItem(label, key)
        idx = self.category_combo.findData(self.expense.get(E.CATEGORY.value))
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        form.addRow("Categoria:", self.category_combo)

        self.merchant_edit = QLineEdit(self.expense.get(E.MERCHANT.value) or "")
        form.addRow("Esercente:", self.merchant_edit)

        self.amount_edit = QLineEdit(f"{float(self.expense.get(E.TOTAL_AMOUNT.value) or 0):.2f}")
        form.addRow("Importo totale (€):", self.amount_edit)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        parsed_date = QDate.fromString((self.expense.get(E.DATE.value) or "")[:10], "yyyy-MM-dd")
        self.date_edit.setDate(parsed_date if parsed_date.isValid() else QDate.currentDate())
        form.addRow("Data:", self.date_edit)

        self.payment_combo = QComboBox()
        self.payment_combo.addItems([m.value for m in PaymentMethod])
        if self.expense.get(E.PAYMENT_METHOD.value):
            self.payment_combo.setCurrentText(self.expense[E.PAYMENT_METHOD.value])
        form.addRow("Metodo di pagamento:", self.payment_combo)

        self.visibility_combo = QComboBox()
        self.visibility_combo.addItems([v.value for v in Visibility])
        if self.expense.get(E.VISIBILITY.value):
            self.visibility_combo.setCurrentText(self.expense[E.VISIBILITY.value])
        form.addRow("Visibilità:", self.visibility_combo)

        self.note_edit = QLineEdit(self.expense.get(E.NOTE.value) or "")
        form.addRow("Note:", self.note_edit)
        body.addLayout(form)

        save_btn = QPushButton("Salva modifiche")
        save_btn.clicked.connect(self._save)
        body.addWidget(save_btn)

        title = QLabel("Condivisione e rimborsi")
        f = title.font()
        f.setBold(True)
        f.setPointSize(12)
        title.setFont(f)
        body.addWidget(title)

        self.shares_editor = QTExpenseSharesEditor(
            self.app_context, self.expense, on_changed=self._on_shares_changed
        )
        body.addWidget(self.shares_editor)
        body.addStretch(1)

    def _save(self):
        description = self.description_edit.text().strip()
        if not description:
            QMessageBox.warning(self, "Validazione", "La descrizione e' obbligatoria.")
            return
        amount_text = self.amount_edit.text().strip()
        if not _AMOUNT_RE.fullmatch(amount_text):
            QMessageBox.warning(self, "Validazione", "Importo non valido (es. 49.90).")
            return

        total = float(amount_text)
        net, iva = self._split_net_iva(total)
        updates = {
            E.DESCRIPTION.value: description,
            E.CATEGORY.value: self.category_combo.currentData(),
            E.MERCHANT.value: self.merchant_edit.text().strip(),
            E.TOTAL_AMOUNT.value: total,
            E.NET_AMOUNT.value: net,
            E.IVA_AMOUNT.value: iva,
            E.DATE.value: self.date_edit.date().toString("yyyy-MM-dd"),
            E.PAYMENT_METHOD.value: self.payment_combo.currentText(),
            E.VISIBILITY.value: self.visibility_combo.currentText(),
            E.NOTE.value: self.note_edit.text().strip(),
        }
        ok, msg = self.expense_controller.update_expense(self.expense_id, updates)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return

        # Se l'importo e' cambiato e la spesa e' condivisa, risincronizza
        # gli importi delle quote mantenendo le percentuali.
        self.expense = self.app_context.expenses_query_service.retrieve_expense_map_by_id(self.expense_id)
        if self.expense.get(E.IS_SHARED.value):
            shares = self.app_context.expense_shares_query_service.retrieve_shares_for_expense(self.expense_id)
            from Gestionale_Enums import DBExpenseSharesColumns as S
            pct = {s[S.USER_ID.value]: s[S.PERCENTAGE.value] for s in shares}
            if pct:
                self.app_context.refund_controller.set_shares(self.expense_id, pct, total)
        self.shares_editor.expense = self.expense
        self.shares_editor.load()
        QMessageBox.information(self, "Salvato", "Spesa aggiornata.")

    def _split_net_iva(self, total):
        try:
            rate = float(self.app_context.app_settings_manager.get_default_iva())
        except (TypeError, ValueError):
            rate = 0.0
        if rate <= 0:
            return round(total, 2), 0.0
        net = round(total / (1 + rate), 2)
        return net, round(total - net, 2)

    def _on_shares_changed(self):
        self.expense = self.app_context.expenses_query_service.retrieve_expense_map_by_id(self.expense_id)

    def _delete(self):
        confirm = QMessageBox.question(
            self, "Elimina", "Eliminare questa spesa?", QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        ok, msg = self.expense_controller.delete_expense(self.expense_id)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return
        if self.on_back:
            self.on_back()
