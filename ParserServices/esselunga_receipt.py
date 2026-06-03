"""Strutture dati per lo scontrino Esselunga 'a voci' (itemized).

Lo scontrino viene mostrato voce per voce: l'utente assegna ogni articolo a
una delle due categorie predefinite (Cibo / Consumabili Casa) e dallo
scontrino vengono create spese separate.

Sullo scontrino sono riportati anche i metodi di pagamento (``payments``):
parte della spesa puo' essere pagata con buoni pasto, che per legge coprono
solo generi alimentari. La view usa questa informazione per attribuire le
quote pagate da utenti diversi (vedi ``QTEsselungaImportDialog``)."""

from dataclasses import dataclass, field


@dataclass
class ReceiptItem:
    description: str
    price: float                 # puo' essere negativo (sconti)
    category_key: str = "CIBO"   # assegnazione di default, modificabile in UI


@dataclass
class ReceiptPayment:
    """Un metodo di pagamento riportato sullo scontrino."""
    method: str                  # etichetta grezza, es. "BANCOMAT", "BUONO PASTO ELETTRON"
    amount: float
    is_meal_voucher: bool = False  # True per buoni pasto/ticket (solo alimentari)


@dataclass
class EsselungaReceipt:
    date: str                    # "YYYY-MM-DD"
    items: list = field(default_factory=list)      # list[ReceiptItem]
    total: float = 0.0
    iva: float = 0.0
    merchant: str = "Esselunga"
    payments: list = field(default_factory=list)   # list[ReceiptPayment]

    def items_total(self) -> float:
        return round(sum(i.price for i in self.items), 2)

    def meal_voucher_total(self) -> float:
        return round(sum(p.amount for p in self.payments if p.is_meal_voucher), 2)

    def has_meal_voucher(self) -> bool:
        return any(p.is_meal_voucher for p in self.payments)

    def has_multiple_payments(self) -> bool:
        return len(self.payments) > 1
