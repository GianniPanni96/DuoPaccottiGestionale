# DuoPaccottiGestionale — Proposta di Architettura

> Documento di **preview architetturale** (nessun codice ancora scritto).
> Obiettivo: replicare il più fedelmente possibile l'architettura e la
> filosofia di `willowGestionale2.0`, adattandola a un dominio più
> semplice (tracciamento spese/entrate di una coppia, con automatismi di
> data-entry via parsing di PDF).
>
> Le sezioni marcate con 🟡 **DECISIONE APERTA** richiedono una tua conferma
> prima di procedere all'implementazione (riepilogate in fondo).

---

## 1. Filosofia e principi

Riprendiamo *integralmente* i principi che reggono Willow:

- **Monolite MVC** con separazione netta dei layer.
- **SQLite3** accesso diretto via `sqlite3` stdlib (no ORM), con
  *connection-per-operation* gestita da un context manager (`_connect`)
  che fa `commit`/`rollback`/`close` — risolve i lock su Windows.
- **Enum delle colonne DB** (`DBExpensesColumns`, …): unica fonte di verità
  per i nomi colonna; le query si costruiscono dinamicamente filtrando i
  `**kwargs` sulle colonne valide dell'enum.
- **`row_to_map`**: ogni riga grezza (tupla) viene convertita in `dict`
  chiave→valore usando l'enum, così i layer superiori lavorano sempre con
  dizionari leggibili.
- **Layer a responsabilità singola**:
  - **Model** → SQL grezzo.
  - **QueryService** → letture di dominio (ritornano dict/list di dict).
  - **AnalyzerService** → aggregazioni e metriche (read-only, calcolate).
  - **Controller** → scritture, validazioni, regole di business.
  - **ConfigManager** → persistenza JSON dei file di configurazione.
  - **View (PySide6)** → UI; non contiene logica di dominio.
- **`AppContext`** = container di dependency-injection: istanzia *una sola
  volta* model, servizi, controller, config manager, event bus, e li
  cabla tra loro. È l'unico oggetto passato alle view.
- **`Event_bus`**: pub/sub per disaccoppiare le view (es. login cambiato,
  apertura dettaglio cross-tab).
- **PySide6** con il pattern `QAbstractTableModel` + `QSortFilterProxyModel`
  per le liste (rendering solo delle celle visibili → performante), e
  `QTBaseListView` come classe base che orchestra
  `fetch → build_rows → swap model → aggregati`.
- **Path runtime centralizzati** in `Utils/App_paths.py` (`RuntimePaths`
  dataclass): dove stanno DB, JSON di config, ecc., con logica
  dev/frozen (PyInstaller).

### Cosa cambia rispetto a Willow (semplificazioni)

| Willow | DuoPaccotti |
|---|---|
| ~11 tabelle (fatture, clienti, fornitori, produzioni, pagamenti, conti, salari, rimborsi, trasferimenti, spese, utenti, admin) | **5 tabelle** (utenti, spese, entrate, quote_condivisione, admin) |
| ~14 tab | **4 tab** (Utenti, Spese, Entrate, Analisi) |
| Logica fiscale forfettario/ordinario, IVA, IRPEF, INPS, chiusura esercizio, backup books, fatturazione elettronica | **rimosse** |
| Crittografia per-utente delle credenziali provider | 🟡 da decidere (vedi §6) |
| Niente parsing | **Parser PDF banca + scontrino Esselunga** (feature centrale, §7) |

---

## 2. Stack tecnologico

Versioni **verificate compatibili con il `venv` esistente su Python 3.14**
(dry-run `pip` con wheel native cp314/abi3 risolto correttamente):

```
Python 3.14.0     (venv esistente — confermato OK)
PySide6 6.11.1    UI            (+ shiboken6 6.11.1)
sqlite3 (stdlib)  DB
pdfplumber 0.11.9 parsing PDF testuali (banca / Esselunga)   ← nuova dipendenza
                  (porta con sé pdfminer.six, pypdfium2)
pycryptodome 3.23 hashing password (riuso da Willow)
python-dateutil   parsing date flessibile
matplotlib 3.10.9 grafici tab Analisi (+ numpy 2.4.6)
pyinstaller       build (riuso da Willow)
```

