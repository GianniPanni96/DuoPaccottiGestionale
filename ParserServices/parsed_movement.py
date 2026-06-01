"""Riga candidata prodotta dai parser PDF, mostrata in preview e
modificabile prima del salvataggio."""

from dataclasses import dataclass, field


@dataclass
class ParsedMovement:
    date: str                       # "YYYY-MM-DD"
    amount: float                   # importo positivo
    description: str
    merchant: str = ""
    suggested_category: str = "ALTRO"
    kind: str = "expense"           # "expense" | "income"
    raw_text: str = ""
    include: bool = True            # selezionato per il salvataggio
    operation: str = ""             # testo OPERAZIONE grezzo dal PDF (chiave per operation_labels.json)

    def to_expense_data(self, user_id: int, source: str) -> dict:
        from Gestionale_Enums import DBExpensesColumns
        return {
            DBExpensesColumns.DESCRIPTION.value: self.description,
            DBExpensesColumns.USER_ID.value: user_id,
            DBExpensesColumns.CATEGORY.value: self.suggested_category,
            DBExpensesColumns.MERCHANT.value: self.merchant,
            DBExpensesColumns.TOTAL_AMOUNT.value: self.amount,
            DBExpensesColumns.DATE.value: self.date,
            DBExpensesColumns.SOURCE.value: source,
        }
