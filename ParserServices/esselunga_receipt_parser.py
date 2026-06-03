"""Parser dello scontrino Esselunga.

Due livelli di lettura:
- ``parse`` (interfaccia base): una spesa unica = il totale dello scontrino;
- ``parse_receipt``: lettura 'a voci' (articoli + prezzi + metodi di pagamento)
  per la view che permette di assegnare ogni articolo a Cibo o Consumabili Casa
  e di attribuire le quote pagate con metodi diversi a utenti diversi.

Se il PDF non e' riconoscibile come scontrino, ``parse_receipt`` solleva
``ReceiptParseError`` (la view lo mostra come popup di errore all'utente).
"""

import re

from ParserServices.base_pdf_parser import BasePdfParser
from ParserServices.esselunga_receipt import EsselungaReceipt, ReceiptItem, ReceiptPayment
from ParserServices.parse_utils import to_float
from ParserServices.parsed_movement import ParsedMovement

_TOTAL_RE = re.compile(r"TOTALE\s+EURO\s+([\d.]+,\d{2})", re.IGNORECASE)
_IVA_RE = re.compile(r"di\s+cui\s+IVA\s+([\d.]+,\d{2})", re.IGNORECASE)
_DATE_DASH_RE = re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\b")
_DATE_SLASH_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")

# Riga articolo: "<descrizione> *a 1,98"  (il marcatore *a/*c/*d = aliquota IVA)
_ARTICLE_RE = re.compile(r"^(?P<desc>.+?)\s+\*[a-zA-Z]\s+(?P<price>\d+,\d{2})$")
# Riga di storno (sconti, buoni spesa): "SCONTO 30% 0,69-S", "BUONO SPESA 6,00-S".
# Qualsiasi descrizione seguita da "<prezzo>-<lettera>" a fine riga.
_DISCOUNT_RE = re.compile(r"^(?P<desc>.+?)\s+(?P<price>\d+,\d{2})-[A-Z]$")
# Riga pagamento: "PAGAMENTO BANCOMAT 110,32", "PAGAMENTO BUONO PASTO ELETTRON 56,00"
_PAYMENT_RE = re.compile(r"^PAGAMENTO\s+(?P<method>.+?)\s+(?P<amount>\d[\d.]*,\d{2})$", re.IGNORECASE)
# Marcatore buono pasto/ticket all'interno dell'etichetta del metodo.
_MEAL_VOUCHER_RE = re.compile(r"buono\s+pasto|buoni\s+pasto|ticket", re.IGNORECASE)


class ReceiptParseError(Exception):
    """Il PDF non e' uno scontrino Esselunga analizzabile.

    Trasporta un messaggio leggibile mostrato come popup di errore all'utente."""


class EsselungaReceiptParser(BasePdfParser):
    MERCHANT_NAME = "Esselunga"

    def __init__(self, category_hints_manager=None):
        self.category_hints_manager = category_hints_manager

    # ------------------------------------------------------------------
    # Interfaccia base: una spesa = il totale
    # ------------------------------------------------------------------

    def parse(self, pdf_path: str) -> list:
        text = self.extract_text(pdf_path)
        if not text:
            return []
        total = self._extract_total(text)
        if total is None or total <= 0:
            return []
        return [ParsedMovement(
            date=self._extract_date(text),
            amount=round(total, 2),
            description="Spesa Esselunga",
            merchant=self.MERCHANT_NAME,
            suggested_category="ALIMENTARI",
            kind="expense",
            raw_text=text[:500],
        )]

    # ------------------------------------------------------------------
    # Lettura a voci
    # ------------------------------------------------------------------

    def parse_receipt(self, pdf_path: str) -> EsselungaReceipt:
        lines = self.extract_lines(pdf_path)
        text = "\n".join(lines)
        if not text.strip():
            raise ReceiptParseError("Impossibile leggere il contenuto del PDF.")

        items = []
        payments = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            article = _ARTICLE_RE.match(stripped)
            if article:
                price = to_float(article.group("price"))
                if price is not None:
                    items.append(ReceiptItem(article.group("desc").strip(), round(price, 2)))
                continue
            discount = _DISCOUNT_RE.match(stripped)
            if discount:
                price = to_float(discount.group("price"))
                if price is not None:
                    items.append(ReceiptItem(discount.group("desc").strip(), round(-price, 2)))
                continue
            payment = _PAYMENT_RE.match(stripped)
            if payment:
                amount = to_float(payment.group("amount"))
                if amount is not None:
                    method = payment.group("method").strip()
                    payments.append(ReceiptPayment(
                        method=method,
                        amount=round(amount, 2),
                        is_meal_voucher=bool(_MEAL_VOUCHER_RE.search(method)),
                    ))

        total = self._extract_total(text)
        if not items and total is None:
            raise ReceiptParseError(
                "Il PDF selezionato non sembra uno scontrino Esselunga riconoscibile."
            )
        if not items:
            raise ReceiptParseError(
                "Nessun articolo riconosciuto nello scontrino: impossibile importarlo."
            )

        return EsselungaReceipt(
            date=self._extract_date(text),
            items=items,
            total=total or round(sum(i.price for i in items), 2),
            iva=self._extract_iva(text) or 0.0,
            merchant=self.MERCHANT_NAME,
            payments=payments,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _extract_total(text: str):
        match = _TOTAL_RE.search(text)
        return to_float(match.group(1)) if match else None

    @staticmethod
    def _extract_iva(text: str):
        match = _IVA_RE.search(text)
        return to_float(match.group(1)) if match else None

    @staticmethod
    def _extract_date(text: str) -> str:
        match = _DATE_DASH_RE.search(text) or _DATE_SLASH_RE.search(text)
        if not match:
            from datetime import date as _date
            return _date.today().strftime("%Y-%m-%d")
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
