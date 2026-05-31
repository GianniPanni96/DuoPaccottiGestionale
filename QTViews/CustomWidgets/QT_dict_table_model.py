"""Table model generico configurato a colonne, condiviso dalle list view.

Ogni riga e' un dict; ogni ``Column`` mappa una chiave del dict a una
colonna con header, formatter di visualizzazione, allineamento e chiave di
ordinamento (Qt.UserRole)."""

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QAbstractTableModel, Qt


@dataclass
class Column:
    header: str
    key: str
    formatter: Callable = lambda v: "" if v is None else str(v)
    align: int = int(Qt.AlignLeft | Qt.AlignVCenter)
    sort_key: Callable = None


class DictTableModel(QAbstractTableModel):
    def __init__(self, rows: list, columns: list, parent=None):
        super().__init__(parent)
        self._rows = rows or []
        self._columns = columns

    # --- dimensioni ---
    def rowCount(self, parent=None):
        return len(self._rows)

    def columnCount(self, parent=None):
        return len(self._columns)

    # --- header ---
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section].header
        return None

    # --- dati ---
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = self._columns[index.column()]
        value = row.get(col.key)

        if role == Qt.DisplayRole:
            return col.formatter(value)
        if role == Qt.UserRole:
            return col.sort_key(value) if col.sort_key else value
        if role == Qt.TextAlignmentRole:
            return col.align
        return None

    # --- helpers ---
    def row_dict(self, source_row: int):
        if 0 <= source_row < len(self._rows):
            return self._rows[source_row]
        return None
