from copy import deepcopy

from Gestionale_Enums import PaymentMethod, Visibility


# ----------------------------------------------------------------------
# Cataloghi (categorie spese/entrate) — editabili dal menu
# ----------------------------------------------------------------------
CATALOGS_DEFAULT = {
    "expense_categories": {
        "ALIMENTARI": "Alimentari e Spesa",
        "CASA_BOLLETTE": "Casa e Bollette",
        "TRASPORTI": "Trasporti",
        "SALUTE": "Salute",
        "RISTORANTI": "Ristoranti e Bar",
        "SVAGO": "Svago e Tempo Libero",
        "ABBIGLIAMENTO": "Abbigliamento",
        "VIAGGI": "Viaggi",
        "ABBONAMENTI": "Abbonamenti",
        "ALTRO": "Altro",
        "ADD_CATEGORY": "AGGIUNGI UNA CATEGORIA ALLA LISTA",
    },
    "income_categories": {
        "STIPENDIO": "Stipendio",
        "BONUS": "Bonus / Premi",
        "RIMBORSO": "Rimborso",
        "REGALO": "Regalo",
        "INVESTIMENTI": "Investimenti",
        "ALTRO": "Altro",
        "ADD_CATEGORY": "AGGIUNGI UNA CATEGORIA ALLA LISTA",
    },
}

# Trigger key (ultima voce "AGGIUNGI…") per ogni sezione catalogo.
CATALOG_ADD_TRIGGERS = {
    "expense_categories": "ADD_CATEGORY",
    "income_categories": "ADD_CATEGORY",
}


# ----------------------------------------------------------------------
# Impostazioni applicative / default utente
# ----------------------------------------------------------------------
APP_SETTINGS_DEFAULT = {
    "general": {
        "collective_name": {
            "value": "DuoPaccotti",
            "description": "Nome del nucleo mostrato nell'interfaccia.",
        },
    },
    "defaults": {
        "default_iva": {
            "value": "0.22",
            "description": "Aliquota IVA predefinita usata per scorporare netto/IVA dalle spese.",
        },
        "default_payment_method": {
            "value": PaymentMethod.CARTA.value,
            "description": "Metodo di pagamento predefinito per le nuove spese.",
        },
        "default_visibility": {
            "value": Visibility.PUBBLICA.value,
            "description": "Visibilita' predefinita delle nuove spese/entrate.",
        },
    },
}


# ----------------------------------------------------------------------
# Hint categorie per il parsing (parola chiave -> chiave categoria)
# ----------------------------------------------------------------------
CATEGORY_HINTS_DEFAULT = {
    "expense_hints": {
        "esselunga": "ALIMENTARI",
        "conad": "ALIMENTARI",
        "coop": "ALIMENTARI",
        "carrefour": "ALIMENTARI",
        "lidl": "ALIMENTARI",
        "farmacia": "SALUTE",
        "enel": "CASA_BOLLETTE",
        "eni": "CASA_BOLLETTE",
        "telepass": "TRASPORTI",
        "trenitalia": "TRASPORTI",
        "italo": "TRASPORTI",
        "netflix": "ABBONAMENTI",
        "spotify": "ABBONAMENTI",
        "amazon": "ALTRO",
    },
}


# ----------------------------------------------------------------------
# Preferenze GUI
# ----------------------------------------------------------------------
DEFAULT_STARTUP_TAB = "Spese"

LIST_VIEWS_PREFERENCES_DEFAULT = {
    "expenses": {"window_index": 0},
    "incomes": {"window_index": 0},
}


def build_gui_preferences_default():
    return {
        "general": {"startup_tab": DEFAULT_STARTUP_TAB},
        "list_views": clone_default_config(LIST_VIEWS_PREFERENCES_DEFAULT),
    }


def clone_default_config(default_config):
    return deepcopy(default_config)
