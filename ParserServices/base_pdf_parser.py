"""Interfaccia comune dei parser PDF.

Aggiungere il supporto a un nuovo formato (altra banca, altro scontrino)
significa scrivere una sottoclasse che implementa ``parse``: l'isolamento
e' garantito da questa base.
"""

from __future__ import annotations


class BasePdfParser:
    def parse(self, pdf_path: str) -> list:
        """Estrae la lista di ``ParsedMovement`` dal PDF."""
        raise NotImplementedError

    @staticmethod
    def extract_text(pdf_path: str) -> str:
        """Testo concatenato di tutte le pagine (import locale di
        pdfplumber per non rallentare l'avvio dell'app)."""
        import pdfplumber

        parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts)

    @staticmethod
    def extract_lines(pdf_path: str) -> list[str]:
        text = BasePdfParser.extract_text(pdf_path)
        return [line.rstrip() for line in text.splitlines()]
