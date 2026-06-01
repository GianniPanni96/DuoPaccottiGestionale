"""Parser dello scontrino Esselunga.

Due livelli di lettura:
- ``parse`` (interfaccia base): una spesa unica = il totale dello scontrino;
- ``parse_receipt``: lettura 'a voci' (articoli + prezzi) per la view che
  permette di assegnare ogni articolo a Cibo o Consumabili Casa e salvare
  due spese separate.
"""

import re

from ParserServices.base_pdf_parser import BasePdfParser
from ParserServices.esselunga_receipt import EsselungaReceipt, ReceiptItem
from ParserServices.parse_utils import to_float
from ParserServices.parsed_movement import ParsedMovement

_TOTAL_RE = re.compile(r"TOTALE\s+EURO\s+([\d.]+,\d{2})", re.IGNORECASE)
_IVA_RE = re.compile(r"di\s+cui\s+IVA\s+([\d.]+,\d{2})", re.IGNORECASE)
_DATE_DASH_RE = re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\b")
_DATE_SLASH_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")

# Riga articolo: "<descrizione> *a 1,98"  (il marcatore *a/*c/*d = aliquota IVA)
_ARTICLE_RE = re.compile(r"^(?P<desc>.+?)\s+\*[a-zA-Z]\s+(?P<price>\d+,\d{2})$")
# Riga sconto: "SCONTO 30% 0,69-S"
_DISCOUNT_RE = re.compile(r"^(?P<desc>SCONTO.*?)\s+(?P<price>\d+,\d{2})-[A-Z]$", re.IGNORECASE)


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
        items = []
        for line in lines:
            stripped = line.strip()
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

        return EsselungaReceipt(
            date=self._extract_date(text),
            items=items,
            total=self._extract_total(text) or round(sum(i.price for i in items), 2),
            iva=self._extract_iva(text) or 0.0,
            merchant=self.MERCHANT_NAME,
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
