"""Parser della lista movimenti IntesaSanpaolo.

Il PDF e' una tabella a 5 colonne (DATA CONTABILE, OPERAZIONE,
CONTABILIZZATO, CATEGORIA, IMPORTO) in cui descrizione e categoria possono
andare a capo su piu' righe. Il parsing su testo "piatto" sarebbe fragile,
quindi ricostruiamo le colonne dalle coordinate x delle parole
(``extract_words``):

- ogni movimento ha una *riga di ancoraggio* che contiene sia la data sia
  l'importo;
- le righe di continuazione (descrizione/categoria a capo) vengono
  attribuite all'ancora verticalmente piu' vicina.

Importa sia le USCITE (importo negativo) come spese sia le ENTRATE (importo
positivo) come entrate: il segno determina ``kind`` e la categoria suggerita.
"""

import re

from ParserServices.base_pdf_parser import BasePdfParser
from ParserServices.parse_utils import to_float
from ParserServices.parsed_movement import ParsedMovement

_DATE_RE = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")

# Soglie x (in punti PDF) dei confini di colonna, tarate sul formato Intesa.
_X_OP = 120.0       # < => DATA
_X_CONTAB = 325.0   # < => OPERAZIONE
_X_CAT = 392.0      # < => CONTABILIZZATO
_X_IMP = 500.0      # < => CATEGORIA ; >= => IMPORTO

_ROW_TOL = 4.0      # parole entro questa distanza di top stanno sulla stessa riga
_HEADER_TOKENS = {"OPERAZIONE", "CONTABILIZZATO", "CATEGORIA", "IMPORTO", "CONTABILE"}

# Categoria Intesa -> chiave del nostro catalogo expense_categories.
_INTESA_CATEGORY_MAP = (
    ("aliment", "ALIMENTARI"),
    ("supermercato", "ALIMENTARI"),
    ("ristoranti", "RISTORANTI"),
    ("bar", "RISTORANTI"),
    ("carburant", "TRASPORTI"),
    ("pedaggi", "TRASPORTI"),
    ("telepass", "TRASPORTI"),
    ("trasporti", "TRASPORTI"),
    ("noleggi", "TRASPORTI"),
    ("taxi", "TRASPORTI"),
    ("parcheggi", "TRASPORTI"),
    ("abbigliamento", "ABBIGLIAMENTO"),
    ("spese mediche", "SALUTE"),
    ("salute", "SALUTE"),
    ("farmac", "SALUTE"),
    ("corsi e sport", "SVAGO"),
    ("sport", "SVAGO"),
    ("svago", "SVAGO"),
    ("tv, internet", "ABBONAMENTI"),
    ("telefono", "ABBONAMENTI"),
    ("hi-tech", "ABBONAMENTI"),
    ("informatica", "ABBONAMENTI"),
    ("condominiali", "CASA_BOLLETTE"),
    ("elettrodomestic", "CASA_BOLLETTE"),
    ("arredamento", "CASA_BOLLETTE"),
    ("giardino", "CASA_BOLLETTE"),
    ("viaggi", "VIAGGI"),
)

# Categoria Intesa -> chiave del nostro catalogo income_categories (entrate).
_INTESA_INCOME_MAP = (
    ("stipend", "STIPENDIO"),
    ("pension", "STIPENDIO"),
    ("salvadanaio", "INVESTIMENTI"),
    ("disinvestiment", "INVESTIMENTI"),
    ("investiment", "INVESTIMENTI"),
    ("rimbors", "RIMBORSO"),
    ("bonus", "BONUS"),
    ("regal", "REGALO"),
)


