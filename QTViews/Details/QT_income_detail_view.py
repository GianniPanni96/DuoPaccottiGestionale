"""Dettaglio entrata: modifica campi + eliminazione."""

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import DBIncomesColumns as I, Visibility

if TYPE_CHECKING:
    from App_context import AppContext

_AMOUNT_RE = re.compile(r"^\d+(\.\d{1,2})?$")


class QTIncomeDetailView(QWidget):
    def __init__(self, app_context: "AppContext", income_id: int, on_back=None, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.income_id = income_id
        self.on_back = on_back
        self.income_controller = app_context.income_controller

        self.income = app_context.incomes_query_service.retrieve_income_map_by_id(income_id)
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
        delete_btn = QPushButton("Elimina entrata")
        delete_btn.clicked.connect(self._delete)
        header.addWidget(delete_btn)
        root.addLayout(header)

        if not self.income:
            root.addWidget(QLabel("Entrata non trovata."))
            return

        form = QFormLayout()
        self.description_edit = QLineEdit(self.income.get(I.DESCRIPTION.value, ""))
        form.addRow("Descrizione:", self.description_edit)

        self.category_combo = QComboBox()
        for key, label in self.app_context.catalogs_manager.get_section("income_categories").items():
            if key == "ADD_CATEGORY":
                continue
            self.category_combo.addItem(label, key)
        idx = self.category_combo.findData(self.income.get(I.CATEGORY.value))
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        form.addRow("Categoria:", self.category_combo)

        self.amount_edit = QLineEdit(f"{float(self.income.get(I.AMOUNT.value) or 0):.2f}")
        form.addRow("Importo (€):", self.amount_edit)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        parsed_date = QDate.fromString((self.income.get(I.DATE.value) or "")[:10], "yyyy-MM-dd")
        self.date_edit.setDate(parsed_date if parsed_date.isValid() else QDate.currentDate())
        form.addRow("Data:", self.date_edit)

        self.visibility_combo = QComboBox()
        self.visibility_combo.addItems([v.value for v in Visibility])
        if self.income.get(I.VISIBILITY.value):
            self.visibility_combo.setCurrentText(self.income[I.VISIBILITY.value])
        form.addRow("Visibilità:", self.visibility_combo)

        self.note_edit = QLineEdit(self.income.get(I.NOTE.value) or "")
        form.addRow("Note:", self.note_edit)
        root.addLayout(form)

        save_btn = QPushButton("Salva modifiche")
        save_btn.clicked.connect(self._save)
        root.addWidget(save_btn)
        root.addStretch(1)

    def _save(self):
        description = self.description_edit.text().strip()
        if not description:
            QMessageBox.warning(self, "Validazione", "La descrizione e' obbligatoria.")
            return
        amount_text = self.amount_edit.text().strip()
        if not _AMOUNT_RE.fullmatch(amount_text):
            QMessageBox.warning(self, "Validazione", "Importo non valido (es. 1500.00).")
            return

        updates = {
            I.DESCRIPTION.value: description,
            I.CATEGORY.value: self.category_combo.currentData(),
            I.AMOUNT.value: float(amount_text),
            I.DATE.value: self.date_edit.date().toString("yyyy-MM-dd"),
            I.VISIBILITY.value: self.visibility_combo.currentText(),
            I.NOTE.value: self.note_edit.text().strip(),
        }
        ok, msg = self.income_controller.update_income(self.income_id, updates)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return
        QMessageBox.information(self, "Salvato", "Entrata aggiornata.")

    def _delete(self):
        confirm = QMessageBox.question(
            self, "Elimina", "Eliminare questa entrata?", QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        ok, msg = self.income_controller.delete_income(self.income_id)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return
        if self.on_back:
            self.on_back()
