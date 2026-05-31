"""Dialog di creazione manuale di una spesa.

Se 'Spesa condivisa' e' attiva mostra la selezione dei partecipanti e
l'anticipatore; le quote vengono create eque (modificabili poi dal
dettaglio)."""

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QGroupBox,
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
    DBUsersColumns,
    ExpenseSource,
    PaymentMethod,
    Visibility,
)

if TYPE_CHECKING:
    from App_context import AppContext

_AMOUNT_RE = re.compile(r"^\d+(\.\d{1,2})?$")
_IVA_RATES = ["0.22", "0.10", "0.05", "0.04", "0.00"]


class QTExpenseCreateView(QDialog):
    def __init__(self, app_context: "AppContext", owner_user_id: int, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.owner_user_id = owner_user_id
        self.expense_controller = app_context.expense_controller
        self.users = app_context.users_query_service.retrieve_users_map_list()
        self.created_expense_id = None

        self.setWindowTitle("Aggiungi spesa")
        self.setModal(True)
        self.resize(520, 720)
        self._participant_checks = {}
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, stretch=1)
        container = QWidget()
        scroll.setWidget(container)

        form = QFormLayout(container)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(8)

        self.description_edit = QLineEdit()
        form.addRow("Descrizione:", self.description_edit)

        self.category_combo = QComboBox()
        for key, label in self.app_context.catalogs_manager.get_section("expense_categories").items():
            if key == "ADD_CATEGORY":
                continue
            self.category_combo.addItem(label, key)
        form.addRow("Categoria:", self.category_combo)

        self.merchant_edit = QLineEdit()
        form.addRow("Esercente:", self.merchant_edit)

        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("es. 49.90")
        form.addRow("Importo totale (€):", self.amount_edit)

        self.iva_combo = QComboBox()
        for rate in _IVA_RATES:
            self.iva_combo.addItem(f"{int(float(rate) * 100)}%", rate)
        default_iva = self.app_context.app_settings_manager.get_default_iva()
        idx = self.iva_combo.findData(default_iva)
        if idx >= 0:
            self.iva_combo.setCurrentIndex(idx)
        form.addRow("Aliquota IVA:", self.iva_combo)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Data:", self.date_edit)

        self.payment_combo = QComboBox()
        self.payment_combo.addItems([m.value for m in PaymentMethod])
        self.payment_combo.setCurrentText(self.app_context.app_settings_manager.get_default_payment_method())
        form.addRow("Metodo di pagamento:", self.payment_combo)

        self.visibility_combo = QComboBox()
        self.visibility_combo.addItems([v.value for v in Visibility])
        self.visibility_combo.setCurrentText(self.app_context.app_settings_manager.get_default_visibility())
        form.addRow("Visibilità:", self.visibility_combo)

        self.note_edit = QLineEdit()
        form.addRow("Note:", self.note_edit)

        # Sezione condivisione
        self.shared_check = QCheckBox("Spesa condivisa")
        self.shared_check.toggled.connect(self._on_shared_toggled)
        form.addRow("", self.shared_check)

        self.shared_box = self._build_shared_box()
        self.shared_box.setVisible(False)
        form.addRow(self.shared_box)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        save_btn = QPushButton("Salva spesa")
        save_btn.setMinimumSize(140, 38)
        save_btn.clicked.connect(self._save)
        bottom.addWidget(save_btn)
        bottom.addStretch(1)
        outer.addLayout(bottom)

    def _build_shared_box(self) -> QGroupBox:
        box = QGroupBox("Condivisione")
        layout = QVBoxLayout(box)

        layout.addWidget(QLabel("Partecipanti (quote eque, modificabili dal dettaglio):"))
        for user in self.users:
            uid = user[DBUsersColumns.ID.value]
            check = QCheckBox(f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}")
            if uid == self.owner_user_id:
                check.setChecked(True)
            layout.addWidget(check)
            self._participant_checks[uid] = check

        advancer_row = QHBoxLayout()
        advancer_row.addWidget(QLabel("Anticipata da:"))
        self.advancer_combo = QComboBox()
        for user in self.users:
            self.advancer_combo.addItem(
                f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}",
                user[DBUsersColumns.ID.value],
            )
        adv_idx = self.advancer_combo.findData(self.owner_user_id)
        if adv_idx >= 0:
            self.advancer_combo.setCurrentIndex(adv_idx)
        advancer_row.addWidget(self.advancer_combo, stretch=1)
        layout.addLayout(advancer_row)
        return box

    def _on_shared_toggled(self, checked):
        self.shared_box.setVisible(checked)

    def _save(self):
        description = self.description_edit.text().strip()
        if not description:
            QMessageBox.warning(self, "Validazione", "La descrizione e' obbligatoria.")
            return
        amount = self.amount_edit.text().strip()
        if not _AMOUNT_RE.fullmatch(amount):
            QMessageBox.warning(self, "Validazione", "Importo non valido (es. 49.90).")
            return

        data = {
            E.DESCRIPTION.value: description,
            E.USER_ID.value: self.owner_user_id,
            E.CATEGORY.value: self.category_combo.currentData(),
            E.MERCHANT.value: self.merchant_edit.text().strip(),
            E.TOTAL_AMOUNT.value: amount,
            E.DATE.value: self.date_edit.date().toString("yyyy-MM-dd"),
            E.PAYMENT_METHOD.value: self.payment_combo.currentText(),
            E.VISIBILITY.value: self.visibility_combo.currentText(),
            E.NOTE.value: self.note_edit.text().strip(),
            E.SOURCE.value: ExpenseSource.MANUALE.value,
            "_iva_rate": self.iva_combo.currentData(),
        }

        if self.shared_check.isChecked():
            participants = [uid for uid, c in self._participant_checks.items() if c.isChecked()]
            advancer = self.advancer_combo.currentData()
            if not participants:
                QMessageBox.warning(self, "Validazione", "Seleziona almeno un partecipante.")
                return
            if advancer not in participants:
                QMessageBox.warning(self, "Validazione", "L'anticipatore deve essere tra i partecipanti.")
                return
            data[E.IS_SHARED.value] = True
            data[E.ADVANCED_BY_USER_ID.value] = advancer
            data["_participants"] = participants

        ok, msg, expense_id = self.expense_controller.save_expense(data)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return
        self.created_expense_id = expense_id
        self.accept()
