"""Tab Analisi: le 4 analisi del SCOPO (grafici matplotlib + tabelle).

1. Spese annuali per utente x categoria (selettore anno)
2. Spese mensili per utente x categoria (selettore mese/anno)
3. Media mensile delle spese per categoria (anno corrente)
4. Rimborsi: chi-deve-a-chi

I dati arrivano dagli analyzer e quindi rispettano il filtro di
visibilita' dell'utente loggato."""

from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import DBUsersColumns
from QTViews.CustomWidgets.QT_mpl_canvas import MplCanvas

if TYPE_CHECKING:
    from App_context import AppContext

_MONTHS = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]
_YEARS_BACK = 5


class QTAnalysisView(QWidget):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.expense_analyzer = app_context.expense_analyzer_service
        self.refund_analyzer = app_context.refund_analyzer_service
        self.users_query = app_context.users_query_service
        self._cat_labels = dict(app_context.catalogs_manager.get_section("expense_categories"))

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _user_name(self, uid):
        user = self.users_query.retrieve_user_map_by_id(uid)
        if user:
            return f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"
        return f"Utente {uid}"

    def _cat_label(self, key):
        return self._cat_labels.get(key, key)

    def _named_grouped(self, data_by_uid):
        """{uid:{cat_key:val}} -> {user_name:{cat_label:val}}."""
        out = {}
        for uid, cats in data_by_uid.items():
            out[self._user_name(uid)] = {self._cat_label(k): v for k, v in cats.items()}
        return out

    @staticmethod
    def _make_year_combo() -> QComboBox:
        combo = QComboBox()
        current = datetime.now().year
        for y in range(current, current - _YEARS_BACK, -1):
            combo.addItem(str(y), y)
        return combo

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        self.inner_tabs = QTabWidget()
        root.addWidget(self.inner_tabs)

        self.inner_tabs.addTab(self._build_annual_tab(), "Annuale per categoria")
        self.inner_tabs.addTab(self._build_monthly_tab(), "Mensile per categoria")
        self.inner_tabs.addTab(self._build_average_tab(), "Media mensile")
        self.inner_tabs.addTab(self._build_refund_tab(), "Rimborsi")

    def _build_annual_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Anno:"))
        self.annual_year_combo = self._make_year_combo()
        self.annual_year_combo.currentIndexChanged.connect(self._refresh_annual)
        controls.addWidget(self.annual_year_combo)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.annual_canvas = MplCanvas()
        layout.addWidget(self.annual_canvas, stretch=2)
        self.annual_table = QTableWidget()
        layout.addWidget(self.annual_table, stretch=1)
        return page

    def _build_monthly_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Mese:"))
        self.monthly_month_combo = QComboBox()
        for i, m in enumerate(_MONTHS, start=1):
            self.monthly_month_combo.addItem(m, i)
        self.monthly_month_combo.setCurrentIndex(datetime.now().month - 1)
        self.monthly_month_combo.currentIndexChanged.connect(self._refresh_monthly)
        controls.addWidget(self.monthly_month_combo)
        controls.addWidget(QLabel("Anno:"))
        self.monthly_year_combo = self._make_year_combo()
        self.monthly_year_combo.currentIndexChanged.connect(self._refresh_monthly)
        controls.addWidget(self.monthly_year_combo)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.monthly_canvas = MplCanvas()
        layout.addWidget(self.monthly_canvas, stretch=2)
        self.monthly_table = QTableWidget()
        layout.addWidget(self.monthly_table, stretch=1)
        return page

    def _build_average_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Anno:"))
        self.average_year_combo = self._make_year_combo()
        self.average_year_combo.currentIndexChanged.connect(self._refresh_average)
        controls.addWidget(self.average_year_combo)
        controls.addStretch(1)
        layout.addLayout(controls)
        hint = QLabel("Media mensile = totale categoria / mesi trascorsi nell'anno.")
        hint.setStyleSheet("color: palette(mid);")
        layout.addWidget(hint)

        self.average_canvas = MplCanvas()
        layout.addWidget(self.average_canvas, stretch=2)
        self.average_table = QTableWidget()
        layout.addWidget(self.average_table, stretch=1)
        return page

    def _build_refund_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Saldi tra utenti (spese condivise non saldate)")
        f = title.font()
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)
        self.refund_table = QTableWidget()
        layout.addWidget(self.refund_table, stretch=1)
        self.refund_summary = QLabel("")
        self.refund_summary.setStyleSheet("color: palette(mid);")
        layout.addWidget(self.refund_summary)
        return page

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self):
        self._refresh_annual()
        self._refresh_monthly()
        self._refresh_average()
        self._refresh_refund()

    def _refresh_annual(self):
        year = self.annual_year_combo.currentData()
        data = self._named_grouped(self.expense_analyzer.annual_by_user_and_category(year=year))
        self._draw_grouped_bars(self.annual_canvas, data, f"Spese {year} per categoria")
        self._fill_user_category_table(self.annual_table, data)

    def _refresh_monthly(self):
        month = self.monthly_month_combo.currentData()
        year = self.monthly_year_combo.currentData()
        data = self._named_grouped(
            self.expense_analyzer.monthly_by_user_and_category(month=month, year=year)
        )
        self._draw_grouped_bars(self.monthly_canvas, data, f"{_MONTHS[month - 1]} {year}")
        self._fill_user_category_table(self.monthly_table, data)

    def _refresh_average(self):
        year = self.average_year_combo.currentData()
        raw = self.expense_analyzer.monthly_average_by_category(year=year)
        data = {self._cat_label(k): v for k, v in raw.items()}
        self._draw_single_bars(self.average_canvas, data, f"Media mensile {year}")
        self._fill_single_table(self.average_table, data, "Categoria", "Media mensile")

    def _refresh_refund(self):
        rows = self.refund_analyzer.build_summary_rows()
        self.refund_table.clear()
        self.refund_table.setColumnCount(3)
        self.refund_table.setHorizontalHeaderLabels(["Deve", "A", "Importo"])
        self.refund_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.refund_table.setItem(r, 0, QTableWidgetItem(row["debtor_name"]))
            self.refund_table.setItem(r, 1, QTableWidgetItem(row["creditor_name"]))
            self.refund_table.setItem(r, 2, QTableWidgetItem(f"{row['amount']:.2f} €"))
        self.refund_table.resizeColumnsToContents()
        if rows:
            self.refund_summary.setText(f"{len(rows)} saldo/i in sospeso.")
        else:
            self.refund_summary.setText("Nessun rimborso in sospeso: tutto saldato.")

    # ------------------------------------------------------------------
    # Disegno grafici
    # ------------------------------------------------------------------

    def _draw_grouped_bars(self, canvas: MplCanvas, data_by_user: dict, title: str):
        categories = sorted({c for cats in data_by_user.values() for c in cats})
        users = list(data_by_user.keys())
        if not categories or not users:
            canvas.draw_empty()
            return

        ax = canvas.reset_axes()
        x = np.arange(len(categories))
        n = len(users)
        width = 0.8 / n
        for i, user in enumerate(users):
            vals = [data_by_user[user].get(c, 0.0) for c in categories]
            ax.bar(x + i * width, vals, width, label=user)
        ax.set_xticks(x + width * (n - 1) / 2)
        ax.set_xticklabels(categories, rotation=30, ha="right", fontsize=8)
        ax.set_ylabel("€")
        ax.set_title(title)
        ax.legend(fontsize=8)
        canvas.figure.tight_layout()
        canvas.draw()

    def _draw_single_bars(self, canvas: MplCanvas, data: dict, title: str):
        data = {k: v for k, v in data.items() if v}
        if not data:
            canvas.draw_empty()
            return
        ax = canvas.reset_axes()
        categories = list(data.keys())
        x = np.arange(len(categories))
        ax.bar(x, [data[c] for c in categories], 0.6, color="#2e7d57")
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=30, ha="right", fontsize=8)
        ax.set_ylabel("€")
        ax.set_title(title)
        canvas.figure.tight_layout()
        canvas.draw()

    # ------------------------------------------------------------------
    # Tabelle
    # ------------------------------------------------------------------

    def _fill_user_category_table(self, table: QTableWidget, data_by_user: dict):
        categories = sorted({c for cats in data_by_user.values() for c in cats})
        users = list(data_by_user.keys())
        table.clear()
        table.setColumnCount(1 + len(users) + 1)
        table.setHorizontalHeaderLabels(["Categoria"] + users + ["Totale"])
        table.setRowCount(len(categories))
        for r, cat in enumerate(categories):
            table.setItem(r, 0, QTableWidgetItem(cat))
            row_total = 0.0
            for c, user in enumerate(users, start=1):
                val = data_by_user[user].get(cat, 0.0)
                row_total += val
                table.setItem(r, c, QTableWidgetItem(f"{val:.2f}"))
            table.setItem(r, 1 + len(users), QTableWidgetItem(f"{row_total:.2f}"))
        table.resizeColumnsToContents()

    def _fill_single_table(self, table: QTableWidget, data: dict, key_header: str, val_header: str):
        table.clear()
        items = [(k, v) for k, v in data.items() if v]
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels([key_header, val_header])
        table.setRowCount(len(items))
        for r, (k, v) in enumerate(items):
            table.setItem(r, 0, QTableWidgetItem(k))
            table.setItem(r, 1, QTableWidgetItem(f"{v:.2f} €"))
        table.resizeColumnsToContents()