> ✅ **Compatibilità Python/PySide6 — RISOLTA.** Contrariamente al timore
> iniziale, PySide6 6.10+ pubblica wheel per Python 3.14: `pip index
> versions PySide6` su questo venv elenca 6.10.1 → 6.11.1 e il dry-run
> dell'intero set (PySide6, pdfplumber, matplotlib, pycryptodome, …) si
> risolve con sole wheel native. **Restiamo su Python 3.14.**

Per il parsing PDF propongo **`pdfplumber`** (estrazione testo + tabelle
con coordinate) anziché OpenCV/OCR: gli estratti conto e gli scontrini
Esselunga scaricati dall'app sono PDF *testuali* (non scansioni), quindi
non serve OCR. Se in futuro servisse OCR su scansioni, si aggiunge
`pytesseract` dietro la stessa interfaccia parser.

---

## 3. Struttura cartelle e file

```
DuoPaccottiGestionale/
├── MainQT.py                     # entry-point UI: auth flow + main window
├── Main_bootstrap.py             # build config + AppContext (no UI)
├── App_context.py                # container DI
├── Model.py                      # DatabaseModel (SQL grezzo) + bootstrap schema
├── Schema.py                     # DDL CREATE TABLE + create_schema(db_path)
├── Gestionale_Enums.py           # enum colonne DB + enum di dominio
├── Event_bus.py                  # pub/sub
├── requirements.txt
│
├── ConfigManagers/
│   ├── base_json_manager.py      # load/save/merge-with-defaults
│   ├── type_utils.py             # merge_with_defaults
│   ├── defaults.py               # dizionari di default di ogni file json
│   ├── config_manager.py         # aggregatore
│   ├── catalogs_manager.py       # categorie spese + categorie entrate
│   ├── app_settings_manager.py   # default utente, nome collettivo
│   └── gui_preferences_manager.py# tab di avvio, finestre temporali liste
│
├── QueryServices/
│   ├── Users_query_service.py
│   ├── Expenses_query_service.py
│   ├── Incomes_query_service.py
│   ├── Expense_shares_query_service.py
│   └── Admin_query_service.py
│
├── AnalyzerServices/
│   ├── Expense_analyzer_service.py   # annuale/mensile/media per utente×categoria
│   ├── Income_analyzer_service.py
│   └── Refund_analyzer_service.py    # chi-deve-a-chi
│
├── Controllerss/                     # (nome mantenuto come Willow; v. §12)
│   ├── User_controller.py
│   ├── Expense_controller.py
│   ├── Income_controller.py
│   ├── Refund_controller.py          # marca quote come "saldate"
│   └── Admin_controller.py
│
├── ParserServices/
│   ├── base_pdf_parser.py            # interfaccia comune
│   ├── parsed_movement.py            # dataclass riga candidata (preview)
│   ├── bank_statement_parser.py      # estratto conto banca → spese candidate
│   └── esselunga_receipt_parser.py   # scontrino Esselunga → spese candidate
│
├── OtherServices/
│   ├── User_auth_service.py          # verifica password + sessione
│   ├── Session_context.py            # stato sessione: utente loggato, is_admin
│   ├── Visibility_service.py         # filtro privacy "globale vs privato"
│   ├── User_crypto_service.py        # 🟡 solo se si sceglie cifratura (§6)
│   └── Admin_audit_log.py            # (opzionale) log accessi admin
│
├── Utils/
│   ├── App_paths.py                  # RuntimePaths + risoluzione percorsi
│   ├── Controller_utils.py           # row_to_map, hash_password, parse_date…
│   ├── Validation_utils.py           # validate_amount, ecc.
│   └── View_utils.py                 # EventBusKeys + helper UI
│
└── QTViews/
    ├── QT_main_view.py               # QMenuBar + QTabWidget + icona utente
    ├── QT_palette_Manager.py         # tema chiaro/scuro
    ├── QT_analysis_view.py           # tab Analisi (grafici + tabelle + refund)
    ├── LoginViews/
    │   ├── QT_login_dialog.py        # login utente + scelta visibilità
    │   ├── QT_admin_login_dialog.py
    │   ├── QT_onboarding_dialog.py   # primo avvio: crea primo utente
    │   ├── QT_admin_create_dialog.py # primo avvio: crea admin
    │   └── QT_recovery_*.py          # reset via recovery code (opzionale)
    ├── ListViews/
    │   ├── QT_base_list_view.py
    │   ├── QT_expenses_view.py  +  QT_expenses_table_model.py
    │   └── QT_incomes_view.py   +  QT_incomes_table_model.py
    ├── Creators/
    │   ├── QT_expense_create_view.py # inserimento spesa manuale
    │   ├── QT_income_create_view.py
    │   └── QT_user_create_view.py
    ├── Details/
    │   ├── QT_expense_detail_view.py # dettaglio + editor quote condivise
    │   ├── QT_income_detail_view.py
    │   └── QT_user_detail_view.py
    ├── ParserViews/
    │   └── QT_parsed_movements_preview_dialog.py  # tabella editabile pre-salvataggio
    ├── CustomWidgets/
    │   ├── QT_user_card.py
    │   ├── QT_filterable_combo_box.py
    │   ├── QT_catalog_filterable_combo_box.py
    │   └── QT_expense_shares_editor.py            # widget partecipanti + %
    └── MenuWindows/
        ├── QT_catalogs_dialog.py     # editor categorie spese/entrate
        ├── QT_app_settings_dialog.py # default utente, nome collettivo
        └── QT_privacy_settings_dialog.py
```

