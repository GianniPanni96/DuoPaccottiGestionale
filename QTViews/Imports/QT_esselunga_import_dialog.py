"""Import 'a voci' dello scontrino Esselunga.

Mostra l'elenco degli articoli; l'utente assegna ciascuno a Cibo o
Consumabili Casa. La spesa si riduce a uno o due «bucket» di pagamento:

- **carta**: importo = totale scontrino − buoni pasto (finanzia Consumabili +
  Cibo-carta);
- **buoni pasto**: per legge coprono solo generi alimentari (finanzia Cibo).

Per ogni bucket si sceglie chi ha pagato (anticipatore) e come ripartire la
spesa (partecipanti + percentuali) tramite il dialog di suddivisione. La
suddivisione di default deriva dalla preferenza app (equa tra tutti / personale).

Quando esistono due metodi di pagamento di due utenti diversi il selettore
utente globale non avrebbe senso e viene rimosso: vincono i selettori per
metodo di pagamento.

Prima del salvataggio ogni bucket viene controllato contro le spese gia' a
sistema (possibile addebito gia' importato da estratto conto); se solo alcuni
bucket risultano duplicati l'utente puo' scegliere di salvare solo quelli non
trovati."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
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

from Gestionale_Enums import DBExpensesColumns as E, DBUsersColumns, ExpenseSource

if TYPE_CHECKING:
    from App_context import AppContext
    from ParserServices.esselunga_receipt import EsselungaReceipt

_CIBO = "CIBO"
_CONSUMABILI = "CONSUMABILI_CASA"
_SPLIT = [("Cibo", _CIBO), ("Consumabili Casa", _CONSUMABILI)]
_LABEL_BY_KEY = {key: label for label, key in _SPLIT}
_EURO_TOLERANCE = 0.01

_BUCKET_LABEL = {"card": "Carta", "voucher": "Buoni pasto"}


class QTEsselungaImportDialog(QDialog):
    COL_ARTICLE, COL_PRICE, COL_CATEGORY = range(3)

    def __init__(self, app_context: "AppContext", owner_user_id: int,
                 receipt: "EsselungaReceipt", parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.receipt = receipt
        self.saved_count = 0

        self.expense_controller = app_context.expense_controller
        self.app_settings = app_context.app_settings_manager
        self.duplicate_detector = app_context.duplicate_detection_service
        self.users = app_context.users_query_service.retrieve_users_map_list()
        self._labels = dict(app_context.catalogs_manager.get_section("expense_categories"))
        self._combos = []
        self._loading = True

        # --- modello a bucket -------------------------------------------------
        meal_total = round(self.receipt.meal_voucher_total(), 2)
        card_total = round(self.receipt.total - meal_total, 2)
        self.two_bucket = (
            self.receipt.has_meal_voucher()
            and card_total > _EURO_TOLERANCE
            and meal_total > _EURO_TOLERANCE
        )
        if self.two_bucket:
            self._bucket_amounts = {"card": card_total, "voucher": meal_total}
        else:
            self._bucket_amounts = {"card": round(self.receipt.total, 2)}
        self._payer_combos = {}                 # key -> QComboBox (solo two_bucket)
        self._split_buttons = {}                # key -> QPushButton
        self._splits = {k: None for k in self._bucket_amounts}  # key -> {uid: frazione} | None

        self.setWindowTitle("Import scontrino Esselunga")
        self.setModal(True)
        self.resize(700, 700)
        self._build_ui(owner_user_id)
        self._populate()
        self._loading = False
        self._refresh_all_split_buttons()
        self._recompute_totals()

    def _user_name(self, user) -> str:
        return f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"

    def _user_combo(self, selected_id) -> QComboBox:
        combo = QComboBox()
        for user in self.users:
            combo.addItem(self._user_name(user), user[DBUsersColumns.ID.value])
        idx = combo.findData(selected_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        return combo

    # ------------------------------------------------------------------
    # Costruzione UI
    # ------------------------------------------------------------------

    def _build_ui(self, owner_user_id):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        if not self.two_bucket:
            # Un solo metodo di pagamento: il selettore globale e' il pagatore.
            top.addWidget(QLabel("Pagata da:"))
            self.user_combo = self._user_combo(owner_user_id)
            self.user_combo.currentIndexChanged.connect(self._on_single_payer_changed)
            top.addWidget(self.user_combo)
            split_btn = QPushButton()
            split_btn.clicked.connect(lambda _=False: self._configure_split("card"))
            self._split_buttons["card"] = split_btn
            top.addWidget(split_btn)
            top.addSpacing(20)
        else:
            self.user_combo = None
        top.addWidget(QLabel("Data:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setCalendarPopup(True)
        parsed = QDate.fromString(self.receipt.date, "yyyy-MM-dd")
        self.date_edit.setDate(parsed if parsed.isValid() else QDate.currentDate())
        top.addWidget(self.date_edit)
        top.addStretch(1)
        root.addLayout(top)

        info = QLabel(
            f"Totale scontrino: {self.receipt.total:.2f} € — assegna ogni articolo "
            "a Cibo o Consumabili Casa."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        # Sezione metodi di pagamento (solo con due bucket).
        if self.two_bucket:
            root.addWidget(self._build_payments_section(owner_user_id))

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Articolo", "Prezzo (€)", "Categoria"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_ARTICLE, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_PRICE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_CATEGORY, QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(lambda _i: self._recompute_totals())
        root.addWidget(self.table, stretch=1)

        bulk = QHBoxLayout()
        for label, key in _SPLIT:
            btn = QPushButton(f"Tutti → {label}")
            btn.clicked.connect(lambda _=False, k=key: self._set_all_category(k))
            bulk.addWidget(btn)
        bulk.addStretch(1)
        root.addLayout(bulk)

        self.totals_label = QLabel("")
        tf = self.totals_label.font()
        tf.setBold(True)
        self.totals_label.setFont(tf)
        root.addWidget(self.totals_label)

        self.split_hint_label = QLabel("")
        self.split_hint_label.setWordWrap(True)
        self.split_hint_label.setStyleSheet("color: palette(mid);")
        root.addWidget(self.split_hint_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Salva le spese")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _build_payments_section(self, owner_user_id) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(frame)
        header = QLabel("Metodi di pagamento — indica chi ha pagato e come ripartire:")
        hf = header.font()
        hf.setBold(True)
        header.setFont(hf)
        lay.addWidget(header)

        for key in ("card", "voucher"):
            row = QHBoxLayout()
            label = QLabel(f"{_BUCKET_LABEL[key]} — {self._bucket_amounts[key]:.2f} €")
            label.setMinimumWidth(180)
            row.addWidget(label)
            combo = self._user_combo(owner_user_id)
            combo.currentIndexChanged.connect(lambda _i=0, k=key: self._on_bucket_payer_changed(k))
            self._payer_combos[key] = combo
            row.addWidget(combo)
            split_btn = QPushButton()
            split_btn.clicked.connect(lambda _=False, k=key: self._configure_split(k))
            self._split_buttons[key] = split_btn
            row.addWidget(split_btn)
            row.addStretch(1)
            lay.addLayout(row)

        note = QLabel(
            "I buoni pasto coprono solo generi alimentari: se pagati da un utente "
            "diverso da chi ha usato la carta, la spesa «Cibo» verra' divisa."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        lay.addWidget(note)
        return frame

    def _populate(self):
        items = self.receipt.items
        self.table.setRowCount(len(items))
        for r, item in enumerate(items):
            art = QTableWidgetItem(item.description)
            self.table.setItem(r, self.COL_ARTICLE, art)
            price = QTableWidgetItem(f"{item.price:.2f}")
            price.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
            self.table.setItem(r, self.COL_PRICE, price)
            combo = QComboBox()
            for label, key in _SPLIT:
                combo.addItem(label, key)
            ci = combo.findData(item.category_key)
            combo.setCurrentIndex(ci if ci >= 0 else 0)
            combo.currentIndexChanged.connect(self._recompute_totals)
            self.table.setCellWidget(r, self.COL_CATEGORY, combo)
            self._combos.append(combo)

    # ------------------------------------------------------------------
    # Pagatori e suddivisione per bucket
    # ------------------------------------------------------------------

    def _bucket_keys(self):
        return list(self._bucket_amounts.keys())

    def _payer_for(self, key):
        if self.two_bucket:
            combo = self._payer_combos.get(key) or self._payer_combos.get("card")
            return combo.currentData() if combo is not None else None
        return self.user_combo.currentData()

    def _default_split(self, payer) -> dict:
        """Suddivisione di default dalla preferenza app."""
        if self.app_settings.get_default_split_mode() == "EQUA" and self.users:
            frac = 1.0 / len(self.users)
            return {u[DBUsersColumns.ID.value]: frac for u in self.users}
        return {payer: 1.0}

    def _resolved_split(self, key, payer) -> dict:
        stored = self._splits.get(key)
        return dict(stored) if stored else self._default_split(payer)

    def _is_personal(self, shares, payer) -> bool:
        participants = [uid for uid, frac in shares.items() if frac > 0]
        return len(participants) <= 1 and (not participants or participants[0] == payer)

    def _configure_split(self, key):
        from QTViews.Imports.QT_share_config_dialog import QTShareConfigDialog
        payer = self._payer_for(key)
        if payer is None:
            QMessageBox.warning(self, "Suddivisione", "Seleziona prima chi ha pagato.")
            return
        amount = self._bucket_amounts.get(key, 0.0)
        existing = {"advancer": payer, "shares": self._resolved_split(key, payer)}
        dialog = QTShareConfigDialog(
            self.app_context, total_amount=amount, owner_user_id=payer,
            existing=existing, fixed_advancer=payer, parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.config:
            self._splits[key] = dialog.config["shares"]
        else:
            # "Rimuovi condivisione" -> spesa personale di chi ha pagato.
            self._splits[key] = {payer: 1.0}
        self._update_split_button(key)

    def _split_summary(self, key) -> str:
        payer = self._payer_for(key)
        shares = self._resolved_split(key, payer)
        if self._is_personal(shares, payer):
            return "Suddividi… (personale)"
        n = len([f for f in shares.values() if f > 0])
        custom = self._splits.get(key) is not None
        prefix = "Suddivisa" if custom else "Equa"
        return f"Suddividi… ({prefix} · {n} quote)"

    def _update_split_button(self, key):
        btn = self._split_buttons.get(key)
        if btn is not None:
            btn.setText(self._split_summary(key))

    def _refresh_all_split_buttons(self):
        for key in self._bucket_keys():
            self._update_split_button(key)

    def _on_single_payer_changed(self, _idx=None):
        if self._loading:
            return
        self._refresh_all_split_buttons()
        self._recompute_totals()

    def _on_bucket_payer_changed(self, key):
        if self._loading:
            return
        self._update_split_button(key)
        self._recompute_totals()

    # ------------------------------------------------------------------
    # Categorie / totali
    # ------------------------------------------------------------------

    def _set_all_category(self, key):
        for combo in self._combos:
            idx = combo.findData(key)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        self._recompute_totals()

    def _row_price(self, row):
        item = self.table.item(row, self.COL_PRICE)
        if item is None:
            return 0.0
        try:
            return float(item.text().strip().replace(",", "."))
        except ValueError:
            return 0.0

    def _totals_by_category(self) -> dict:
        totals = {_CIBO: 0.0, _CONSUMABILI: 0.0}
        for r in range(self.table.rowCount()):
            key = self._combos[r].currentData()
            totals[key] = totals.get(key, 0.0) + self._row_price(r)
        return {k: round(v, 2) for k, v in totals.items()}

    def _recompute_totals(self):
        if self._loading:
            return
        totals = self._totals_by_category()
        self.totals_label.setText(
            f"Totale Cibo: {totals[_CIBO]:.2f} €     ·     "
            f"Totale Consumabili Casa: {totals[_CONSUMABILI]:.2f} €"
        )

        if not self.two_bucket:
            self.split_hint_label.setText("")
            return
        card_user = self._payer_for("card")
        meal_user = self._payer_for("voucher")
        meal_amount = self._bucket_amounts.get("voucher", 0.0)
        cibo = totals[_CIBO]
        if meal_amount > 0 and meal_user is not None and meal_user != card_user:
            if meal_amount > cibo + _EURO_TOLERANCE:
                self.split_hint_label.setText(
                    f"⚠ I buoni pasto ({meal_amount:.2f} €) superano il totale Cibo "
                    f"({cibo:.2f} €): sposta gli alimentari sotto «Cibo» prima di salvare."
                )
            else:
                card_food = round(cibo - meal_amount, 2)
                self.split_hint_label.setText(
                    f"Cibo diviso: {meal_amount:.2f} € → {self._name_of(meal_user)} (buoni pasto), "
                    f"{card_food:.2f} € → {self._name_of(card_user)} (carta)."
                )
        else:
            self.split_hint_label.setText("")

    def _name_of(self, user_id):
        for user in self.users:
            if user[DBUsersColumns.ID.value] == user_id:
                return self._user_name(user)
        return f"Utente {user_id}"

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _make_expense(self, user_id, key, label, amount, date) -> dict:
        return {
            E.DESCRIPTION.value: f"Spesa Esselunga – {label}",
            E.USER_ID.value: user_id,
            E.CATEGORY.value: key,
            E.MERCHANT.value: self.receipt.merchant,
            E.TOTAL_AMOUNT.value: f"{amount:.2f}",
            E.DATE.value: date,
            E.VISIBILITY.value: self.app_settings.get_default_visibility(),
            E.SOURCE.value: ExpenseSource.SCONTRINO.value,
            "_iva_rate": self.app_settings.get_default_iva(),
        }

    def _build_tagged_rows(self, date):
        """Costruisce le righe di spesa taggate per bucket.

        Ritorna ``(rows, None)`` dove rows = list[(data, bucket_key)], oppure
        ``(None, errore)`` per fermare il salvataggio con un avviso."""
        totals = self._totals_by_category()
        cibo = totals.get(_CIBO, 0.0)
        consumabili = totals.get(_CONSUMABILI, 0.0)

        card_user = self._payer_for("card")
        meal_user = self._payer_for("voucher")
        meal_amount = self._bucket_amounts.get("voucher", 0.0) if self.two_bucket else 0.0
        split_food = meal_amount > _EURO_TOLERANCE and meal_user is not None and meal_user != card_user

        if split_food and meal_amount > cibo + _EURO_TOLERANCE:
            return None, (
                f"L'importo dei buoni pasto ({meal_amount:.2f} €) supera il totale "
                f"assegnato a «Cibo» ({cibo:.2f} €).\n\nI buoni pasto possono pagare "
                "solo generi alimentari: sposta gli articoli alimentari sotto «Cibo» e riprova."
            )

        rows = []
        # Non alimentari: sempre a carico del bucket carta.
        if consumabili > 0:
            rows.append((self._make_expense(
                card_user, _CONSUMABILI, _LABEL_BY_KEY[_CONSUMABILI], consumabili, date), "card"))
        # Alimentari: split solo se i buoni pasto sono di un altro utente.
        if cibo > 0:
            if split_food:
                voucher_food = min(meal_amount, cibo)
                card_food = round(cibo - voucher_food, 2)
                if voucher_food > 0:
                    rows.append((self._make_expense(
                        meal_user, _CIBO, "Cibo (buoni pasto)", voucher_food, date), "voucher"))
                if card_food > 0:
                    rows.append((self._make_expense(
                        card_user, _CIBO, "Cibo (carta)", card_food, date), "card"))
            else:
                rows.append((self._make_expense(
                    card_user, _CIBO, _LABEL_BY_KEY[_CIBO], cibo, date), "card"))
        return rows, None

    def _group_buckets(self, tagged_rows, date) -> list:
        """Raggruppa le righe per bucket, calcola importo/pagatore/split e
        rileva i duplicati. Ritorna una lista di dict descrittori."""
        by_key = {}
        for data, key in tagged_rows:
            by_key.setdefault(key, []).append(data)

        buckets = []
        for key, rows in by_key.items():
            payer = self._payer_for(key)
            amount = round(sum(float(d[E.TOTAL_AMOUNT.value]) for d in rows), 2)
            split = self._resolved_split(key, payer)
            match = self.duplicate_detector.find_duplicate(
                payer, date, amount, merchant_hint=self.receipt.merchant,
            ) if amount > 0 else None
            buckets.append({
                "key": key, "label": _BUCKET_LABEL.get(key, key), "rows": rows,
                "payer": payer, "amount": amount, "split": split, "dup": match,
            })
        return buckets

    def _apply_split(self, bucket) -> tuple[bool, str]:
        payer = bucket["payer"]
        shares = bucket["split"]
        if self._is_personal(shares, payer):
            return True, ""
        if payer not in shares or shares.get(payer, 0.0) <= 0:
            return False, (f"Bucket «{bucket['label']}»: l'anticipatore deve essere "
                           "tra i partecipanti della suddivisione.")
        total_pct = sum(shares.values())
        if abs(total_pct - 1.0) > _EURO_TOLERANCE:
            return False, (f"Bucket «{bucket['label']}»: la somma delle percentuali deve "
                           f"essere 100% (attuale: {total_pct * 100:.1f}%).")
        for data in bucket["rows"]:
            data[E.IS_SHARED.value] = True
            data[E.ADVANCED_BY_USER_ID.value] = payer
            data["_shares"] = dict(shares)
        return True, ""

    def _resolve_duplicates(self, buckets) -> str:
        """Ritorna 'all' | 'partial' | 'cancel' in base alla scelta utente."""
        dups = [b for b in buckets if b["dup"]]
        if not dups:
            return "all"

        lines = []
        for b in dups:
            m = b["dup"]
            day = QDate.fromString(str(m.get("existing_date") or "")[:10], "yyyy-MM-dd")
            when = day.toString("dd/MM/yyyy") if day.isValid() else m.get("existing_date")
            lines.append(
                f"• {b['label']} {b['amount']:.2f} € → già a sistema una spesa del "
                f"{when} da {m.get('existing_total', 0.0):.2f} €"
            )

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Possibili duplicati")
        has_non_dup = any(not b["dup"] for b in buckets)

        if len(buckets) >= 2 and has_non_dup:
            msg.setText(
                "Alcuni metodi di pagamento risultano già a sistema (probabile addebito "
                "già importato da estratto conto):\n\n" + "\n".join(lines)
                + "\n\nCosa vuoi salvare?"
            )
            all_btn = msg.addButton("Salva tutto", QMessageBox.AcceptRole)
            partial_btn = msg.addButton("Salva solo i non duplicati", QMessageBox.ActionRole)
            msg.addButton("Annulla", QMessageBox.RejectRole)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked is all_btn:
                return "all"
            if clicked is partial_btn:
                return "partial"
            return "cancel"

        msg.setText(
            "La spesa risulta già a sistema (probabile addebito già importato da "
            "estratto conto):\n\n" + "\n".join(lines) + "\n\nSalvare comunque?"
        )
        yes_btn = msg.addButton("Salva comunque", QMessageBox.AcceptRole)
        msg.addButton("Annulla", QMessageBox.RejectRole)
        msg.exec()
        return "all" if msg.clickedButton() is yes_btn else "cancel"

    def _save(self):
        date = self.date_edit.date().toString("yyyy-MM-dd")
        for key in self._bucket_keys():
            if self._payer_for(key) is None:
                QMessageBox.warning(self, "Import", "Seleziona chi ha pagato.")
                return

        tagged_rows, error = self._build_tagged_rows(date)
        if error:
            QMessageBox.warning(self, "Import", error)
            return
        if not tagged_rows:
            QMessageBox.information(self, "Import", "Nessun articolo con importo positivo da salvare.")
            return

        buckets = self._group_buckets(tagged_rows, date)

        decision = self._resolve_duplicates(buckets)
        if decision == "cancel":
            return
        selected = [b for b in buckets if not b["dup"]] if decision == "partial" else buckets
        if not selected:
            QMessageBox.information(self, "Import", "Nessuna spesa da salvare.")
            return

        to_save = []
        for bucket in selected:
            ok, msg = self._apply_split(bucket)
            if not ok:
                QMessageBox.warning(self, "Suddivisione", msg)
                return
            to_save.extend(bucket["rows"])

        n_ok, errors = self.expense_controller.save_parsed_expenses(to_save)
        self.saved_count = n_ok
        if errors:
            QMessageBox.warning(self, "Import parziale",
                                f"Salvate {n_ok} spese. Errori:\n- " + "\n- ".join(errors[:8]))
        else:
            QMessageBox.information(self, "Import", f"Salvate {n_ok} spese dallo scontrino.")
        self.accept()
