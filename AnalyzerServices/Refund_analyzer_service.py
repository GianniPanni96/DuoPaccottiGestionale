"""Analisi 4 del SCOPO: calcolo dei rimborsi (chi-deve-a-chi).

Per ogni spesa condivisa con un anticipatore, ciascun partecipante
diverso dall'anticipatore gli deve la propria quota finche' non e'
saldata. I debiti reciproci tra due utenti vengono nettati.
"""

from Gestionale_Enums import (
    DBExpenseSharesColumns,
    DBExpensesColumns,
    DBUsersColumns,
)


class RefundAnalyzerService:
    def __init__(self, expenses_query_service, expense_shares_query_service, users_query_service):
        self.expenses_query_service = expenses_query_service
        self.expense_shares_query_service = expense_shares_query_service
        self.users_query_service = users_query_service

    def compute_raw_debts(self) -> dict:
        """{(debtor_id, creditor_id): importo} prima del netting."""
        raw = {}
        shared = self.expenses_query_service.retrieve_shared_expenses(year=-1)
        for expense in shared:
            advancer = expense.get(DBExpensesColumns.ADVANCED_BY_USER_ID.value)
            if not advancer:
                continue
            expense_id = expense.get(DBExpensesColumns.ID.value)
            shares = self.expense_shares_query_service.retrieve_shares_for_expense(expense_id)
            for share in shares:
                debtor = share.get(DBExpenseSharesColumns.USER_ID.value)
                if debtor == advancer:
                    continue
                if share.get(DBExpenseSharesColumns.IS_SETTLED.value):
                    continue
                amount = float(share.get(DBExpenseSharesColumns.AMOUNT.value) or 0.0)
                if amount <= 0:
                    continue
                key = (debtor, advancer)
                raw[key] = raw.get(key, 0.0) + amount
        return raw

    def compute_balances(self) -> dict:
        """{(debtor_id, creditor_id): importo} dopo il netting reciproco
        (solo importi positivi)."""
        raw = self.compute_raw_debts()
        seen = set()
        netted = {}
        for (a, b), amount in raw.items():
            if (a, b) in seen or (b, a) in seen:
                continue
            seen.add((a, b))
            reverse = raw.get((b, a), 0.0)
            net = amount - reverse
            if net > 0.005:
                netted[(a, b)] = round(net, 2)
            elif net < -0.005:
                netted[(b, a)] = round(-net, 2)
        return netted

    def build_summary_rows(self) -> list:
        """Lista di dict {debtor_name, creditor_name, amount} per la UI."""
        names = self._user_names()
        rows = []
        for (debtor, creditor), amount in self.compute_balances().items():
            rows.append({
                "debtor_id": debtor,
                "creditor_id": creditor,
                "debtor_name": names.get(debtor, f"Utente {debtor}"),
                "creditor_name": names.get(creditor, f"Utente {creditor}"),
                "amount": amount,
            })
        return rows

    def _user_names(self) -> dict:
        names = {}
        for user in self.users_query_service.retrieve_users_map_list():
            names[user[DBUsersColumns.ID.value]] = (
                f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"
            )
        return names

    # ------------------------------------------------------------------
    # Dettaglio per finestra temporale (tab Rimborsi)
    # ------------------------------------------------------------------

    @staticmethod
    def _expense_day(expense) -> str:
        return (expense.get(DBExpensesColumns.DATE.value) or "")[:10]

    def _debt_shares_in_window(self, start_date: str, end_date: str):
        """Itera le quote-debito (partecipante != anticipatore, importo > 0)
        delle spese condivise la cui data cade in [start_date, end_date].

        Restituisce tuple (expense, share)."""
        for expense in self.expenses_query_service.retrieve_shared_expenses(year=-1):
            advancer = expense.get(DBExpensesColumns.ADVANCED_BY_USER_ID.value)
            if not advancer:
                continue
            day = self._expense_day(expense)
            if not day or day < start_date or day > end_date:
                continue
            expense_id = expense.get(DBExpensesColumns.ID.value)
            for share in self.expense_shares_query_service.retrieve_shares_for_expense(expense_id):
                debtor = share.get(DBExpenseSharesColumns.USER_ID.value)
                if debtor == advancer:
                    continue
                amount = float(share.get(DBExpenseSharesColumns.AMOUNT.value) or 0.0)
                if amount <= 0:
                    continue
                yield expense, share

    def build_window_detail(self, start_date: str, end_date: str) -> dict:
        """Dettaglio voce-per-voce dei rimborsi per la finestra indicata.

        Returns dict con:
        - ``rows``: lista item {share_id, expense_id, date, description,
          debtor_id/creditor_id (+ nomi), amount, settled};
        - ``pair_totals``: {(debtor,creditor): {outstanding, settled, total}};
        - ``total_outstanding``: somma di quanto resta da rimborsare;
        - ``unsettled_share_ids``: quote ancora da saldare (per 'segna tutti')."""
        names = self._user_names()
        rows = []
        pair_totals = {}
        unsettled_share_ids = []

        for expense, share in self._debt_shares_in_window(start_date, end_date):
            advancer = expense.get(DBExpensesColumns.ADVANCED_BY_USER_ID.value)
            debtor = share.get(DBExpenseSharesColumns.USER_ID.value)
            amount = round(float(share.get(DBExpenseSharesColumns.AMOUNT.value) or 0.0), 2)
            settled = bool(share.get(DBExpenseSharesColumns.IS_SETTLED.value))
            share_id = share.get(DBExpenseSharesColumns.ID.value)

            rows.append({
                "share_id": share_id,
                "expense_id": expense.get(DBExpensesColumns.ID.value),
                "date": self._expense_day(expense),
                "description": expense.get(DBExpensesColumns.DESCRIPTION.value) or "—",
                "debtor_id": debtor,
                "creditor_id": advancer,
                "debtor_name": names.get(debtor, f"Utente {debtor}"),
                "creditor_name": names.get(advancer, f"Utente {advancer}"),
                "amount": amount,
                "settled": settled,
            })

            key = (debtor, advancer)
            tot = pair_totals.setdefault(key, {"outstanding": 0.0, "settled": 0.0, "total": 0.0})
            tot["total"] += amount
            if settled:
                tot["settled"] += amount
            else:
                tot["outstanding"] += amount
                unsettled_share_ids.append(share_id)

        rows.sort(key=lambda r: (r["creditor_name"], r["debtor_name"], r["date"]))
        for tot in pair_totals.values():
            for k in tot:
                tot[k] = round(tot[k], 2)
        total_outstanding = round(sum(t["outstanding"] for t in pair_totals.values()), 2)

        return {
            "rows": rows,
            "pair_totals": pair_totals,
            "names": names,
            "total_outstanding": total_outstanding,
            "unsettled_share_ids": unsettled_share_ids,
        }

    def count_outstanding_before(self, start_date: str) -> int:
        """Numero di quote ancora da saldare con data anteriore alla finestra
        corrente (per segnalare sospesi nei periodi precedenti)."""
        count = 0
        for expense, share in self._debt_shares_in_window("0000-00-00", start_date):
            if share.get(DBExpenseSharesColumns.IS_SETTLED.value):
                continue
            # _debt_shares_in_window e' inclusivo su end: escludo il giorno start.
            if self._expense_day(expense) >= start_date:
                continue
            count += 1
        return count
