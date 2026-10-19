# Feed fermo con ticker residuo: prova offline del 19 ottobre 2026

## Contratto

Risultato: riprodurre sul ciclo `BybitWebSocketClient.run` la mancata
rilevazione del silenzio quando resta un ticker nel buffer. Distinguere arrivo
di nuovi ticker, scrittura e recupero dopo un flush fallito.

Repository canonica: `tedin7/get_ws_data_crypto`, base
`9e0da7d25ef01a55565b1a4f0f441b0c3257a653`. Worktree separato:
`/root/wt/crypto-feed-fermo-20261019`, ramo `verifica/feed-fermo-20261019`.
Nessuna modifica a `main.py`, dipendenze o configurazione produttiva.
Socket e orologio simulati; file e lock reali in directory temporanee.
Nessuna connessione al mercato. Nessuna verifica sul servizio distribuito.

## Risultato

| Caso | Ricezioni | Esito |
| --- | --- | --- |
| Ticker residuo, poi silenzio | 1 | Nessun recupero entro 80 secondi simulati; una riga nel buffer. |
| Prezzo invariato, ticker ogni 5 secondi | 17 | Nessun recupero entro 80 secondi. Controllo positivo di attività. |
| Un ticker e solo flush a 5 secondi | 1 | Recupero a 70 secondi: il flush rinnova impropriamente il timer una volta. |
| Flush fallito con `fsync` in errore | 1 | `close` segnala dati non salvati; buffer e batch pendente conservati. Il retry senza guasto salva esattamente una riga. |

Il primo caso conferma il difetto ipotizzato nella Page. Il terzo separa
ricezione e scrittura: un salvataggio non costituisce un nuovo dato ricevuto.
La prova usa il ciclo reale, senza riscriverne le condizioni nel simulatore.
Il clock civile avanza in modo regolare: salti dell'orario civile non ancora
qualificati. Nessuna nuova politica di riconnessione scelta o implementata.

## Riproduzione e verifiche

Ambiente: Python 3.14.8, Linux. Il probe usa soltanto libreria standard e
`storage_protocol.py` della base; sostituisce trasporto, configurazione,
healthcheck e attesa asincrona. Non certifica la compatibilità del runtime
produttivo o di pybit. `EndProbe`, derivata da `BaseException`, arresta la
simulazione dopo la finestra osservata senza attivare il gestore delle normali
eccezioni del collector.

| Input | Comando nel worktree | Esito | Invalidazione |
| --- | --- | --- | --- |
| Base sopra e `tests/probe_feed_stall.py` | `PYTHONPATH=. python3 tests/probe_feed_stall.py` | Uscita 1 prevista: difetto rilevato. Tre scenari completati, controlli di conservazione e retry superati. | Modifiche a callback, ciclo, storage o fixture. |
| Base sopra | `PYTHONPATH=. python3 -m unittest discover -s tests -p test_storage_integrity.py` | Uscita 0. | Modifiche allo storage o ambiente. |
| Base sopra | `PYTHONPATH=. python3 -m unittest discover -s tests -p test_write_failures.py` | Uscita 0. | Modifiche a callback, retry, storage o ambiente. |

Il probe non fa parte della suite verde: è un diagnostico che restituisce 1
quando osserva il difetto. Le sue asserzioni verificano i controlli prima di
interpretare quell'uscita. Per vedere l'evidenza leggere il JSON su stdout;
stderr conserva l'errore di disco iniettato e l'avviso del caso con solo flush.

## Correzione candidata del 19 ottobre

Il seguito locale modifica `main.py`: il callback registra la ricezione valida
con `time.monotonic()` sotto `_buffer_lock`. Il ciclo confronta quel valore
con il tempo monotono corrente; né il buffer né il flush rinnovano la ricezione.
Prima della nuova connessione azzera lo stato della vecchia sottoscrizione.
Il periodo iniziale parte prima della sottoscrizione, che può chiamare subito
il callback. La soglia resta oltre 60 secondi, controllata ogni cinque secondi.
Il percorso di scrittura non cambia.

Nove regressioni esercitano il ciclo reale: ticker residuo e flush fallito,
prezzo invariato, solo flush, messaggi invalidi, nessun primo callback, primo
ticker ritardato, callback da un altro thread e salti dell'orario civile nelle
due direzioni. In assenza di ricezioni il recupero parte a 65 secondi; dopo
il primo ticker a 20 secondi parte a 85. Il retry dopo errore conserva una sola
riga. Queste prove non dimostrano assenza di ogni possibile interleaving.

| Input e comando | Ambiente | Esito | Invalidazione |
| --- | --- | --- | --- |
| Nove prove correnti applicate a una copia temporanea di `main.py` e `storage_protocol.py` della base `9e0da7d2`; `python -m unittest discover -s tests -p test_feed_freshness.py` | Python 3.13.5 | 9 test, 6 fallimenti: la suite rileva il difetto della base. Log locale `/tmp/crypto-freshness-final-baseline.log`. | Cambiamenti a fixture, requisiti o base. |
| Candidato; `WS_DIR_PATH=/tmp/crypto-feed-suite-data-20261019 build-a-turno /tmp/crypto-feed-venv-20261019/bin/python tests/run_all_tests.py` | Python 3.13.5, dipendenze esatte da `requirements.txt`, venv isolato; dati di prova fuori repository | Tutti gli 11 script verdi, incluse le 9 nuove regressioni, shutdown, storage e lock. Log locale `/tmp/crypto-feed-full-suite.log`. | Modifiche rilevanti a codice, test, dipendenze o ambiente. |

Il runner del progetto include ora le regressioni di freschezza. La prima
riproduzione sopra resta evidenza storica della base; il probe sul candidato
restituisce zero quando il recupero viene osservato. I log in `/tmp` sono
effimeri; comandi e risultati sono conservati qui per la riproduzione.

`pre-commit run` ha inizialmente rilevato whitespace preesistente e una
configurazione TOML non valida per gitleaks, presente dal commit `8761e5c`.
Corrette soltanto le virgolette della configurazione e accettate le rimozioni
di spazi finali degli hook. Il secondo controllo completo degli hook è verde
(`/tmp/crypto-feed-hooks-fixed.log`). La suite funzionale non viene ripetuta
per queste sole variazioni senza effetto sul runtime. La correzione del file
TOML non modifica regex o allowlist.

## Lavoro aperto

Correzione e controlli locali completati. Resta la review indipendente prima
dell'integrazione della modifica concorrente. Il servizio di revisione dei
passi ha risposto `monthly cap reached`; nessun nuovo incarico a pagamento
avviato. Nessuna integrazione, push o distribuzione eseguiti. Il runtime
produttivo, la versione installata e la stabilità live restano non verificati.
