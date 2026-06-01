"""Strutture dati per lo scontrino Esselunga 'a voci' (itemized).

Lo scontrino viene mostrato voce per voce: l'utente assegna ogni articolo a
una delle due categorie predefinite (Cibo / Consumabili Casa) e dallo
scontrino vengono create due spese separate (i due totali)."""

from dataclasses import dataclass, field


@dataclass
class ReceiptItem:
    description: str
    price: float                 # puo' essere negativo (sconti)
    category_key: str = "CIBO"   # assegnazione di default, modificabile in UI


@dataclass
class EsselungaReceipt:
    date: str                    # "YYYY-MM-DD"
    items: list = field(default_factory=list)   # list[ReceiptItem]
    total: float = 0.0
    iva: float = 0.0
    merchant: str = "Esselunga"

    def items_total(self) -> float:
        return round(sum(i.price for i in self.items), 2)
