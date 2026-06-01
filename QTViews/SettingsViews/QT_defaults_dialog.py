"""Dialog 'Default utente': aliquota IVA, metodo di pagamento e visibilita'
predefiniti per le nuove spese/entrate. Persiste via ``app_settings_manager``."""

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
)

from Gestionale_Enums import PaymentMethod, Visibility

if TYPE_CHECKING:
    from App_context import AppContext

_IVA_RATES = ["0.22", "0.10", "0.05", "0.04", "0.00"]


class QTDefaultsDialog(QDialog):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_settings = app_context.app_settings_manager

        self.setWindowTitle("Default utente")
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.iva_combo = QComboBox()
        for rate in _IVA_RATES:
            self.iva_combo.addItem(f"{int(float(rate) * 100)}%", rate)
        idx = self.iva_combo.findData(self.app_settings.get_default_iva())
        if idx >= 0:
            self.iva_combo.setCurrentIndex(idx)
        form.addRow("Aliquota IVA predefinita:", self.iva_combo)

        self.payment_combo = QComboBox()
        self.payment_combo.addItems([m.value for m in PaymentMethod])
        self.payment_combo.setCurrentText(self.app_settings.get_default_payment_method())
        form.addRow("Metodo di pagamento:", self.payment_combo)

        self.visibility_combo = QComboBox()
        self.visibility_combo.addItems([v.value for v in Visibility])
        self.visibility_combo.setCurrentText(self.app_settings.get_default_visibility())
        form.addRow("Visibilita' predefinita:", self.visibility_combo)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Salva")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _save(self):
        self.app_settings.set_default("default_iva", self.iva_combo.currentData())
        self.app_settings.set_default("default_payment_method", self.payment_combo.currentText())
        self.app_settings.set_default("default_visibility", self.visibility_combo.currentText())
        self.accept()
