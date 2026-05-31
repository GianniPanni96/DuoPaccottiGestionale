"""Dialog di creazione manuale di un'entrata."""

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Gestionale_Enums import (
    DBIncomesColumns as I,
    IncomeSource,
    Visibility,
)

if TYPE_CHECKING:
    from App_context import AppContext

_AMOUNT_RE = re.compile(r"^\d+(\.\d{1,2})?$")


class QTIncomeCreateView(QDialog):
    def __init__(self, app_context: "AppContext", owner_user_id: int, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.owner_user_id = owner_user_id
        self.income_controller = app_context.income_controller
        self.created_income_id = None

        self.setWindowTitle("Aggiungi entrata")
        self.setModal(True)
        self.resize(480, 420)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        form = QFormLayout()
        form.setSpacing(8)
        root.addLayout(form)

        self.description_edit = QLineEdit()
        form.addRow("Descrizione:", self.description_edit)

        self.category_combo = QComboBox()
        for key, label in self.app_context.catalogs_manager.get_section("income_categories").items():
            if key == "ADD_CATEGORY":
                continue
            self.category_combo.addItem(label, key)
        form.addRow("Categoria:", self.category_combo)

        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("es. 1500.00")
        form.addRow("Importo (€):", self.amount_edit)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Data:", self.date_edit)

        self.visibility_combo = QComboBox()
        self.visibility_combo.addItems([v.value for v in Visibility])
        self.visibility_combo.setCurrentText(self.app_context.app_settings_manager.get_default_visibility())
        form.addRow("Visibilità:", self.visibility_combo)

        self.note_edit = QLineEdit()
        form.addRow("Note:", self.note_edit)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        save_btn = QPushButton("Salva entrata")
        save_btn.setMinimumSize(140, 38)
        save_btn.clicked.connect(self._save)
        bottom.addWidget(save_btn)
        bottom.addStretch(1)
        root.addLayout(bottom)

    def _save(self):
        description = self.description_edit.text().strip()
        if not description:
            QMessageBox.warning(self, "Validazione", "La descrizione e' obbligatoria.")
            return
        amount = self.amount_edit.text().strip()
        if not _AMOUNT_RE.fullmatch(amount):
            QMessageBox.warning(self, "Validazione", "Importo non valido (es. 1500.00).")
            return

        data = {
            I.DESCRIPTION.value: description,
            I.USER_ID.value: self.owner_user_id,
            I.CATEGORY.value: self.category_combo.currentData(),
            I.AMOUNT.value: amount,
            I.DATE.value: self.date_edit.date().toString("yyyy-MM-dd"),
            I.VISIBILITY.value: self.visibility_combo.currentText(),
            I.NOTE.value: self.note_edit.text().strip(),
            I.SOURCE.value: IncomeSource.MANUALE.value,
        }
        ok, msg, income_id = self.income_controller.save_income(data)
        if not ok:
            QMessageBox.critical(self, "Errore", msg)
            return
        self.created_income_id = income_id
        self.accept()
