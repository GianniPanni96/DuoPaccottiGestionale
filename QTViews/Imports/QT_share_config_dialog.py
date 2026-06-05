"""Dialog per configurare la condivisione di una spesa importata:
partecipanti, percentuali (default eque) e anticipatore.

Restituisce in ``self.config`` un dict ``{is_shared, advancer, shares}`` dove
``shares`` = {user_id: frazione 0..1}, oppure ``None`` se la condivisione
viene rimossa/annullata."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Gestionale_Enums import DBUsersColumns

if TYPE_CHECKING:
    from App_context import AppContext

_PCT_TOLERANCE = 0.5  # punti percentuali


class QTShareConfigDialog(QDialog):
    def __init__(self, app_context: "AppContext", total_amount: float,
                 owner_user_id: int, existing: dict | None = None,
                 fixed_advancer: int | None = None, parent=None):
        super().__init__(parent)
        self.total_amount = total_amount
        self.owner_user_id = owner_user_id
        self.fixed_advancer = fixed_advancer
        self.config = existing
        self.users = app_context.users_query_service.retrieve_users_map_list()
        self._widgets = {}  # uid -> (check, pct_spin, amount_label)

        self.setWindowTitle("Condivisione spesa")
        self.setModal(True)
        self._build_ui()
        self._load(existing)

    def _user_name(self, user) -> str:
        return f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"Importo totale: {self.total_amount:.2f} €"))

        adv_row = QHBoxLayout()
        adv_label = QLabel("Anticipata da:")
        adv_row.addWidget(adv_label)
        self.advancer_combo = QComboBox()
        for user in self.users:
            self.advancer_combo.addItem(self._user_name(user), user[DBUsersColumns.ID.value])
        adv_row.addWidget(self.advancer_combo, stretch=1)
        root.addLayout(adv_row)
        # Quando l'anticipatore e' fissato dall'esterno (es. pagatore del metodo
        # di pagamento) il combo e' superfluo: lo nascondiamo per evitare un
        # secondo selettore concorrente.
        if self.fixed_advancer is not None:
            adv_label.setVisible(False)
            self.advancer_combo.setVisible(False)

        grid = QGridLayout()
        grid.addWidget(QLabel("Partecipa"), 0, 0)
        grid.addWidget(QLabel("Utente"), 0, 1)
        grid.addWidget(QLabel("Quota %"), 0, 2)
        grid.addWidget(QLabel("Importo"), 0, 3)
        for i, user in enumerate(self.users, start=1):
            uid = user[DBUsersColumns.ID.value]
            check = QCheckBox()
            check.toggled.connect(self._recompute)
            grid.addWidget(check, i, 0, alignment=Qt.AlignCenter)
            grid.addWidget(QLabel(self._user_name(user)), i, 1)
            pct = QDoubleSpinBox()
            pct.setRange(0.0, 100.0)
            pct.setDecimals(1)
            pct.setSuffix(" %")
            pct.valueChanged.connect(self._recompute)
            grid.addWidget(pct, i, 2)
            amount = QLabel("0.00 €")
            grid.addWidget(amount, i, 3)
            self._widgets[uid] = (check, pct, amount)
        root.addLayout(grid)

        btns = QHBoxLayout()
        equal = QPushButton("Dividi equamente")
        equal.clicked.connect(self._equal_split)
        btns.addWidget(equal)
        btns.addStretch(1)
        remove = QPushButton("Rimuovi condivisione")
        remove.clicked.connect(self._remove)
        btns.addWidget(remove)
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Conferma")
        ok.setDefault(True)
        ok.clicked.connect(self._confirm)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        root.addLayout(btns)

    def _load(self, existing):
        if self.fixed_advancer is not None:
            adv_idx = self.advancer_combo.findData(self.fixed_advancer)
            shares = existing.get("shares", {}) if existing else {}
        elif existing:
            adv_idx = self.advancer_combo.findData(existing.get("advancer"))
            shares = existing.get("shares", {})
        else:
            adv_idx = self.advancer_combo.findData(self.owner_user_id)
            shares = {}
        if adv_idx >= 0:
            self.advancer_combo.setCurrentIndex(adv_idx)
        for uid, (check, pct, _a) in self._widgets.items():
            if uid in shares:
                check.setChecked(True)
                pct.setValue(float(shares[uid]) * 100.0)
            elif not existing and uid == self.owner_user_id:
                check.setChecked(True)
        self._recompute()

    def _recompute(self):
        for _uid, (check, pct, amount) in self._widgets.items():
            pct.setEnabled(check.isChecked())
            value = self.total_amount * (pct.value() / 100.0) if check.isChecked() else 0.0
            amount.setText(f"{value:.2f} €")

    def _equal_split(self):
        selected = [uid for uid, (c, _p, _a) in self._widgets.items() if c.isChecked()]
        if not selected:
            QMessageBox.warning(self, "Condivisione", "Seleziona almeno un partecipante.")
            return
        pct = 100.0 / len(selected)
        for uid, (check, spin, _a) in self._widgets.items():
            spin.blockSignals(True)
            spin.setValue(pct if check.isChecked() else 0.0)
            spin.blockSignals(False)
        self._recompute()

    def _remove(self):
        self.config = None
        self.accept()

    def _confirm(self):
        shares = {
            uid: round(spin.value() / 100.0, 6)
            for uid, (check, spin, _a) in self._widgets.items()
            if check.isChecked()
        }
        if not shares:
            QMessageBox.warning(self, "Condivisione", "Seleziona almeno un partecipante.")
            return
        advancer = self.advancer_combo.currentData()
        if advancer not in shares:
            QMessageBox.warning(self, "Condivisione", "L'anticipatore deve essere tra i partecipanti.")
            return
        total_pct = sum(spin.value() for _u, (c, spin, _a) in self._widgets.items() if c.isChecked())
        if abs(total_pct - 100.0) > _PCT_TOLERANCE:
            QMessageBox.warning(
                self, "Condivisione",
                f"La somma delle percentuali deve essere 100% (attuale: {total_pct:.1f}%).",
            )
            return
        self.config = {"is_shared": True, "advancer": advancer, "shares": shares}
        self.accept()
