"""Parser dello scontrino Esselunga (una spesa per scontrino: il totale).

NOTA: implementazione completa nello Step 4 (taratura su
PDFExamples/2026-*.pdf). Per ora espone l'interfaccia e restituisce una
lista vuota.
"""

from ParserServices.base_pdf_parser import BasePdfParser


class EsselungaReceiptParser(BasePdfParser):
    MERCHANT_NAME = "Esselunga"

    def __init__(self, category_hints_manager=None):
        self.category_hints_manager = category_hints_manager

    def parse(self, pdf_path: str) -> list:
        # TODO (Step 4): estrai data + totale dello scontrino -> 1 ParsedMovement.
        return []
