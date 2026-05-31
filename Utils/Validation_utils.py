import re


class ValidationUtils:
    @staticmethod
    def validate_email(email):
        """Valida un indirizzo email."""
        return bool(re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email))

    @staticmethod
    def validate_phone_number(phone_number):
        """Solo cifre, lunghezza 8-15."""
        return isinstance(phone_number, str) and phone_number.isdigit() and 8 <= len(phone_number) <= 15

    @staticmethod
    def validate_amount(amount):
        """True se ``amount`` e' una stringa numerica non negativa con al
        massimo due decimali (es. "100", "100.5", "100.50")."""
        if not isinstance(amount, str):
            return False
        return re.fullmatch(r"^\d+(\.\d{1,2})?$", amount) is not None

    @staticmethod
    def validate_integers(value):
        """True se ``value`` (stringa) e' convertibile in intero."""
        return isinstance(value, str) and value.isdigit()

    @staticmethod
    def validate_percentage(value):
        """True se ``value`` rappresenta una percentuale 0..100 (anche float)."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False
        return 0.0 <= v <= 100.0

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """Criteri minimi di sicurezza della password (>= 8 caratteri)."""
        if password is None or len(password) < 8:
            return False, "La password deve essere lunga almeno 8 caratteri"
        return True, ""

    @staticmethod
    def _row_to_map(row, database_columns):
        """Converte una singola riga grezza in un dizionario."""
        if row is None:
            return None
        keys = [column.value for column in database_columns]
        return dict(zip(keys, row))
