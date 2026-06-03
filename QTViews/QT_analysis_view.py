"""Tab Analisi: le 4 analisi del SCOPO (grafici a torta + tabelle).

1. Spese annuali per utente x categoria — una torta per utente
2. Spese mensili per utente x categoria — una torta per utente
3. Media mensile delle spese per categoria — una torta
4. Rimborsi: chi-deve-a-chi, per finestra temporale navigabile

I dati arrivano dagli analyzer e quindi rispettano il filtro di
visibilita' dell'utente loggato. La view si sottoscrive a ``DATA_CHANGED``
sull'event bus e si auto-aggiorna quando l'utente modifica il database."""

from datetime import datetime
from itertools import groupby
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QStyledItemDelegate,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Event_bus import DATA_CHANGED
from Gestionale_Enums import DBUsersColumns
from QTViews.CustomWidgets.QT_mpl_canvas import InteractivePieCanvas
from Utils.Refund_window_utils import WINDOW_LABELS, window_bounds

if TYPE_CHECKING:
    from App_context import AppContext

_MONTHS = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]
_YEARS_BACK = 5

# Altezza minima della striscia dei grafici: la torta resta tonda e leggibile.
# L'area grafici occupa lo spazio in eccesso (stretch), mentre la tabella
# riassuntiva sotto si dimensiona sul proprio contenuto e resta ancorata in basso.
_CHART_MIN_HEIGHT = 280

# Colore del bordo evidenziato per le righe riassuntive dei rimborsi.
_RECAP_BORDER_COLOR = "#2e7d57"


class _TableLeaveFilter(QObject):
    """Event filter sul viewport di una QTableWidget: chiama ``on_leave``
    quando il mouse lascia la tabella, cosi' la view puo' cancellare
    l'highlighting sui pie chart corrispondenti."""

    def __init__(self, on_leave, parent=None):
        super().__init__(parent)
        self._on_leave = on_leave

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Leave:
            self._on_leave()
        return False