---

## 4. Schema del Database

5 tabelle. Mantengo le convenzioni di Willow: PK `INTEGER PRIMARY KEY
AUTOINCREMENT`, timestamp `created_at`/`updated_at` con
`DEFAULT CURRENT_TIMESTAMP`, FK esplicite. Lo schema vive in `Schema.py`
e viene creato automaticamente al primo avvio se il file DB non esiste
(miglioria rispetto a Willow, che usava script manuali separati).

### 4.1 `users`

| colonna | tipo | note |
|---|---|---|
| `id` | INTEGER PK | |
| `first_name` | TEXT NOT NULL | |
| `last_name` | TEXT NOT NULL | |
| `email` | TEXT | opzionale |
| `telefono` | TEXT | opzionale |
| `photo_path` | TEXT | per la card utente |
| `password_login` | TEXT | hash PBKDF2 (salt+hash hex), come Willow |
| `recovery_hash` | TEXT | hash del recovery code (reset password) |
| `default_visibility` | TEXT | `PUBBLICA`/`PRIVATA` — default per nuove spese |
| `status` | TEXT | `attivo`/`disattivo` |
| `created_at`, `updated_at` | TIMESTAMP | |

> Privacy con Opzione A (§6): **niente** colonne `crypto_*`.

### 4.2 `expenses` (spese)

| colonna | tipo | note |
|---|---|---|
| `id` | INTEGER PK | |
| `description` | TEXT NOT NULL | nome/descrizione spesa |
| `user_id` | INTEGER NOT NULL | proprietario (chi ha registrato la spesa) → `users.id` |
| `category` | TEXT NOT NULL | chiave del catalogo `expense_categories` (JSON) |
| `merchant` | TEXT | esercente/negozio (es. "Esselunga") — free text |
| `total_amount` | REAL NOT NULL | importo lordo |
| `net_amount` | REAL | opzionale (utile per scontrini con IVA) |
| `iva_amount` | REAL | opzionale |
| `date` | TIMESTAMP NOT NULL | data spesa |
| `payment_method` | TEXT | enum `CONTANTI`/`CARTA`/`BONIFICO`/`ALTRO` |
| `is_shared` | INTEGER (bool) DEFAULT 0 | spesa condivisa? |
| `advanced_by_user_id` | INTEGER | chi ha anticipato (per spese condivise) → `users.id` |
| `is_settled` | INTEGER (bool) DEFAULT 0 | spesa condivisa interamente saldata? (derivabile dalle quote, cache) |
| `visibility` | TEXT NOT NULL | `PUBBLICA` (visibile agli altri) / `PRIVATA` |
| `source` | TEXT NOT NULL | `MANUALE`/`SCONTRINO`/`ESTRATTO_BANCA` |
| `note` | TEXT | |
| `created_at`, `updated_at` | TIMESTAMP | |

