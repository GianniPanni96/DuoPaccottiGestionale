Applicazione Monolitica basata su model-view-controller paradigm con SQLITE3 per il db e PySide6 per la view.

La struttura dell'applicazione deve prendere interamente spunto da quella che trovi in:
C:\pythonProject\willowGestionale2.0, deve imitarla il più possibile sia a livello di architettura sia a livello di filosofia
implementativa; semplicemente qui il dominio di applicazione è leggermente diverso, quindi il database sarà differente (meno tabelle) ed esisteranno molti meno
tabs.

Lo scopo di questa applicazione è facilitare il tracciamento delle spese dei propri utenti, permettendo di analizzare la
tipologia delle spese inserite e visualizzare un insieme di dati aggregati.
Il selling point è una serie di automatismi creati ad hoc per facilitare il data entry, altrimenti tedioso per tutte le spese.
Ad esempio ci sarà una funzionalità di parsing di pdf dell'elenco delle spese estratti dall'app della banca.
Così come un parser dei pdf degli scontrini dell'esselunga.
Il parsing deve generare delle liste interattive delle spese da inserire con i dati di inserimento dedotti, ma mostrati
nell'interfaccia in preview, per essere visualizzati ed eventualmente corretti prima di salvare le spese nel database.

La view deve mostrare una barra di menu in alto in cui gestiremo i dati presenti in alcuni file di configurazione dell'app
ad esempio file json in cui salveremo la classificazione delle spese 1 in funzione della tipologia di spesa e altri json
che potrebbero servire all'app per configurare il suo comportamento/settare dei predefiniti utente.

Sotto la barra di menu deve essere presente una tabview in cui in ogni tab vengono gestiti diversi domini:
TAB UTENTI con le cards degli utenti e la possibilità di aggiungere un nuovo utente
TAB SPESE con una tabella che riflette le informazioni utili all'utente delle righe della tabella "spese" del database e la possibilità
di aggiungere una nuova spesa manualmente, la possibilità di estrarre le spese da uno scontrino o la possibilità di estrarre
le spese da un pdf della banca.
TAB ENTRATE -> come per le spese, righe della tabella "entrate" del db con possibilità di inserimento manuale di una entrata.
TAB ANALISI TBD più avanti.

La struttura del db e del resto dell'app deve permettere di eseguire le seguenti analisi (con conseguente inserimento nella view):
1. aggregazione delle spese totali annuali per utente, suddivise per tipologia di spesa, con scelta dell'anno da mostrare
2. aggregazione delle spese mensili per utente (dell'anno corrente), suddivise per tipologia di spesa, con scelta del mese da mostrare
3. aggregazione delle spese mensili medie (dell'anno corrente), suddivise per tipologia di spesa
4. calcolo dei rimborsi che un utente deve nei confronti di un altro utente in funzione di quali spese sono segnate come
"condivise" e "anticipate" da un certo utente.


La struttura del db e del resto dell'app deve permettere di eseguire le seguenti operazioni (con conseguente inserimento nella view):
1. segnare una spesa condivisa ed anticipata come "saldata" da un utente
2. segnare quali utenti sono contemplati in una spesa condivisa e in che percentuale, con un valore di default percentuale: suddivisione equa tra i partecipanti alla spesa.


- Logiche di login degli utenti all'avvio dell'app con inserimento password con scelta da parte del singolo utente di quali
dati mostrare globalmente agli altri utenti e quali mostrare solo a se stessi (quindi a login effettuato).
- Admin (superuser) diverso da altri utenti, no user con superpoteri



