"""Helper trasversali ai controller/service: conversione righe, hashing
password e recovery code, parsing/filtri sulle date.

Riprende l'impianto di ``willowGestionale2.0/Utils/Controller_utils.py``
limitato a cio' che serve al dominio spese/entrate.
"""

import hashlib
import hmac
import secrets
from datetime import datetime


class ControllerUtils:

    DATE_FORMATS = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
    ]

    # ------------------------------------------------------------------
    # Date
    # ------------------------------------------------------------------

    @staticmethod
    def parse_date(date_str):
        """Prova a convertire una stringa in ``date`` (None se non parsabile)."""
        dt = ControllerUtils._parse_datetime(date_str)
        return dt.date() if dt else None

    @staticmethod
    def _parse_datetime(date_str):
        if not date_str:
            return None
        for fmt in ControllerUtils.DATE_FORMATS:
            try:
                return datetime.strptime(str(date_str), fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def is_in_current_year(date_str: str) -> bool:
        dt = ControllerUtils._parse_datetime(date_str)
        return bool(dt and dt.year == datetime.now().year)

    @staticmethod
    def filter_by_year(items, date_key, year: int = None):
        """Filtra ``items`` (lista di dict) per anno sulla colonna ``date_key``.

        year=None -> anno corrente; year=-1 -> nessun filtro.
        """
        if not items or year == -1:
            return items
        target_year = year if year is not None else datetime.now().year
        filtered = []
        for item in items:
            dt = ControllerUtils._parse_datetime(item.get(date_key))
            if dt and dt.year == target_year:
                filtered.append(item)
        return filtered

    # ------------------------------------------------------------------
    # Righe DB
    # ------------------------------------------------------------------

    @staticmethod
    def row_to_map(row, database_columns):
        """Converte una singola riga grezza (tupla) in un dizionario."""
        if row is None:
            return None
        keys = [column.value for column in database_columns]
        return dict(zip(keys, row))

    # ------------------------------------------------------------------
    # Password (PBKDF2 + salt)
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash sicuro con salt casuale; ritorna ``salt_hex + hash_hex``."""
        salt = secrets.token_bytes(32)
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return f"{salt.hex()}{hashed.hex()}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        try:
            salt = bytes.fromhex(stored_hash[:64])
            stored_hashed = bytes.fromhex(stored_hash[64:])
            computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
            return hmac.compare_digest(computed, stored_hashed)
        except Exception as exc:
            print(f"Errore nella verifica password: {exc}")
            return False

    # ------------------------------------------------------------------
    # Recovery code (Crockford base32, ~80 bit)
    # ------------------------------------------------------------------

    _RECOVERY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

    @staticmethod
    def generate_recovery_code() -> str:
        chars = "".join(secrets.choice(ControllerUtils._RECOVERY_ALPHABET) for _ in range(16))
        return f"{chars[0:4]}-{chars[4:8]}-{chars[8:12]}-{chars[12:16]}"

    @staticmethod
    def normalize_recovery_code(code: str) -> str:
        return "".join(ch for ch in code.upper() if ch.isalnum())

    @staticmethod
    def hash_recovery_code(code: str) -> str:
        return ControllerUtils.hash_password(ControllerUtils.normalize_recovery_code(code))

    @staticmethod
    def verify_recovery_code(code: str, stored_hash: str) -> bool:
        if not stored_hash:
            return False
        return ControllerUtils.verify_password(
            ControllerUtils.normalize_recovery_code(code), stored_hash
        )