FK: `user_id`, `advanced_by_user_id` → `users(id)`.

### 4.3 `expense_shares` (quote di condivisione)

Tabella ponte: per ogni spesa condivisa, righe partecipante↔percentuale.
Risolve sia "**quali utenti** sono contemplati e **in che percentuale**"
sia il "**saldata** per singolo partecipante".

| colonna | tipo | note |
|---|---|---|
| `id` | INTEGER PK | |
| `expense_id` | INTEGER NOT NULL | → `expenses.id` (ON DELETE CASCADE) |
| `user_id` | INTEGER NOT NULL | partecipante → `users.id` |
| `percentage` | REAL NOT NULL | quota (somma quote di una spesa = 1.0) |
| `amount` | REAL NOT NULL | = `percentage * total_amount` (denormalizzato, ricalcolato a ogni modifica) |
| `is_settled` | INTEGER (bool) DEFAULT 0 | questa quota è stata restituita all'anticipatore? |
| `settled_at` | TIMESTAMP | |
| `created_at`, `updated_at` | TIMESTAMP | |

> Default richiesto da SCOPO: alla marcatura "condivisa", se non
> diversamente specificato, le quote sono **eque** tra i partecipanti
> (`percentage = 1/N`). Il `Refund_controller` genera le righe di default
> e l'utente può poi modificarle dall'editor quote (§8).

### 4.4 `incomes` (entrate)

Mirror semplificato delle spese (le entrate **non** sono condivise/anticipate
salvo tua diversa indicazione).

| colonna | tipo | note |
|---|---|---|
| `id` | INTEGER PK | |
| `description` | TEXT NOT NULL | |
| `user_id` | INTEGER NOT NULL | → `users.id` |
| `category` | TEXT NOT NULL | catalogo `income_categories` |
| `amount` | REAL NOT NULL | |
| `date` | TIMESTAMP NOT NULL | |
| `visibility` | TEXT NOT NULL | `PUBBLICA`/`PRIVATA` |
| `source` | TEXT NOT NULL | `MANUALE`/`ESTRATTO_BANCA` |
| `note` | TEXT | |
| `created_at`, `updated_at` | TIMESTAMP | |

### 4.5 `admin`

Identica a Willow: singolo amministratore di sistema, vincolo "uno solo"
applicato a livello applicativo nell'`AdminController`.

| colonna | tipo |
|---|---|
| `id` | INTEGER PK |
| `name` | TEXT NOT NULL DEFAULT 'ADMIN' |
| `password_login` | TEXT NOT NULL |
| `recovery_hash` | TEXT NOT NULL |
| `created_at`, `updated_at` | TIMESTAMP |

---

## 5. Layer applicativi (responsabilità + esempi di firma)

### Model (`Model.py`)
`DatabaseModel(db_path)`: stessa identica forma di Willow. Metodi:
`add_expense(**kwargs)`, `fetch_expenses()`, `fetch_expense_by_id(id)`,
`update_expense(id, **kwargs)`, `remove_expense(id)`, idem per
`incomes`, `users`, `admin`, `expense_shares`. Filtra i kwargs sulle
colonne valide dell'enum. All'avvio: se il DB non esiste,
`Schema.create_schema(db_path)`.

