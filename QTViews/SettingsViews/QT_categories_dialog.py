"""Gestione dei cataloghi categorie (spese ed entrate) dal menu 'Categorie'.

CRUD sulle voci ``key -> label`` tramite ``catalogs_manager``. La voce
trigger 'AGGIUNGI…' viene nascosta e mantenuta in coda dal manager."""

import re
import unicodedata
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from App_context import AppContext

_TRIGGER_KEY = "ADD_CATEGORY"
_SECTIONS = [
    ("Categorie spese", "expense_categories"),
    ("Categorie entrate", "income_categories"),
]


def _slugify(label: str) -> str:
    normalized = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_").upper()
    return slug or "CATEGORIA"


class QTCategoriesDialog(QDialog):
    def __init__(self, app_context: "AppContext", on_changed=None, parent=None):
        super().__init__(parent)
        self.catalogs_manager = app_context.catalogs_manager
        self.on_changed = on_changed
        self.changed = False

        self.setWindowTitle("Gestisci categorie")
        self.setModal(True)
        self.resize(420, 480)
        self._build_ui()
        self._reload_list()

    def _build_ui(self):
        root = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Catalogo:"))
        self.section_combo = QComboBox()
        for label, key in _SECTIONS:
            self.section_combo.addItem(label, key)
        self.section_combo.currentIndexChanged.connect(self._reload_list)
        row.addWidget(self.section_combo, stretch=1)
        root.addLayout(row)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(lambda _i: self._rename())
        root.addWidget(self.list_widget, stretch=1)

        buttons = QHBoxLayout()
        add_btn = QPushButton("Aggiungi")
        add_btn.clicked.connect(self._add)
        rename_btn = QPushButton("Rinomina")
        rename_btn.clicked.connect(self._rename)
        delete_btn = QPushButton("Elimina")
        delete_btn.clicked.connect(self._delete)
        buttons.addWidget(add_btn)
        buttons.addWidget(rename_btn)
        buttons.addWidget(delete_btn)
        buttons.addStretch(1)
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

    # ------------------------------------------------------------------

    def _section_key(self) -> str:
        return self.section_combo.currentData()

    def _current_items(self) -> dict:
        return self.catalogs_manager.get_section(self._section_key())

    def _reload_list(self):
        self.list_widget.clear()
        for key, label in self._current_items().items():
            if key == _TRIGGER_KEY:
                continue
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self.list_widget.addItem(item)

    def _selected(self):
        item = self.list_widget.currentItem()
        if item is None:
            return None, None
        return item.data(Qt.UserRole), item.text()

    def _apply(self, key, value=None, operation="update"):
        self.catalogs_manager.update_list_field(self._section_key(), key, value, operation)
        self.changed = True
        if self.on_changed is not None:
            self.on_changed()
        self._reload_list()

    def _add(self):
        label, ok = QInputDialog.getText(self, "Nuova categoria", "Nome della categoria:")
        label = (label or "").strip()
        if not ok or not label:
            return
        existing = self._current_items()
        key = _slugify(label)
        base, n = key, 2
        while key in existing:
            key = f"{base}_{n}"
            n += 1
        self._apply(key, label, "update")

    def _rename(self):
        key, current = self._selected()
        if key is None:
            QMessageBox.information(self, "Categorie", "Seleziona una categoria.")
            return
        label, ok = QInputDialog.getText(self, "Rinomina categoria", "Nuovo nome:", text=current)
        label = (label or "").strip()
        if not ok or not label or label == current:
            return
        self._apply(key, label, "update")

    def _delete(self):
        key, current = self._selected()
        if key is None:
            QMessageBox.information(self, "Categorie", "Seleziona una categoria.")
            return
        confirm = QMessageBox.question(
            self, "Elimina categoria",
            f"Eliminare la categoria «{current}»?\n"
            "Le spese/entrate gia' salvate con questa categoria non vengono modificate.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self._apply(key, operation="delete")