class _RecapBorderDelegate(QStyledItemDelegate):
    """Disegna un bordo evidenziato attorno alle righe riassuntive (totali)
    della tabella rimborsi. Le righe da evidenziare sono in ``recap_rows``."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recap_rows: set[int] = set()

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.row() not in self.recap_rows:
            return
        painter.save()
        pen = QPen(QColor(_RECAP_BORDER_COLOR))
        pen.setWidth(2)
        painter.setPen(pen)
        rect = option.rect
        # Linee orizzontali (top/bottom) per tutte le celle della riga.
        painter.drawLine(rect.topLeft(), rect.topRight())
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        # Bordi verticali solo agli estremi della riga.
        if index.column() == 0:
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
        if index.column() == index.model().columnCount() - 1:
            painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.restore()


class QTAnalysisView(QWidget):
    def __init__(self, app_context: "AppContext", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.expense_analyzer = app_context.expense_analyzer_service
        self.refund_analyzer = app_context.refund_analyzer_service
        self.users_query = app_context.users_query_service
        self.app_settings = app_context.app_settings_manager
        self.refund_controller = app_context.refund_controller
        self.catalogs_manager = app_context.catalogs_manager
        self._cat_labels = dict(self.catalogs_manager.get_section("expense_categories"))

        self._refund_offset = 0          # 0 = periodo corrente, <0 = precedenti
        self._refresh_pending = False

        # Canvas attivi per tab: aggiornati a ogni refresh, usati per
        # l'highlighting sincrono con l'hover sulla tabella.
        self._annual_canvases:  list[InteractivePieCanvas] = []
        self._monthly_canvases: list[InteractivePieCanvas] = []
        self._average_canvases: list[InteractivePieCanvas] = []

        # Event filter keep-alive (evita il GC).
        self._leave_filters: list = []

        self._build_ui()
        self.refresh()

        app_context.event_bus.subscribe(DATA_CHANGED, self._on_data_changed)

    # ------------------------------------------------------------------
    # Auto-refresh su modifica del DB
    # ------------------------------------------------------------------

    def _on_data_changed(self, _payload=None):
        # Deferimento + coalescing: un burst di modifiche (es. import batch o
        # il toggle di una quota mentre siamo dentro al suo signal handler)
        # produce un solo refresh, eseguito dopo che il gestore corrente e'
        # rientrato (evita di distruggere widget mentre emettono segnali).
        if self._refresh_pending:
            return
        self._refresh_pending = True
        QTimer.singleShot(0, self._do_deferred_refresh)

    def _do_deferred_refresh(self):
        self._refresh_pending = False
        self.refresh()

    # ------------------------------------------------------------------
    # Helpers dominio
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

    @staticmethod
    def _make_chart_toggle(on_changed) -> QComboBox:
        """Selettore tipo di grafico (torta/istogramma) per un tab."""
        combo = QComboBox()
        combo.addItem("Torta", "pie")
        combo.addItem("Istogramma", "bar")
        combo.currentIndexChanged.connect(on_changed)
        return combo

    @staticmethod
    def _fit_table_to_contents(table: QTableWidget):
        """Fissa l'altezza della tabella su quella dei suoi contenuti: la
        tabella si espande in verticale per mostrare tutte le righe senza mai
        scrollare, occupando solo lo spazio necessario ai figli."""
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.resizeRowsToContents()
        height = table.horizontalHeader().height() + 2 * table.frameWidth()
        for r in range(table.rowCount()):
            height += table.rowHeight(r)
        table.setFixedHeight(height)

    def _wire_table_hover(self, table: QTableWidget, canvases: list):
        """Abilita il mouse-tracking sulla tabella e collega i segnali per
        evidenziare le fette dei pie chart al passaggio del mouse sulle righe."""
        table.setMouseTracking(True)
        table.viewport().setMouseTracking(True)
        table.cellEntered.connect(
            lambda r, _c, t=table, cv=canvases: self._on_table_hover(r, t, cv)
        )
        leave_filter = _TableLeaveFilter(lambda cv=canvases: self._clear_pie_highlights(cv), table.viewport())
        table.viewport().installEventFilter(leave_filter)
        self._leave_filters.append(leave_filter)

    def _on_table_hover(self, row: int, table: QTableWidget, canvases: list):
        item = table.item(row, 0)
        label = item.text().strip() if item else None
        for canvas in canvases:
            if label is None or not canvas._labels:
                canvas.clear_highlight()
                continue
            try:
                idx = canvas._labels.index(label)
                canvas.highlight_label(idx)
            except ValueError:
                canvas.clear_highlight()

    @staticmethod
    def _clear_pie_highlights(canvases: list):
        for canvas in canvases:
            canvas.clear_highlight()

    @staticmethod
    def _style_table(table: QTableWidget):
        """Colonne larghe (riempiono la viewport), sola lettura, righe alte."""
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setMinimumSectionSize(90)
        table.verticalHeader().setDefaultSectionSize(28)

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
        controls.addWidget(QLabel("Grafico:"))
        self.annual_chart_combo = self._make_chart_toggle(self._refresh_annual)
        controls.addWidget(self.annual_chart_combo)
        layout.addLayout(controls)

        self.annual_charts_layout = self._build_pies_area(layout)
        self.annual_table = QTableWidget()
        self._style_table(self.annual_table)
        self._wire_table_hover(self.annual_table, self._annual_canvases)
        layout.addWidget(self.annual_table, stretch=0)
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
        controls.addWidget(QLabel("Grafico:"))
        self.monthly_chart_combo = self._make_chart_toggle(self._refresh_monthly)
        controls.addWidget(self.monthly_chart_combo)
        layout.addLayout(controls)

        self.monthly_charts_layout = self._build_pies_area(layout)
        self.monthly_table = QTableWidget()
        self._style_table(self.monthly_table)
        self._wire_table_hover(self.monthly_table, self._monthly_canvases)
        layout.addWidget(self.monthly_table, stretch=0)
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
        controls.addWidget(QLabel("Grafico:"))
        self.average_chart_combo = self._make_chart_toggle(self._refresh_average)
        controls.addWidget(self.average_chart_combo)
        layout.addLayout(controls)
        hint = QLabel("Media mensile = totale categoria / mesi trascorsi nell'anno.")
        hint.setStyleSheet("color: palette(mid);")
        layout.addWidget(hint)

        self.average_charts_layout = self._build_pies_area(layout)
        self.average_table = QTableWidget()
        self._style_table(self.average_table)
        self._wire_table_hover(self.average_table, self._average_canvases)
        layout.addWidget(self.average_table, stretch=0)
        return page

    def _build_refund_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)

        title = QLabel("Saldi tra utenti (spese condivise per finestra temporale)")
        f = title.font()
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        controls = QHBoxLayout()
        self.refund_window_label = QLabel("")
        self.refund_window_label.setStyleSheet("color: palette(mid);")
        controls.addWidget(self.refund_window_label)
        controls.addSpacing(16)

        self.refund_prev_btn = QPushButton("◀ Precedente")
        self.refund_prev_btn.clicked.connect(self._refund_prev)
        controls.addWidget(self.refund_prev_btn)
        self.refund_period_label = QLabel("")
        pf = self.refund_period_label.font()
        pf.setBold(True)
        self.refund_period_label.setFont(pf)
        self.refund_period_label.setAlignment(Qt.AlignCenter)
        self.refund_period_label.setMinimumWidth(220)
        controls.addWidget(self.refund_period_label)
        self.refund_next_btn = QPushButton("Successivo ▶")
        self.refund_next_btn.clicked.connect(self._refund_next)
        controls.addWidget(self.refund_next_btn)
        controls.addStretch(1)
        self.refund_toggle_all_btn = QPushButton("Segna tutti come saldati")
        self.refund_toggle_all_btn.clicked.connect(self._toggle_all)
        controls.addWidget(self.refund_toggle_all_btn)
        layout.addLayout(controls)

        self.refund_pending_banner = QLabel("")
        self.refund_pending_banner.setStyleSheet(
            "color: #b35900; background-color: palette(alternate-base);"
            " border: 1px solid #f7b267; border-radius: 4px; padding: 4px 8px;"
        )
        self.refund_pending_banner.setVisible(False)
        layout.addWidget(self.refund_pending_banner)

        self.refund_table = QTableWidget()
        self._style_table(self.refund_table)
        self.refund_recap_delegate = _RecapBorderDelegate(self.refund_table)
        self.refund_table.setItemDelegate(self.refund_recap_delegate)
        layout.addWidget(self.refund_table, stretch=1)

        self.refund_summary = QLabel("")
        sf = self.refund_summary.font()
        sf.setBold(True)
        self.refund_summary.setFont(sf)
        layout.addWidget(self.refund_summary)
        return page

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self):
        self._cat_labels = dict(self.catalogs_manager.get_section("expense_categories"))
        self._refresh_annual()
        self._refresh_monthly()
        self._refresh_average()
        self._refresh_refund()

    def _refresh_annual(self):
        year = self.annual_year_combo.currentData()
        data = self._named_grouped(self.expense_analyzer.annual_by_user_and_category(year=year))
        self._draw_user_charts(self.annual_charts_layout, data,
                               self.annual_chart_combo.currentData(), self._annual_canvases)
        self._fill_user_category_table(self.annual_table, data)

    def _refresh_monthly(self):
        month = self.monthly_month_combo.currentData()
        year = self.monthly_year_combo.currentData()
        data = self._named_grouped(
            self.expense_analyzer.monthly_by_user_and_category(month=month, year=year)
        )
        self._draw_user_charts(self.monthly_charts_layout, data,
                               self.monthly_chart_combo.currentData(), self._monthly_canvases)
        self._fill_user_category_table(self.monthly_table, data)

    def _refresh_average(self):
        year = self.average_year_combo.currentData()
        raw = self.expense_analyzer.monthly_average_by_category(year=year)
        data = {self._cat_label(k): v for k, v in raw.items()}
        self._draw_single_chart(
            self.average_charts_layout, data, f"Media mensile {year}",
            self.average_chart_combo.currentData(), self._average_canvases,
        )
        self._fill_single_table(self.average_table, data, "Categoria", "Media mensile")

    # ------------------------------------------------------------------
    # Rimborsi (finestra temporale navigabile)
    # ------------------------------------------------------------------

    def _refund_prev(self):
        self._refund_offset -= 1
        self._refresh_refund()

    def _refund_next(self):
        if self._refund_offset < 0:
            self._refund_offset += 1
            self._refresh_refund()

    def reset_refund_window(self):
        """Chiamata dal menu quando cambia la preferenza di finestra: riparte
        dal periodo corrente."""
        self._refund_offset = 0
        self._refresh_refund()

    def _refresh_refund(self):
        window_type = self.app_settings.get_refund_window()
        start, end, period_label = window_bounds(window_type, self._refund_offset)

        self.refund_window_label.setText(f"Finestra: {WINDOW_LABELS.get(window_type, window_type)}")
        self.refund_period_label.setText(period_label)
        self.refund_next_btn.setEnabled(self._refund_offset < 0)

        older = self.refund_analyzer.count_outstanding_before(start)
        if older > 0:
            self.refund_pending_banner.setText(
                f"⚠ Ci sono {older} rimborso/i non saldato/i in periodi precedenti: "
                "usa «◀ Precedente» per controllarli."
            )
            self.refund_pending_banner.setVisible(True)
        else:
            self.refund_pending_banner.setVisible(False)

        detail = self.refund_analyzer.build_window_detail(start, end)
        self._fill_refund_table(detail)
        self._update_toggle_all_button(detail)

        total = detail["total_outstanding"]
        if not detail["rows"]:
            self.refund_summary.setText("Nessuna spesa condivisa in questo periodo.")
        elif total > 0:
            self.refund_summary.setText(f"Totale da rimborsare in questo periodo: {total:.2f} €")
        else:
            self.refund_summary.setText("Tutto saldato in questo periodo. ✓")

    def _update_toggle_all_button(self, detail):
        unsettled = detail["unsettled_share_ids"]
        settled = [r["share_id"] for r in detail["rows"] if r["settled"]]
        btn = self.refund_toggle_all_btn
        try:
            btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        if unsettled:
            btn.setEnabled(True)
            btn.setText("Segna tutti come saldati")
            btn.clicked.connect(lambda: self._set_all_settled(unsettled, True))
        elif settled:
            btn.setEnabled(True)
            btn.setText("Segna tutti come da saldare")
            btn.clicked.connect(lambda: self._set_all_settled(settled, False))
        else:
            btn.setEnabled(False)
            btn.setText("Segna tutti come saldati")
            btn.clicked.connect(self._toggle_all)

    def _toggle_all(self):
        # Placeholder ricollegato dinamicamente in _update_toggle_all_button.
        return

    def _set_all_settled(self, share_ids, settled):
        ok, msg = self.refund_controller.set_shares_settled(share_ids, settled)
        if not ok:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Errore", msg)
            self._on_data_changed()
        # Il controller pubblica DATA_CHANGED -> refresh deferito automatico.

    def _toggle_share(self, share_id, settled):
        if settled:
            ok, msg = self.refund_controller.mark_share_settled(share_id)
        else:
            ok, msg = self.refund_controller.mark_share_unsettled(share_id)
        if not ok:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Errore", msg)
            self._on_data_changed()
        # Successo -> DATA_CHANGED dal controller -> refresh deferito.

    def _fill_refund_table(self, detail):
        table = self.refund_table
        table.clearContents()
        table.clearSpans()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Debitore", "Creditore", "Data", "Voce", "Importo", "Saldato"]
        )
        table.setRowCount(0)

        rows = detail["rows"]
        pair_totals = detail["pair_totals"]
        recap_font = QFont()
        recap_font.setBold(True)
        recap_rows: set[int] = set()

        def add_text(r, c, text, align=None):
            item = QTableWidgetItem(text)
            if align is not None:
                item.setTextAlignment(align)
            table.setItem(r, c, item)
            return item

        for (_creditor_name, _debtor_name), group in groupby(
            rows, key=lambda x: (x["creditor_name"], x["debtor_name"])
        ):
            group = list(group)
            for item in group:
                r = table.rowCount()
                table.insertRow(r)
                add_text(r, 0, item["debtor_name"])
                add_text(r, 1, item["creditor_name"])
                add_text(r, 2, item["date"])
                add_text(r, 3, item["description"])
                add_text(r, 4, f"{item['amount']:.2f} €", int(Qt.AlignRight | Qt.AlignVCenter))
                table.setCellWidget(r, 5, self._settled_checkbox(item["share_id"], item["settled"]))

            debtor_id = group[0]["debtor_id"]
            creditor_id = group[0]["creditor_id"]
            tot = pair_totals.get((debtor_id, creditor_id), {"outstanding": 0.0, "settled": 0.0})
            r = table.rowCount()
            table.insertRow(r)
            recap_rows.add(r)
            table.setSpan(r, 0, 1, 4)
            recap = add_text(
                r, 0,
                f"▶ {group[0]['debtor_name']} deve a {group[0]['creditor_name']} — da rimborsare:",
            )
            recap.setFont(recap_font)
            amount_item = add_text(r, 4, f"{tot['outstanding']:.2f} €", int(Qt.AlignRight | Qt.AlignVCenter))
            amount_item.setFont(recap_font)
            info = add_text(r, 5, f"{tot['settled']:.2f} € saldati")
            info.setForeground(Qt.gray)

        self.refund_recap_delegate.recap_rows = recap_rows
        table.viewport().update()

        header = table.horizontalHeader()
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

    def _settled_checkbox(self, share_id, settled) -> QWidget:
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        check = QCheckBox()
        check.setChecked(bool(settled))
        check.toggled.connect(lambda checked, sid=share_id: self._toggle_share(sid, checked))
        lay.addWidget(check)
        return holder

    # ------------------------------------------------------------------
    # Grafici a torta
    # ------------------------------------------------------------------

    def _build_pies_area(self, layout) -> QHBoxLayout:
        """Striscia orizzontale che ospita i grafici; ha un'altezza minima e
        occupa lo spazio verticale in eccesso (stretch), lasciando alla tabella
        sottostante solo lo spazio necessario al suo contenuto."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(_CHART_MIN_HEIGHT)
        host = QWidget()
        charts_layout = QHBoxLayout(host)
        charts_layout.setContentsMargins(4, 4, 4, 4)
        charts_layout.setSpacing(12)
        scroll.setWidget(host)
        layout.addWidget(scroll, stretch=1)
        return charts_layout

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _empty_charts_label(self, charts_layout):
        empty = QLabel("Nessun dato per il periodo selezionato.")
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet("color: palette(mid);")
        charts_layout.addWidget(empty, stretch=1)

    def _draw_user_charts(self, charts_layout: QHBoxLayout, data_by_user: dict,
                          mode: str, canvas_store: list):
        """Un grafico per utente (torta o istogramma) che occupa tutta la
        larghezza disponibile, suddivisa equamente tra gli utenti."""
        self._clear_layout(charts_layout)
        canvas_store.clear()

        users = [u for u in data_by_user if any(data_by_user[u].values())]
        if not users:
            self._empty_charts_label(charts_layout)
            return

        for user in users:
            cats = data_by_user[user]
            pairs = sorted(
                ((label, val) for label, val in cats.items() if val),
                key=lambda kv: kv[1],
                reverse=True,
            )
            canvas = InteractivePieCanvas()
            if mode == "bar":
                canvas.draw_bar(user, [p[0] for p in pairs], [p[1] for p in pairs])
            else:
                canvas.draw_pie(user, [p[0] for p in pairs], [p[1] for p in pairs])
            canvas_store.append(canvas)
            charts_layout.addWidget(canvas, stretch=1)

    def _draw_single_chart(self, charts_layout: QHBoxLayout, data: dict,
                           title: str, mode: str, canvas_store: list):
        """Un solo grafico centrato che occupa tutta la larghezza disponibile."""
        self._clear_layout(charts_layout)
        canvas_store.clear()

        pairs = sorted(
            ((label, val) for label, val in data.items() if val),
            key=lambda kv: kv[1],
            reverse=True,
        )
        if not pairs:
            self._empty_charts_label(charts_layout)
            return

        canvas = InteractivePieCanvas()
        if mode == "bar":
            canvas.draw_bar(title, [p[0] for p in pairs], [p[1] for p in pairs])
        else:
            canvas.draw_pie(title, [p[0] for p in pairs], [p[1] for p in pairs])
        canvas_store.append(canvas)
        charts_layout.addWidget(canvas, stretch=1)

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
        self._fit_table_to_contents(table)

    def _fill_single_table(self, table: QTableWidget, data: dict, key_header: str, val_header: str):
        table.clear()
        items = [(k, v) for k, v in data.items() if v]
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels([key_header, val_header])
        table.setRowCount(len(items))
        for r, (k, v) in enumerate(items):
            table.setItem(r, 0, QTableWidgetItem(k))
            table.setItem(r, 1, QTableWidgetItem(f"{v:.2f} €"))
        self._fit_table_to_contents(table)