### QueryServices (letture)
Ritornano `dict`/`list[dict]` via `row_to_map`. Es.
`ExpensesQueryService`:
```
retrieve_expense_map_by_id(id)
retrieve_expenses_map_list(year=None, viewer_user_id=None)   # con filtro privacy
retrieve_expenses_map_list_by_user(user_id, year=None)
retrieve_shared_unsettled_expenses()
```
Il parametro `viewer_user_id` consente di delegare il filtro privacy
(vedi `Visibility_service`).

### AnalyzerServices (aggregazioni)
- **`ExpenseAnalyzerService`** — copre le analisi 1/2/3 del SCOPO:
  - `annual_by_user_and_category(year)` → `{user_id: {categoria: totale}}`
  - `monthly_by_user_and_category(year, month)` → idem per il mese
  - `monthly_average_by_category(year)` → media mensile per categoria
  - `build_aggregate_data(...)` per le card in cima alla lista
- **`RefundAnalyzerService`** — analisi 4: calcola la matrice
  *chi-deve-a-chi* dalle `expense_shares` non saldate delle spese
  `is_shared` con un `advanced_by_user_id`:
  - `compute_balances()` → `{(debitore, creditore): importo}`
  - logica: per ogni spesa anticipata da A, ogni partecipante P≠A con
    quota non saldata deve ad A `share.amount`; si nettano i reciproci
    A↔B.
- **`IncomeAnalyzerService`** — aggregazioni entrate (simmetrico).

