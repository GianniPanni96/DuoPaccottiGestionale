"""Base condivisa delle list view (Spese, Entrate).

Orchestrazione fissa: ``_setup_services -> _build_ui -> _reload_data``.
Le sottoclassi dichiarano ``COLUMNS`` e implementano i pochi hook di
dominio (fetch, build_rows, aggregati, creazione, eliminazione).

Usa QAbstractTableModel + QSortFilterProxyModel: la QTableView renderizza
solo le celle visibili. Il filtro temporale e' per anno (piu' naturale per
le finanze personali del nucleo)."""

from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from QTViews.CustomWidgets.QT_dict_table_model import DictTableModel

if TYPE_CHECKING:
    from App_context import AppContext


class QTBaseListView(QWidget):
    COLUMNS = ()
    AGGREGATE_KEYS = ()
    SEARCH_PLACEHOLDER = "Cerca in tutte le colonne…"
    ADD_BUTTON_TEXT = "Aggiungi"
    ITEM_LABEL_PLURAL = "elementi"
    YEAR_ALL_LABEL = "Tutte"
    YEARS_BACK = 5

    def __init__(self, app_context: "AppContext", on_open_detail=None, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.on_open_detail = on_open_detail

        self._source_model = None
        self._proxy = None
        self._aggregate_labels = {}

        self._setup_services(app_context)
        self._build_ui()
        self._reload_data()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 16, 12, 12)
        root.setSpacing(16)
        self._build_aggregates_bar(root)
        self._build_controls_bar(root)
        self._build_table(root)
        self._build_bottom_bar(root)

    def _build_aggregates_bar(self, root):
        if not self.AGGREGATE_KEYS:
            return
        bar = QHBoxLayout()
        bar.setSpacing(10)
        for key in self.AGGREGATE_KEYS:
            card = QFrame()
            card.setFrameShape(QFrame.StyledPanel)
            card.setStyleSheet(
                "QFrame { background-color: palette(alternate-base); border-radius: 6px; }"
            )
            box = QVBoxLayout(card)
            box.setContentsMargins(12, 8, 12, 8)
            title = QLabel(key)
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet(
                "background-color: palette(highlight); color: palette(highlighted-text);"
                " padding: 4px; border-radius: 4px;"
            )
            value = QLabel("0")
            value.setAlignment(Qt.AlignCenter)
            f = value.font()
            f.setPointSize(14)
            value.setFont(f)
            box.addWidget(title)
            box.addWidget(value)
            bar.addWidget(card)
            self._aggregate_labels[key] = value
        bar.addStretch(1)
        root.addLayout(bar)

    def _build_controls_bar(self, root):
        controls = QHBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(QLabel("Anno:"))
        self.year_combo = QComboBox()
        self.year_combo.addItem(self.YEAR_ALL_LABEL)
        current = datetime.now().year
        for y in range(current, current - self.YEARS_BACK, -1):
            self.year_combo.addItem(str(y))
        self.year_combo.setCurrentText(str(current))
        self.year_combo.currentIndexChanged.connect(self._reload_data)
        controls.addWidget(self.year_combo)

        for label, callback in self.extra_action_buttons():
            btn = QPushButton(label)
            btn.clicked.connect(callback)
            controls.addWidget(btn)

        controls.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(self.SEARCH_PLACEHOLDER)
        self.search_edit.textChanged.connect(self._apply_filter)
        controls.addWidget(self.search_edit, stretch=1)

        root.addLayout(controls)

    def _build_table(self, root):
        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        root.addWidget(self.table, stretch=1)

    def _build_bottom_bar(self, root):
        bottom = QHBoxLayout()
        self.add_button = QPushButton(self.ADD_BUTTON_TEXT)
        self.add_button.clicked.connect(self._on_add_item)
        bottom.addStretch(1)
        bottom.addWidget(self.add_button)
        bottom.addStretch(1)
        root.addLayout(bottom)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: palette(mid);")
        root.addWidget(self.status_label)

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def _current_year_filter(self):
        text = self.year_combo.currentText()
        if text == self.YEAR_ALL_LABEL:
            return -1
        try:
            return int(text)
        except ValueError:
            return -1

    def _reload_data(self):
        year = self._current_year_filter()
        items = self.fetch_items(year)
        rows = self.build_rows(items)
        self._source_model = DictTableModel(rows, list(self.COLUMNS))
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._source_model)
        self._proxy.setSortRole(Qt.UserRole)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)
        self.table.setModel(self._proxy)
        self._refresh_aggregates(year)
        self._apply_filter()
        self.status_label.setText(f"{len(rows)} {self.ITEM_LABEL_PLURAL}")

    def _apply_filter(self):
        if self._proxy is not None:
            self._proxy.setFilterFixedString(self.search_edit.text())

    def _refresh_aggregates(self, year):
        if not self._aggregate_labels:
            return
        values = self.compute_aggregates(year) or {}
        for key, label in self._aggregate_labels.items():
            if key in values:
                label.setText(str(values[key]))

    def _on_row_double_clicked(self, proxy_index):
        if not proxy_index.isValid() or self.on_open_detail is None or self._proxy is None:
            return
        row = self._row_for_proxy_index(proxy_index)
        if row is None:
            return
        item_id = self.id_for_row(row)
        if item_id is not None:
            self.on_open_detail(item_id)

    def _row_for_proxy_index(self, proxy_index):
        source_index = self._proxy.mapToSource(proxy_index)
        return self._source_model.row_dict(source_index.row())

    def _on_add_item(self):
        new_id = self.open_creator_dialog()
        if new_id is None:
            return
        self._reload_data()
        if self.on_open_detail is not None:
            self.on_open_detail(new_id)

    def _show_context_menu(self, pos):
        proxy_index = self.table.indexAt(pos)
        if not proxy_index.isValid() or self._proxy is None:
            return
        row = self._row_for_proxy_index(proxy_index)
        if row is None:
            return
        actions = self.context_menu_actions(row)
        if not actions:
            return
        menu = QMenu(self.table)
        for label, callback in actions:
            action = QAction(label, menu)
            action.triggered.connect(callback)
            menu.addAction(action)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def refresh(self):
        self._reload_data()

    # ------------------------------------------------------------------
    # Hook da implementare nelle sottoclassi
    # ------------------------------------------------------------------

    def _setup_services(self, app_context):
        return

    def fetch_items(self, year):
        raise NotImplementedError

    def build_rows(self, items):
        return items

    def compute_aggregates(self, year):
        return {}

    def id_for_row(self, row):
        return row.get("id")

    def open_creator_dialog(self):
        return None

    def extra_action_buttons(self):
        return []

    def context_menu_actions(self, row):
        return []
