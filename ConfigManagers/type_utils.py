from copy import deepcopy


MISSING = object()


def merge_with_defaults(data, defaults):
    """Sovrappone ``data`` sui ``defaults`` in modo ricorsivo: le chiavi
    mancanti vengono riempite dal default, le chiavi extra preservate."""
    if isinstance(defaults, dict):
        result = deepcopy(defaults)
        if not isinstance(data, dict):
            return result
        for key, value in data.items():
            if key in defaults:
                result[key] = merge_with_defaults(value, defaults[key])
            else:
                result[key] = deepcopy(value)
        return result
    return deepcopy(data)


def coerce_to_int(value, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def coerce_to_float(value, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
