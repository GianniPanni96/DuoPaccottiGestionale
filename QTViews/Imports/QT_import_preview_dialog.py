"""Anteprima editabile dei movimenti estratti da un estratto conto, prima
del salvataggio nel DB.

Caratteristiche:
- selettore in alto dell'utente a cui riferire spese ed entrate (default
  l'utente loggato);
- una riga per movimento (spesa o entrata), tutte modificabili; le entrate
  sono evidenziate in verde;
- per ogni spesa si puo' configurare la condivisione (partecipanti, quote,
  anticipatore) direttamente qui;
- al salvataggio crea spese ed entrate tramite i rispettivi controller."""

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import (
    DBExpensesColumns as E,
    DBIncomesColumns as I,
    DBUsersColumns,
)

if TYPE_CHECKING:
    from App_context import AppContext

_AMOUNT_RE = re.compile(r"^\d+([.,]\d{1,2})?$")
_INCOME_BG = QColor("#2f5437")     # verde chiaro per le righe entrata


class QTImportPreviewDialog(QDialog):
    HEADERS = ["Importa", "Tipo", "Data", "Descrizione", "Categoria",
               "Esercente", "Importo (€)", "Condivisione"]
    COL_INCLUDE, COL_KIND, COL_DATE, COL_DESC, COL_CAT, COL_MERCHANT, COL_AMOUNT, COL_SHARE = range(8)

    def __init__(self, app_context: "AppContext", owner_user_id: int, movements: list,
                 source: str, title: str = "Anteprima import", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.movements = movements
        self.source = source
        self.saved_expenses = 0
        self.saved_incomes = 0

        self.expense_controller = app_context.expense_controller
        self.income_controller = app_context.income_controller
        self.app_settings = app_context.app_settings_manager
        self.users = app_context.users_query_service.retrieve_users_map_list()

        self._expense_categories = self._catalog("expense_categories")
        self._income_categories = self._catalog("income_categories")
        self._share_configs = {}   # row -> {is_shared, advancer, shares}

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(1040, 640)
        self._build_ui(owner_user_id)
        self._populate()

    def _catalog(self, section):
        return [
            (key, label)
            for key, label in self.app_context.catalogs_manager.get_section(section).items()
            if key != "ADD_CATEGORY"
        ]

    def _user_name(self, user) -> str:
        return f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"

    # ------------------------------------------------------------------

    def _build_ui(self, owner_user_id):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Spese ed entrate riferite a:"))
        self.user_combo = QComboBox()
        for user in self.users:
            self.user_combo.addItem(self._user_name(user), user[DBUsersColumns.ID.value])
        idx = self.user_combo.findData(owner_user_id)
        if idx >= 0:
            self.user_combo.setCurrentIndex(idx)
        top.addWidget(self.user_combo)
        top.addStretch(1)
        n_exp = sum(1 for m in self.movements if m.kind == "expense")
        n_inc = len(self.movements) - n_exp
        top.addWidget(QLabel(f"{n_exp} spese · {n_inc} entrate (in verde)"))
        root.addLayout(top)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_DESC, QHeaderView.Stretch)
        for col in (self.COL_INCLUDE, self.COL_KIND, self.COL_DATE, self.COL_CAT,
                    self.COL_MERCHANT, self.COL_AMOUNT, self.COL_SHARE):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        root.addWidget(self.table, stretch=1)

        bottom = QHBoxLayout()
        for text, checked in (("Seleziona tutto", True), ("Deseleziona tutto", False)):
            btn = QPushButton(text)
            btn.clicked.connect(lambda _=False, c=checked: self._set_all_checked(c))
            bottom.addWidget(btn)
        bottom.addStretch(1)
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Salva selezionate")
        save.setDefault(True)
        save.clicked.connect(self._save)
        bottom.addWidget(cancel)
        bottom.addWidget(save)
        root.addLayout(bottom)

    def _populate(self):
        self.table.setRowCount(len(self.movements))
        self._check_boxes = []
        self._category_combos = []
        for r, mv in enumerate(self.movements):
            is_income = mv.kind == "income"

            self.table.setCellWidget(r, self.COL_INCLUDE, self._checkbox_holder(mv.include, r))

            kind_item = QTableWidgetItem("Entrata" if is_income else "Spesa")
            kind_item.setFlags(kind_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, self.COL_KIND, kind_item)

            self.table.setItem(r, self.COL_DATE, QTableWidgetItem(mv.date))
            self.table.setItem(r, self.COL_DESC, QTableWidgetItem(mv.description))

            combo = QComboBox()
            categories = self._income_categories if is_income else self._expense_categories
            # Placeholder vuoto per spese senza categoria suggerita
            if not is_income and not mv.suggested_category:
                combo.addItem("— seleziona —", "")
            for key, label in categories:
                combo.addItem(label, key)
            ci = combo.findData(mv.suggested_category) if mv.suggested_category else 0
            combo.setCurrentIndex(ci if ci >= 0 else 0)
            self.table.setCellWidget(r, self.COL_CAT, combo)
            self._category_combos.append(combo)

            self.table.setItem(r, self.COL_MERCHANT, QTableWidgetItem(mv.merchant))
            self.table.setItem(r, self.COL_AMOUNT, QTableWidgetItem(f"{mv.amount:.2f}"))

            if is_income:
                placeholder = QTableWidgetItem("—")
                placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsEditable)
                placeholder.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, self.COL_SHARE, placeholder)
                self._tint_row(r)
            else:
                self.table.setCellWidget(r, self.COL_SHARE, self._share_button(r))

    # ------------------------------------------------------------------

    def _checkbox_holder(self, checked, row):
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        check = QCheckBox()
        check.setChecked(bool(checked))
        lay.addWidget(check)
        # mantieni la lista allineata agli indici riga
        while len(self._check_boxes) <= row:
            self._check_boxes.append(None)
        self._check_boxes[row] = check
        return holder

    def _share_button(self, row) -> QPushButton:
        btn = QPushButton("Condividi…")
        btn.clicked.connect(lambda _=False, r=row: self._configure_share(r))
        return btn

    def _tint_row(self, row):
        for col in (self.COL_KIND, self.COL_DATE, self.COL_DESC,
                    self.COL_MERCHANT, self.COL_AMOUNT, self.COL_SHARE):
            item = self.table.item(row, col)
            if item is not None:
                item.setBackground(_INCOME_BG)

    def _set_all_checked(self, checked: bool):
        for check in self._check_boxes:
            if check is not None:
                check.setChecked(checked)

    def _cell_text(self, row, col) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item is not None else ""

    def _amount_value(self, row):
        raw = self._cell_text(row, self.COL_AMOUNT)
        return float(raw.replace(",", ".")) if _AMOUNT_RE.fullmatch(raw) else None

    def _configure_share(self, row):
        from QTViews.Imports.QT_share_config_dialog import QTShareConfigDialog
        amount = self._amount_value(row) or 0.0
        owner = self.user_combo.currentData()
        dialog = QTShareConfigDialog(
            self.app_context, total_amount=amount, owner_user_id=owner,
            existing=self._share_configs.get(row), parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        btn = self.table.cellWidget(row, self.COL_SHARE)
        if dialog.config:
            self._share_configs[row] = dialog.config
            n = len(dialog.config["shares"])
            if isinstance(btn, QPushButton):
                btn.setText(f"Condivisa · {n} quote")
        else:
            self._share_configs.pop(row, None)
            if isinstance(btn, QPushButton):
                btn.setText("Condividi…")

    # ------------------------------------------------------------------

    def _save(self):
        owner = self.user_combo.currentData()
        expenses, incomes = [], []
        # Per ogni riga salvata: (row_index, operation, category, description)
        # usato per aggiornare operation_labels dopo il salvataggio.
        op_label_updates: list[tuple[str, str, str]] = []

        for r in range(self.table.rowCount()):
            check = self._check_boxes[r]
            if check is None or not check.isChecked():
                continue

            date = self._cell_text(r, self.COL_DATE)
            if not QDate.fromString(date, "yyyy-MM-dd").isValid():
                QMessageBox.warning(self, "Validazione", f"Riga {r + 1}: data non valida (AAAA-MM-GG).")
                return
            description = self._cell_text(r, self.COL_DESC)
            if not description:
                QMessageBox.warning(self, "Validazione", f"Riga {r + 1}: descrizione obbligatoria.")
                return
            amount = self._amount_value(r)
            if amount is None:
                QMessageBox.warning(self, "Validazione", f"Riga {r + 1}: importo non valido (es. 49.90).")
                return

            category = self._category_combos[r].currentData() or ""
            if not category:
                QMessageBox.warning(self, "Validazione", f"Riga {r + 1}: seleziona una categoria.")
                return
            is_income = self.movements[r].kind == "income"

            if is_income:
                incomes.append({
                    I.DESCRIPTION.value: description,
                    I.USER_ID.value: owner,
                    I.CATEGORY.value: category,
                    I.AMOUNT.value: f"{amount:.2f}",
                    I.DATE.value: date,
                    I.VISIBILITY.value: self.app_settings.get_default_visibility(),
                    I.SOURCE.value: "ESTRATTO_BANCA",
                })
            else:
                data = {
                    E.DESCRIPTION.value: description,
                    E.USER_ID.value: owner,
                    E.CATEGORY.value: category,
                    E.MERCHANT.value: self._cell_text(r, self.COL_MERCHANT),
                    E.TOTAL_AMOUNT.value: f"{amount:.2f}",
                    E.DATE.value: date,
                    E.VISIBILITY.value: self.app_settings.get_default_visibility(),
                    E.SOURCE.value: self.source,
                    "_iva_rate": self.app_settings.get_default_iva(),
                }
                cfg = self._share_configs.get(r)
                if cfg:
                    data[E.IS_SHARED.value] = True
                    data[E.ADVANCED_BY_USER_ID.value] = cfg["advancer"]
                    data["_shares"] = cfg["shares"]
                expenses.append(data)
                # Registra la coppia operazione→(categoria, descrizione) per l'aggiornamento
                op = self.movements[r].operation
                if op:
                    op_label_updates.append((op, category, description))

        if not expenses and not incomes:
            QMessageBox.information(self, "Import", "Nessun movimento selezionato.")
            return

        errors = []
        if expenses:
            n_ok, errs = self.expense_controller.save_parsed_expenses(expenses)
            self.saved_expenses = n_ok
            errors += errs
        if incomes:
            n_ok, errs = self.income_controller.save_parsed_incomes(incomes)
            self.saved_incomes = n_ok
            errors += errs

        # Aggiorna operation_labels solo se almeno una spesa è stata salvata
        if self.saved_expenses > 0:
            mgr = getattr(self.app_context, "operation_labels_manager", None)
            if mgr is not None:
                for op, cat, desc in op_label_updates:
                    mgr.set_entry(op, cat, desc)

        summary = f"Salvate {self.saved_expenses} spese e {self.saved_incomes} entrate."
        if errors:
            QMessageBox.warning(self, "Import parziale",
                                summary + f"\n{len(errors)} errori:\n- " + "\n- ".join(errors[:8]))
        else:
            QMessageBox.information(self, "Import", summary)
        self.accept()

    @property
    def saved_count(self) -> int:
        return self.saved_expenses + self.saved_incomes
