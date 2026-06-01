"""Helper condivisi dai parser PDF."""

import re

_AMOUNT_RE = re.compile(r"-?\d[\d.]*,\d{2}")


def to_float(raw: str) -> float | None:
    """Converte un importo all'italiana ('1.663,00', '-80,00') in float.

    Restituisce ``None`` se non interpretabile."""
    if raw is None:
        return None
    match = _AMOUNT_RE.search(raw)
    if not match:
        return None
    token = match.group(0).replace(".", "").replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


def find_amount(text: str) -> float | None:
    return to_float(text)
