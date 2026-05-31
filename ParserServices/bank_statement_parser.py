"""Parser dell'estratto/lista operazioni IntesaSanpaolo.

NOTA: implementazione completa nello Step 4 (taratura su
PDFExamples/lista_operazioni_*.pdf). Per ora espone l'interfaccia e
restituisce una lista vuota, cosi' l'app e' avviabile e cablata.
"""

from ParserServices.base_pdf_parser import BasePdfParser


class BankStatementParser(BasePdfParser):
    BANK_NAME = "IntesaSanpaolo"

    def __init__(self, category_hints_manager=None):
        self.category_hints_manager = category_hints_manager

    def parse(self, pdf_path: str) -> list:
        # TODO (Step 4): regex/euristiche sul formato lista operazioni Intesa.
        return []
