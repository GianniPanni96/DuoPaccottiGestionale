"""Enum di dominio e degli schemi tabellari.

Unica fonte di verita' per i nomi delle colonne del DB: il Model
costruisce le query filtrando i ``**kwargs`` sulle colonne valide di
questi enum, e ``ControllerUtils.row_to_map`` li usa per convertire le
tuple grezze in dizionari leggibili.

SE MODIFICHI UN ENUM DI COLONNE devi aggiornare anche ``Schema.py``.
"""

from enum import Enum


# ----------------------------------------------------------------------
# Enum di dominio
# ----------------------------------------------------------------------

class UserStatus(Enum):
    ATTIVO = "attivo"
    DISATTIVO = "disattivo"


class Visibility(Enum):
    """Visibilita' di una spesa/entrata verso gli altri utenti loggati."""
    PUBBLICA = "PUBBLICA"   # visibile agli altri utenti
    PRIVATA = "PRIVATA"     # visibile solo al proprietario


class PaymentMethod(Enum):
    CONTANTI = "CONTANTI"
    CARTA = "CARTA"
    BONIFICO = "BONIFICO"
    ALTRO = "ALTRO"


class ExpenseSource(Enum):
    """Provenienza del dato spesa (tracciabilita')."""
    MANUALE = "MANUALE"
    SCONTRINO = "SCONTRINO"
    ESTRATTO_BANCA = "ESTRATTO_BANCA"


class IncomeSource(Enum):
    MANUALE = "MANUALE"
    ESTRATTO_BANCA = "ESTRATTO_BANCA"


# ----------------------------------------------------------------------
# Enum colonne DB
# ----------------------------------------------------------------------

class DBUsersColumns(Enum):
    ID = "id"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    EMAIL = "email"
    TELEFONO = "telefono"
    PHOTO_PATH = "photo_path"
    PASSWORD_LOGIN = "password_login"      # hash PBKDF2 (salt+hash hex)
    RECOVERY_HASH = "recovery_hash"        # hash PBKDF2 del recovery code
    DEFAULT_VISIBILITY = "default_visibility"  # default per le nuove spese/entrate
    STATUS = "status"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class DBExpensesColumns(Enum):
    ID = "id"
    DESCRIPTION = "description"
    USER_ID = "user_id"                    # proprietario (chi registra la spesa)
    CATEGORY = "category"                  # chiave del catalogo expense_categories
    MERCHANT = "merchant"                  # esercente/negozio (free text)
    TOTAL_AMOUNT = "total_amount"          # importo lordo
    NET_AMOUNT = "net_amount"              # opzionale
    IVA_AMOUNT = "iva_amount"              # opzionale
    DATE = "date"
    PAYMENT_METHOD = "payment_method"
    IS_SHARED = "is_shared"                # 0/1
    ADVANCED_BY_USER_ID = "advanced_by_user_id"  # chi ha anticipato la spesa condivisa
    IS_SETTLED = "is_settled"              # 0/1 - spesa condivisa interamente saldata (cache)
    VISIBILITY = "visibility"
    SOURCE = "source"
    NOTE = "note"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class DBExpenseSharesColumns(Enum):
    """Quote di una spesa condivisa: partecipante <-> percentuale."""
    ID = "id"
    EXPENSE_ID = "expense_id"
    USER_ID = "user_id"                    # partecipante
    PERCENTAGE = "percentage"              # quota (somma quote di una spesa = 1.0)
    AMOUNT = "amount"                      # = percentage * total_amount (denormalizzato)
    IS_SETTLED = "is_settled"              # 0/1 - quota restituita all'anticipatore
    SETTLED_AT = "settled_at"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class DBIncomesColumns(Enum):
    ID = "id"
    DESCRIPTION = "description"
    USER_ID = "user_id"
    CATEGORY = "category"                  # chiave del catalogo income_categories
    AMOUNT = "amount"
    DATE = "date"
    VISIBILITY = "visibility"
    SOURCE = "source"
    NOTE = "note"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class DBAdminColumns(Enum):
    """Tabella admin: singolo amministratore di sistema (no dati cifrati)."""
    ID = "id"
    NAME = "name"
    PASSWORD_LOGIN = "password_login"
    RECOVERY_HASH = "recovery_hash"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


ADMIN_FIXED_NAME = "ADMIN"
