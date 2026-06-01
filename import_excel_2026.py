"""Script one-shot: importa le spese da 'Spese condivise 2026.xlsx' nel DB.

Esecuzione:
    python import_excel_2026.py

- Aggiorna catalogs.json con le categorie trovate nel foglio.
- Inserisce le spese nel DB (0 spese presenti = no duplicati).
- Coppie (stessa data/importo/tipologia, pagate da entrambi): una sola
  spesa condivisa già saldata con due quote is_settled=1.
- Spese SPLIT singole: condivisa non saldata, quote 50/50.
- Spese PERSONALE: non condivise.
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import openpyxl

# ---------------------------------------------------------------------------
# Percorsi
# ---------------------------------------------------------------------------
DATA_PATH_ENV = "DUOPACCOTTI_DATA_PATH"
env_val = os.environ.get(DATA_PATH_ENV)
if env_val:
    DATA_DIR = Path(env_val).expanduser()
else:
    DATA_DIR = Path(__file__).parent

DB_PATH    = DATA_DIR / "duopaccotti.db"
CATS_PATH  = DATA_DIR / "catalogs.json"
EXCEL_PATH = Path(r"C:\Users\Gianni\Downloads\Spese condivise 2026.xlsx")

print(f"DB:      {DB_PATH}")
print(f"Cats:    {CATS_PATH}")
print(f"Excel:   {EXCEL_PATH}")

# ---------------------------------------------------------------------------
# Mapping tipologie Excel → chiave categoria DB
# ---------------------------------------------------------------------------
TIPOLOGIA_TO_KEY = {
    "Palestra":             "PALESTRA",
    "Elettrodomestici":     "ELETTRODOMESTICI",
    "Spese Extra":          "SPESE_EXTRA",
    "Spese Mediche":        "SPESE_MEDICHE",
    "Consumabili casa":     "CONSUMABILI_CASA",
    "Cibo casa":            "CIBO_CASA",
    "Mobilio":              "MOBILIO",
    "Ristorante":           "RISTORANTE",
    "Internet Casa":        "INTERNET_CASA",
    "extra giornalieri":    "EXTRA_GIORNALIERI",
    "Abbonamento Treno":    "ABBONAMENTO_TRENO",
    "Abbonamenti":          "ABBONAMENTI",
    "Benzina":              "BENZINA",
    "Spesa condominio":     "CONDOMINIO",
    "Spesa super-condominio": "SUPERCONDOMINIO",
    "Abbigliamento":        "ABBIGLIAMENTO",
    "Parrucchiere":         "PARRUCCHIERE",
    "Regali":               "REGALI",
    "Telefonia Mobile":     "TELEFONIA_MOBILE",
    "Autostrada":           "AUTOSTRADA",
    "Gestione Macchina":    "GESTIONE_MACCHINA",
    "Acquisto Macchina":    "ACQUISTO_MACCHINA",
    "Bolletta Gas":         "BOLLETTA_GAS",
    "Bolletta Luce":        "BOLLETTA_LUCE",
    "Paglie":               "PAGLIE",
}

TIPOLOGIA_TO_LABEL = {
    "Palestra":             "Palestra",
    "Elettrodomestici":     "Elettrodomestici",
    "Spese Extra":          "Spese Extra",
    "Spese Mediche":        "Spese Mediche",
    "Consumabili casa":     "Consumabili Casa",
    "Cibo casa":            "Cibo Casa",
    "Mobilio":              "Mobilio",
    "Ristorante":           "Ristorante",
    "Internet Casa":        "Internet Casa",
    "extra giornalieri":    "Extra Giornalieri",
    "Abbonamento Treno":    "Abbonamento Treno",
    "Abbonamenti":          "Abbonamenti",
    "Benzina":              "Benzina",
    "Spesa condominio":     "Spesa Condominio",
    "Spesa super-condominio": "Spesa Super-Condominio",
    "Abbigliamento":        "Abbigliamento",
    "Parrucchiere":         "Parrucchiere",
    "Regali":               "Regali",
    "Telefonia Mobile":     "Telefonia Mobile",
    "Autostrada":           "Autostrada",
    "Gestione Macchina":    "Gestione Macchina",
    "Acquisto Macchina":    "Acquisto Macchina",
    "Bolletta Gas":         "Bolletta Gas",
    "Bolletta Luce":        "Bolletta Luce",
    "Paglie":               "Paglie",
}

# ---------------------------------------------------------------------------
# Mapping metodo di pagamento
# ---------------------------------------------------------------------------
PAYMENT_MAP = {
    "Carta Intesa": "CARTA",
    "Buoni pasto":  "ALTRO",
    "PayPal":       "ALTRO",
}

def map_payment(raw):
    if not raw:
        return "CARTA"
    return PAYMENT_MAP.get(raw, "ALTRO")

# ---------------------------------------------------------------------------
# Step 1: aggiorna catalogs.json
# ---------------------------------------------------------------------------
def update_catalogs():
    with open(CATS_PATH, encoding="utf-8") as f:
        cats = json.load(f)

    new_expense_cats = {}
    for tipo in TIPOLOGIA_TO_KEY:
        key   = TIPOLOGIA_TO_KEY[tipo]
        label = TIPOLOGIA_TO_LABEL[tipo]
        new_expense_cats[key] = label
    new_expense_cats["ADD_CATEGORY"] = "AGGIUNGI UNA CATEGORIA ALLA LISTA"

    cats["expense_categories"] = new_expense_cats
    with open(CATS_PATH, "w", encoding="utf-8") as f:
        json.dump(cats, f, indent=4, ensure_ascii=False)
    print(f"  catalogs.json aggiornato con {len(new_expense_cats)-1} categorie.")

# ---------------------------------------------------------------------------
# Step 2: leggi Excel
# ---------------------------------------------------------------------------
def load_excel_rows():
    wb = openpyxl.load_workbook(str(EXCEL_PATH), data_only=True)
    ws = wb["Spese"]
    rows = []
    for row in ws.iter_rows(min_row=2, max_col=12, values_only=True):
        if row[0] is not None:
            rows.append(row)
    return rows

# ---------------------------------------------------------------------------
# Step 3: identifica coppie (shared+settled)
# ---------------------------------------------------------------------------
def find_paired_indices(rows):
    """Restituisce set di indici di riga che fanno parte di una coppia
    Gianni+Sonja (stessa data, importo, tipologia)."""
    by_key = defaultdict(list)
    for i, r in enumerate(rows):
        date_str = str(r[7]).split()[0] if r[7] else None
        key = (date_str, r[1], r[2])
        by_key[key].append(i)

    pairs = {}   # key -> [idx_gianni, idx_sonja]
    for key, idxs in by_key.items():
        if len(idxs) < 2:
            continue
        payers = {rows[i][9]: i for i in idxs}
        if "Gianni" in payers and "Sonja" in payers:
            pairs[key] = (payers["Gianni"], payers["Sonja"])

    paired_indices = set()
    for (gi, si) in pairs.values():
        paired_indices.add(gi)
        paired_indices.add(si)
    return pairs, paired_indices

# ---------------------------------------------------------------------------
# Step 4: importa nel DB
# ---------------------------------------------------------------------------
def import_to_db(rows, pairs, paired_indices, user_map):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")

    n_personal  = 0
    n_split     = 0
    n_paired    = 0
    errors      = []

    # Coppie già processate (evita doppio inserimento)
    processed_pair_keys = set()

    def insert_expense(**kwargs):
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))
        cur = conn.execute(
            f"INSERT INTO expenses ({cols}) VALUES ({placeholders})",
            tuple(kwargs.values()),
        )
        return cur.lastrowid

    def insert_share(expense_id, user_id, pct, amount, is_settled, settled_at=None):
        conn.execute(
            "INSERT INTO expense_shares "
            "(expense_id, user_id, percentage, amount, is_settled, settled_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (expense_id, user_id, pct, amount, is_settled, settled_at),
        )

    # Mappa pair_key → riga Gianni per descrizione/pagamento
    pair_key_map = {}
    for key, (gi, si) in pairs.items():
        pair_key_map[key] = (gi, si)

    for i, r in enumerate(rows):
        # r: voce, costo, tipologia, split, rata, notifica, scadenza, data_pag, mese, chi, metodo, allegato
        desc    = r[0] or ""
        amount  = float(r[1]) if r[1] else 0.0
        tipo    = r[2]
        split   = r[3]
        date_dt = r[7]
        payer   = r[9]
        metodo  = r[10]

        if not date_dt:
            errors.append(f"Riga {i+2}: data mancante → saltata ({desc})")
            continue

        date_str = date_dt.strftime("%Y-%m-%d %H:%M:%S")
        cat_key  = TIPOLOGIA_TO_KEY.get(tipo, "SPESE_EXTRA")
        pay_meth = map_payment(metodo)
        user_id  = user_map.get(payer)
        if user_id is None:
            errors.append(f"Riga {i+2}: utente '{payer}' non trovato → saltata ({desc})")
            continue

        # --- Caso 1: riga di una coppia ---
        if i in paired_indices:
            date_str_key = str(date_dt).split()[0]
            pk = (date_str_key, amount, tipo)
            if pk in processed_pair_keys:
                continue  # già inserita come coppia
            processed_pair_keys.add(pk)

            gi, si = pair_key_map[pk]
            r_g = rows[gi]
            desc_merged = r_g[0] or r_g[0] or desc
            total = round(amount * 2, 2)
            per_person = round(amount, 2)

            exp_id = insert_expense(
                description=desc_merged,
                user_id=1,               # Gianni come registrante
                category=cat_key,
                merchant="",
                total_amount=total,
                date=date_str,
                payment_method=pay_meth,
                is_shared=1,
                advanced_by_user_id=1,   # Gianni come anticipatore formale
                is_settled=1,
                visibility="PUBBLICA",
                source="MANUALE",
                note="Importato da Excel - spesa condivisa già saldata",
            )
            # Quote: entrambi pagano la propria metà, entrambe saldate
            insert_share(exp_id, 1, 0.5, per_person, 1, date_str)
            insert_share(exp_id, 2, 0.5, per_person, 1, date_str)
            n_paired += 1

        # --- Caso 2: SPLIT singolo (uno ha pagato per entrambi) ---
        elif split == "SPLIT":
            other_user_id = 2 if user_id == 1 else 1
            exp_id = insert_expense(
                description=desc,
                user_id=user_id,
                category=cat_key,
                merchant="",
                total_amount=amount,
                date=date_str,
                payment_method=pay_meth,
                is_shared=1,
                advanced_by_user_id=user_id,
                is_settled=0,
                visibility="PUBBLICA",
                source="MANUALE",
                note="",
            )
            per_person = round(amount / 2, 2)
            insert_share(exp_id, user_id,       0.5, per_person, 1, date_str)  # anticipatore: quota sua = già "pagata"
            insert_share(exp_id, other_user_id, 0.5, per_person, 0, None)      # debitore: da saldare
            n_split += 1

        # --- Caso 3: PERSONALE ---
        else:
            insert_expense(
                description=desc,
                user_id=user_id,
                category=cat_key,
                merchant="",
                total_amount=amount,
                date=date_str,
                payment_method=pay_meth,
                is_shared=0,
                is_settled=0,
                visibility="PUBBLICA",
                source="MANUALE",
                note="",
            )
            n_personal += 1

    conn.commit()
    conn.close()
    return n_personal, n_split, n_paired, errors

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n=== Aggiornamento catalogs.json ===")
    update_catalogs()

    print("\n=== Lettura Excel ===")
    rows = load_excel_rows()
    print(f"  Righe dati: {len(rows)}")

    pairs, paired_indices = find_paired_indices(rows)
    print(f"  Coppie shared+settled trovate: {len(pairs)}")
    for key, (gi, si) in pairs.items():
        print(f"    {key[0]} | {key[1]}€ | {key[2]}")

    # Mappa nomi utenti → ID DB
    conn = sqlite3.connect(str(DB_PATH))
    users_db = conn.execute("SELECT id, first_name FROM users").fetchall()
    conn.close()
    user_map = {u[1]: u[0] for u in users_db}
    # Alias foglio → nome DB
    user_map["Sonja"] = user_map.get("Sonia", 2)
    print(f"  Utenti DB: {user_map}")

    print("\n=== Importazione spese ===")
    n_personal, n_split, n_paired, errors = import_to_db(rows, pairs, paired_indices, user_map)

    print(f"  PERSONALE inserite:        {n_personal}")
    print(f"  SPLIT (non saldate):       {n_split}")
    print(f"  Coppie shared+settled:     {n_paired}  (ognuna = 1 spesa + 2 quote)")
    total_exp = n_personal + n_split + n_paired
    print(f"  Totale spese inserite:     {total_exp}")

    if errors:
        print(f"\n  Attenzione - {len(errors)} righe saltate:")
        for e in errors:
            print(f"    {e}")
    else:
        print("\n  Nessun errore.")