### Controllers (scritture/business)
- **`ExpenseController.save_expense(data)`**: valida, calcola
  net/iva da aliquota se fornita, risolve `category`/`merchant`,
  imposta `source`, `visibility` (default dall'utente), e — se
  `is_shared` — crea le righe `expense_shares` (default equo) tramite il
  `Refund_controller`. `save_parsed_expenses(list_of_data)` per il
  salvataggio batch dal preview del parser.
- **`IncomeController`**: analogo, più semplice.
- **`Refund_controller`**:
  - `set_shares(expense_id, {user_id: percentage})` (validazione somma=1)
  - `generate_equal_shares(expense_id, participant_ids)`
  - `mark_share_settled(share_id)` / `mark_share_unsettled(share_id)` →
    operazione "segna come saldata"
- **`UserController`**: CRUD utenti, set password (hash), recovery,
  `set_default_visibility`.
- **`AdminController`**: crea/gestisce l'unico admin, reset password
  utenti.

### ParserServices (vedi §7)

### ConfigManagers (vedi §10)

### OtherServices
- **`Session_context`**: oggetto stateful con `current_user_id`,
  `is_admin`, esposto da `AppContext`. È la fonte di verità per "chi sta
  guardando" → usato dal `Visibility_service`.
- **`Visibility_service`**: `filter_expenses(expenses, viewer_user_id)`,
  `filter_incomes(...)`. Regola: mostra le righe dell'utente stesso
  (tutte) + le righe altrui con `visibility = PUBBLICA` + le spese
  condivise di cui il viewer è partecipante (sempre visibili a chi
  partecipa). 🟡 Vedi §6 per la scelta del meccanismo di privacy.
- **`User_auth_service`**: verifica password (`ControllerUtils.verify_password`),
  set della sessione, logout. Modellato su Willow ma senza la parte di
  crypto provider.

---

## 6. Autenticazione & Privacy (DECISO)

> **Decisioni prese:** privacy con **Opzione A** (filtro applicativo);
> admin **puramente amministrativo** (nessun accesso ai dati finanziari).
> Le colonne `crypto_*` su `users` e `User_crypto_service` **non servono e
> si rimuovono**.

### Flusso di login (modellato su Willow `MainQT.py`)
1. Se la tabella `admin` è vuota → `QTAdminCreateDialog` (crea il singolo admin).
2. Se non esistono utenti → `QTOnboardingDialog` (crea il primo utente con password).
3. Altrimenti → `QTLoginDialog` obbligatoria (con opzione "Login come admin").
4. A login effettuato si popola `Session_context` e si pubblica
   `LOGIN_STATUS_CHANGED` sull'event bus; le tab si ricaricano filtrate.

L'admin è un **amministratore di sistema** distinto: gestisce utenti e
reset password; **nessun utente ha superpoteri** (rispetta il vincolo SCOPO).

### Scelta "quali dati mostrare globalmente / solo a sé"
Il SCOPO chiede che ogni utente scelga cosa è visibile agli altri. Due
implementazioni possibili — **da decidere**:

**✅ Opzione A — Filtro di visibilità a livello applicativo (SCELTA)**
- Ogni spesa/entrata ha `visibility` (`PUBBLICA`/`PRIVATA`); default
  per-utente in `users.default_visibility`, override per singola riga.
- Il `Visibility_service` filtra i risultati in base a chi è loggato.
- Le spese condivise sono sempre visibili ai partecipanti.
- **Pro**: semplice, permette aggregazioni e refund cross-utente, refresh
  immediato al cambio utente.
- **Contro**: privacy *logica*, non crittografica — chi apre il file
  `.db` con un editor SQLite vede tutto. Adeguata se il PC/file è
  condiviso in fiducia (tipico scenario di coppia).

**Opzione B — Cifratura at-rest per-utente (stile Willow)**
- I campi sensibili (importo, descrizione) cifrati con chiave derivata
  dalla password dell'utente (PBKDF2 → AES).
- **Pro**: privacy reale anche a DB aperto.
- **Contro**: complessità alta; le spese **condivise** non sono cifrabili
  con la chiave di un solo utente (servono ai refund e all'altro
  partecipante) → servirebbe una chiave condivisa/ibrida. Rischio di
  inconsistenze. Probabilmente sovradimensionata per il caso d'uso.

➡️ **Scelta confermata: Opzione A.** `User_crypto_service` e le colonne
`crypto_*` non vengono creati.

**Admin = puramente amministrativo** (deciso): gestisce utenti e reset
password; **non** ha accesso in lettura a spese/entrate degli utenti. Il
`Visibility_service` non concede all'admin alcun bypass del filtro
privacy; le tab finanziarie (Spese/Entrate/Analisi) non mostrano dati
quando si è loggati come admin (o sono disabilitate), mentre la gestione
utenti è accessibile solo in quel ruolo.

---

## 7. Parsing PDF (feature distintiva)

### Architettura
```
base_pdf_parser.BasePdfParser           # interfaccia: parse(path) -> list[ParsedMovement]
parsed_movement.ParsedMovement          # dataclass: date, amount, description,
                                        #   suggested_category, merchant, raw_text, kind
bank_statement_parser.BankStatementParser
esselunga_receipt_parser.EsselungaReceiptParser
```
- I parser usano **`pdfplumber`** per estrarre testo/tabelle e
  applicano regex/euristiche specifiche del formato.
- **`suggested_category`**: dedotta con un mapping euristico
  (parole chiave → categoria) configurabile via JSON
  (`category_hints.json`) così l'utente può migliorare le deduzioni nel
  tempo senza toccare il codice.
- Ogni parser ritorna una lista di `ParsedMovement` **non ancora salvati**.

### Flusso UI (preview interattiva)
1. Dalla tab Spese: bottone "Importa da estratto conto" / "Importa da
   scontrino Esselunga" → file picker.
2. Il parser produce `list[ParsedMovement]`.
3. Si apre **`QT_parsed_movements_preview_dialog`**: una `QTableView`
   editabile con una riga per movimento — colonne: ✔ includi, data,
   descrizione, importo, categoria (combo da catalogo), esercente,
   condivisa?, visibilità. I valori dedotti sono pre-compilati ed
   **editabili**.
4. L'utente corregge/deseleziona righe e preme "Salva selezionate" →
   `ExpenseController.save_parsed_expenses(rows)` inserisce in batch.

### Decisioni sul parsing
- **Scontrino Esselunga** (deciso): **una spesa unica per scontrino**
  (importo = totale, categoria suggerita "Spesa alimentare", esercente
  "Esselunga", data dallo scontrino). Niente itemizzazione per articolo.
- 🟡 **Quale/i banca/banche** per l'estratto conto? Il formato PDF varia
  per istituto → serve un parser per formato. Mi serve **un PDF di
  esempio (anche anonimizzato/con dati finti)** per banca ed Esselunga
  per tarare regex/euristiche. Strutturo `BasePdfParser` così che
  aggiungere un nuovo formato sia un parser in più, isolato.

---

## 8. View layer (PySide6)

- **`QT_main_view.QTMainWindow`**: `QMenuBar` in alto (menu di gestione
  dei file di config) + `QTabWidget` centrale + icona/menu utente in alto
  a destra (login/logout/cambia utente/login admin), identico nello
  spirito a Willow.
  - **Menu**: "Categorie" (apre `QT_catalogs_dialog`), "Impostazioni"
    (`QT_app_settings_dialog`: nome collettivo "DuoPaccotti", default
    utente, hint categorie), "Privacy" (`QT_privacy_settings_dialog`),
    "ADMIN" (gestione utenti, visibile solo da admin).
  - **Tab**: `Utenti`, `Spese`, `Entrate`, `Analisi`.
- **Tab Utenti**: card utenti (`QT_user_card`) in un flow-layout +
  bottone "Aggiungi utente".
- **Tab Spese / Entrate**: `QTBaseListView` sottoclassata
  (`QAbstractTableModel` + proxy), con:
  - barra card aggregate in alto (#spese, totale),
  - filtro temporale (finestra / anno),
  - search box,
  - bottoni: "Aggiungi manuale", "Importa da estratto conto", "Importa da
    scontrino Esselunga".
  - doppio click → dettaglio.
- **Dettaglio spesa** (`QT_expense_detail_view`): include l'**editor
  quote condivise** (`QT_expense_shares_editor`): toggle "condivisa",
  selezione partecipanti, percentuali (default equo), indicazione
  anticipatore, e per ogni partecipante il pulsante "segna come saldata".
- **Tab Analisi** (`QT_analysis_view`): le 4 analisi del SCOPO con
  `matplotlib` + tabelle:
  1. spese annuali per utente×categoria (selettore anno),
  2. spese mensili per utente×categoria (selettore mese, anno corrente),
  3. media mensile per categoria,
  4. riepilogo refund "chi-deve-a-chi" (da `RefundAnalyzerService`).
- **`QT_palette_Manager`**: tema chiaro/scuro riusato da Willow.

---

## 9. File di configurazione (JSON)

Gestiti dai `ConfigManager` con `BaseJsonConfigManager`
(load/save/`merge_with_defaults`), salvati nella `storage_root`.

- **`catalogs.json`**
  ```json
  {
    "expense_categories": { "ALIMENTARI": "Spesa alimentare", "CASA": "Casa e bollette", "...": "...", "ADD_CATEGORY": "AGGIUNGI UNA CATEGORIA" },
    "income_categories":  { "STIPENDIO": "Stipendio", "RIMBORSO": "Rimborso", "ADD_CATEGORY": "AGGIUNGI UNA CATEGORIA" }
  }
  ```
- **`app_settings.json`**: `collective_name` ("DuoPaccotti"), default
  IVA/metodo pagamento, ecc.
- **`category_hints.json`**: mapping parole-chiave → categoria per le
  deduzioni del parser.
- **`gui_preferences.json`**: tab di avvio, indici finestre temporali
  delle liste (come Willow).

---

## 10. Flusso di avvio (`Main_bootstrap` + `MainQT`)

```
get_runtime_paths()                  # risolve percorsi (DB, json, …)
Schema.create_schema(db) se assente  # auto-init DB
ConfigManager().load_config()        # carica/crea json di default
AppContext(...)                      # istanzia model+servizi+controller+bus
── MainQT.main() ──
ensure_admin_exists()                # crea admin se tabella vuota
force_authentication()               # onboarding / login utente / login admin
QTMainWindow(app_context)            # mostra UI, pubblica LOGIN_STATUS_CHANGED
qt_app.exec()
```

---

## 11. `AppContext` (cablaggio DI) — bozza

```python
self.db_model        = DatabaseModel(db_path)
self.session_context = SessionContext()

# Query services
self.users_query_service          = UsersQueryService(self.db_model)
self.expenses_query_service       = ExpensesQueryService(self.db_model, self.visibility_service)
self.incomes_query_service        = IncomesQueryService(self.db_model, self.visibility_service)
self.expense_shares_query_service = ExpenseSharesQueryService(self.db_model)
self.admin_query_service          = AdminQueryService(self.db_model)

# Other services
self.visibility_service = VisibilityService(self.session_context)
self.user_auth_service  = UserAuthService(self.users_query_service, self.db_model, self.admin_query_service, self.session_context)

# Analyzer services
self.expense_analyzer_service = ExpenseAnalyzerService(self.expenses_query_service)
self.income_analyzer_service  = IncomeAnalyzerService(self.incomes_query_service)
self.refund_analyzer_service  = RefundAnalyzerService(self.expenses_query_service, self.expense_shares_query_service, self.users_query_service)

# Controllers
self.refund_controller  = RefundController(self.db_model, self.expense_shares_query_service)
self.expense_controller = ExpenseController(self.db_model, self.users_query_service, self.refund_controller, catalogs)
self.income_controller  = IncomeController(self.db_model, catalogs)
self.user_controller    = UserController(self.db_model, self.users_query_service)
self.admin_controller   = AdminController(self.db_model, self.admin_query_service)

# Parsers
self.bank_parser     = BankStatementParser(category_hints)
self.esselunga_parser = EsselungaReceiptParser(category_hints)

# Config + bus
self.config_manager          = config_manager
self.gui_preferences_manager = GuiPreferencesManager()
self.event_bus               = EventBus()
```

---

## 12. Note implementative minori

- **Nome cartella controller**: Willow usa `Controllerss` (doppia *s*,
  refuso storico). Propongo di correggere in **`Controllers`** per il
  nuovo progetto; dimmi se preferisci mantenere il nome identico per
  copiare codice 1:1.
- **Lingua**: codice/commenti in italiano come Willow.
- **`Schema.py`** auto-inizializzante invece degli script manuali
  `Create_table_*.py`: più adatto a un progetto greenfield.

---

## 13. Riepilogo decisioni

### ✅ Chiuse
1. **Versione Python**: restiamo su **Python 3.14** — compatibilità
   PySide6 6.11.1 verificata (wheel cp314).
2. **Meccanismo privacy**: **Opzione A** (filtro applicativo).
3. **Admin**: **puramente amministrativo** (nessun accesso ai dati
   finanziari).
4. **Scontrino Esselunga**: **una spesa per scontrino** (totale).

### 🟡 Ancora da confermare prima di implementare
5. **Banca/banche** dell'estratto conto da supportare + mi serve **un PDF
   di esempio (anche con dati finti)** per banca ed Esselunga per tarare i
   parser. *(necessario per la feature parsing, non per lo scheletro)*
6. **Entrate condivise**: confermi che le entrate NON sono
   condivise/anticipate (solo le spese)? *(assunto: SÌ, solo spese)*
7. **Conti/metodi di pagamento**: basta il campo `payment_method` sulla
   spesa, niente tabella `accounts`? *(assunto: SÌ)*
8. **Nome cartella controller**: `Controllers` (pulito) o `Controllerss`
   (identico a Willow)? *(assunto: `Controllers`)*

> I punti 6-8 hanno già un default assunto: se non dici nulla procedo così.
> Il punto 5 serve solo quando arriveremo a implementare i parser; lo
> scheletro dell'app e l'inserimento manuale si possono fare prima.
```