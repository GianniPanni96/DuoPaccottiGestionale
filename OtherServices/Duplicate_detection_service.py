"""Rilevamento di spese potenzialmente duplicate tra gli import.

Quando una spesa Esselunga viene pagata (in tutto o in parte) con carta, lo
stesso addebito ricompare nell'estratto conto bancario come singolo movimento.
Importando entrambe le fonti la quota pagata-con-carta verrebbe contata due
volte. Questo servizio, a partire da un movimento candidato (data + importo),
cerca tra le spese gia' a sistema dell'utente una possibile duplicazione.

Il match e' bidirezionale e asimmetrico:
- lato estratto conto: l'importo del movimento bancario corrisponde alla
  *somma* delle spese Esselunga (``SCONTRINO``) di quel giorno → match aggregato;
- lato scontrino Esselunga: la quota-carta dello scontrino corrisponde a una
  singola spesa bancaria gia' presente → match singolo.

Scelte di prodotto (concordate):
- finestra date ±3 giorni (la data contabile in banca segue lo scontrino di 1-3 gg);
- match su importo + data; l'esercente che cita "Esselunga" alza solo la
  confidenza, non e' obbligatorio (copre anche duplicati non-Esselunga).

Servizio read-only: non scrive nulla, lascia la scelta finale all'utente.
"""

from Gestionale_Enums import DBExpensesColumns, ExpenseSource
from Utils.Controller_utils import ControllerUtils


class DuplicateDetectionService:
    DATE_WINDOW_DAYS = 3
    AMOUNT_TOLERANCE = 0.01

    def __init__(self, expenses_query_service):
        self.expenses_query_service = expenses_query_service

    # ------------------------------------------------------------------

    def find_duplicate(self, owner_user_id, date, amount, merchant_hint="",
                       ignore_source=None):
        """Cerca un possibile duplicato tra le spese dell'utente.

        Ritorna ``None`` se nessun match, altrimenti un descrittore::

            {
                "expense_ids": [...],          # spese coinvolte nel match
                "kind": "single" | "aggregate",
                "existing_total": float,        # importo (somma) gia' a sistema
                "existing_date": "YYYY-MM-DD",
                "existing_merchant": str,
                "esselunga_hint": bool,
            }
        """
        target_date = ControllerUtils.parse_date(date)
        try:
            target_amount = float(amount)
        except (TypeError, ValueError):
            return None
        if target_date is None or target_amount <= 0:
            return None

        # Scope per proprietario: i duplicati sono spese dello stesso utente.
        expenses = self.expenses_query_service.retrieve_expenses_map_list_by_user(
            owner_user_id, year=-1
        )
        candidates = [
            e for e in expenses
            if self._within_window(e.get(DBExpensesColumns.DATE.value), target_date)
            and (ignore_source is None
                 or e.get(DBExpensesColumns.SOURCE.value) != ignore_source)
        ]
        if not candidates:
            return None

        single = self._match_single(candidates, target_amount)
        if single is not None:
            return self._descriptor([single], "single", merchant_hint)

        aggregate = self._match_aggregate(candidates, target_amount)
        if aggregate:
            return self._descriptor(aggregate, "aggregate", merchant_hint)

        return None

    # ------------------------------------------------------------------
    # Strategie di match
    # ------------------------------------------------------------------

    def _match_single(self, candidates, amount):
        """Una singola spesa con importo ~ amount."""
        for e in candidates:
            if self._amount_eq(e.get(DBExpensesColumns.TOTAL_AMOUNT.value), amount):
                return e
        return None

    def _match_aggregate(self, candidates, amount):
        """Somma delle spese Esselunga (SCONTRINO) della stessa data ~ amount.

        Raggruppa per data esatta (non sull'intera finestra) per non sommare
        scontrini di giorni diversi."""
        groups = {}
        for e in candidates:
            if e.get(DBExpensesColumns.SOURCE.value) != ExpenseSource.SCONTRINO.value:
                continue
            if not self._is_esselunga(e.get(DBExpensesColumns.MERCHANT.value)):
                continue
            day = ControllerUtils.parse_date(e.get(DBExpensesColumns.DATE.value))
            if day is None:
                continue
            groups.setdefault(day, []).append(e)

        for rows in groups.values():
            total = sum(self._to_float(r.get(DBExpensesColumns.TOTAL_AMOUNT.value)) for r in rows)
            if self._amount_eq(total, amount):
                return rows
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _descriptor(self, rows, kind, merchant_hint):
        total = round(sum(self._to_float(r.get(DBExpensesColumns.TOTAL_AMOUNT.value)) for r in rows), 2)
        first = rows[0]
        existing_merchant = first.get(DBExpensesColumns.MERCHANT.value) or ""
        esselunga = self._is_esselunga(merchant_hint) or any(
            self._is_esselunga(r.get(DBExpensesColumns.MERCHANT.value)) for r in rows
        )
        return {
            "expense_ids": [r.get(DBExpensesColumns.ID.value) for r in rows],
            "kind": kind,
            "existing_total": total,
            "existing_date": first.get(DBExpensesColumns.DATE.value),
            "existing_merchant": existing_merchant,
            "esselunga_hint": esselunga,
        }

    def _within_window(self, date_value, target_date):
        d = ControllerUtils.parse_date(date_value)
        if d is None:
            return False
        return abs((d - target_date).days) <= self.DATE_WINDOW_DAYS

    def _amount_eq(self, a, b):
        # Arrotonda ai centesimi: gli importi sono in euro e il confronto
        # diretto sui float introdurrebbe rumore di rappresentazione al bordo
        # della tolleranza (es. 20.00 - 19.99 = 0.0100000000...0156).
        return round(abs(self._to_float(a) - self._to_float(b)), 2) <= self.AMOUNT_TOLERANCE

    @staticmethod
    def _to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _is_esselunga(text):
        return "esselunga" in (text or "").lower()