class BankStatementParser(BasePdfParser):
    BANK_NAME = "IntesaSanpaolo"

    def __init__(self, category_hints_manager=None):
        self.category_hints_manager = category_hints_manager

    def parse(self, pdf_path: str) -> list:
        import pdfplumber

        movements = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                movements.extend(self._parse_page(page))
        return movements

    # ------------------------------------------------------------------

    def _parse_page(self, page) -> list:
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
        if not words:
            return []

        header_bottom = max(
            (w["bottom"] for w in words if w["text"] in _HEADER_TOKENS),
            default=0.0,
        )
        data_words = [w for w in words if w["top"] > header_bottom + 2]
        if not data_words:
            return []

        rows = self._cluster_rows(data_words)
        anchors = [r for r in rows if r["date"]]
        if not anchors:
            return []

        anchor_tops = [r["top"] for r in anchors]
        buckets = {r["top"]: [] for r in anchors}
        for row in rows:
            nearest = min(anchor_tops, key=lambda at: abs(at - row["top"]))
            buckets[nearest].append(row)

        movements = []
        for anchor in anchors:
            movement = self._build_movement(anchor, buckets[anchor["top"]])
            if movement is not None:
                movements.append(movement)
        return movements

    def _cluster_rows(self, words) -> list:
        """Raggruppa le parole in righe visive (per ``top``) e le distribuisce
        nelle 5 colonne in base alla x."""
        ordered = sorted(words, key=lambda w: (w["top"], w["x0"]))
        rows = []
        current = None
        for w in ordered:
            if current is None or abs(w["top"] - current["top"]) > _ROW_TOL:
                current = {"top": w["top"], "words": []}
                rows.append(current)
            current["words"].append(w)

        result = []
        for row in rows:
            date_txt = ""
            op, cat, imp = [], [], []
            contab = ""
            for w in sorted(row["words"], key=lambda x: x["x0"]):
                x0, text = w["x0"], w["text"]
                if x0 < _X_OP:
                    if _DATE_RE.search(text):
                        date_txt = text
                elif x0 < _X_CONTAB:
                    op.append(text)
                elif x0 < _X_CAT:
                    contab = text
                elif x0 < _X_IMP:
                    cat.append(text)
                else:
                    imp.append(text)
            result.append({
                "top": row["top"],
                "date": date_txt,
                "op": op,
                "contab": contab,
                "cat": cat,
                "imp": imp,
            })
        return result

    def _build_movement(self, anchor, rows):
        amount = to_float(" ".join(anchor["imp"]))
        if amount is None or amount == 0:
            return None

        date = self._iso_date(anchor["date"])
        ordered_rows = sorted(rows, key=lambda r: r["top"])
        description = " ".join(t for r in ordered_rows for t in r["op"]).strip()
        category_text = " ".join(t for r in ordered_rows for t in r["cat"]).strip()
        if not description:
            description = "Movimento bancario"

        # Segno: negativo => uscita (spesa); positivo => entrata.
        if amount < 0:
            kind = "expense"
            category = self._map_category(category_text, description)
        else:
            kind = "income"
            category = self._map_income_category(category_text)

        return ParsedMovement(
            date=date,
            amount=round(abs(amount), 2),
            description=description,
            merchant="",
            suggested_category=category,
            kind=kind,
            raw_text=f"{date} | {description} | {category_text} | {amount}",
        )

    @staticmethod
    def _iso_date(date_txt: str) -> str:
        match = _DATE_RE.search(date_txt or "")
        if not match:
            from datetime import date as _date
            return _date.today().strftime("%Y-%m-%d")
        day, month, year = match.group(1), match.group(2), match.group(3)
        return f"{year}-{month}-{day}"

    def _map_category(self, category_text: str, description: str) -> str:
        lowered = (category_text or "").lower()
        for keyword, key in _INTESA_CATEGORY_MAP:
            if keyword in lowered:
                return key
        if self.category_hints_manager is not None:
            return self.category_hints_manager.suggest_category(description, fallback="ALTRO")
        return "ALTRO"

    @staticmethod
    def _map_income_category(category_text: str) -> str:
        lowered = (category_text or "").lower()
        for keyword, key in _INTESA_INCOME_MAP:
            if keyword in lowered:
                return key
        return "ALTRO"
