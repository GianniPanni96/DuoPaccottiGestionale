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
