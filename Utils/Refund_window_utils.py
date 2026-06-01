"""Calcolo delle finestre temporali dei rimborsi.

Dato un tipo di finestra (SETTIMANALE/MENSILE/TRIMESTRALE/ANNUALE) e un
``offset`` rispetto al periodo corrente (0 = corrente, -1 = precedente,
...), restituisce gli estremi ISO ``yyyy-mm-dd`` e un'etichetta leggibile.
Neutro rispetto alla UI."""

import calendar
from datetime import date, timedelta

_MONTHS_IT = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]

WINDOW_LABELS = {
    "SETTIMANALE": "Settimanale",
    "MENSILE": "Mensile",
    "TRIMESTRALE": "Trimestrale",
    "ANNUALE": "Annuale",
}


def _iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _ddmm(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def window_bounds(window_type: str, offset: int, today: date | None = None):
    """Returns (start_iso, end_iso, label) per la finestra richiesta."""
    window_type = (window_type or "MENSILE").upper()
    today = today or date.today()

    if window_type == "SETTIMANALE":
        week_start = today - timedelta(days=today.weekday())
        start = week_start + timedelta(weeks=offset)
        end = start + timedelta(days=6)
        return _iso(start), _iso(end), f"Settimana {_ddmm(start)} – {_ddmm(end)}"

    if window_type == "ANNUALE":
        year = today.year + offset
        return f"{year}-01-01", f"{year}-12-31", f"Anno {year}"

    if window_type == "TRIMESTRALE":
        base_q = (today.month - 1) // 3              # 0..3
        total = today.year * 4 + base_q + offset
        year, q = divmod(total, 4)
        start_month = q * 3 + 1
        end_month = start_month + 2
        last_day = calendar.monthrange(year, end_month)[1]
        start = date(year, start_month, 1)
        end = date(year, end_month, last_day)
        return _iso(start), _iso(end), f"T{q + 1} {year} ({_MONTHS_IT[start_month - 1][:3]}–{_MONTHS_IT[end_month - 1][:3]})"

    # MENSILE (default)
    total = today.year * 12 + (today.month - 1) + offset
    year, month_idx = divmod(total, 12)
    month = month_idx + 1
    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)
    return _iso(start), _iso(end), f"{_MONTHS_IT[month - 1]} {year}"
