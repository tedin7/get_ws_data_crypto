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

## Lavoro aperto

Valutare una correzione che registri l'ultima ricezione valida sotto il lock,
usi il tempo monotono e non rinnovi quel riferimento al flush. Qualificare
anche messaggi invalidi, salti dell'orario civile e callback concorrenti.
Trasformare il primo caso in regressione prima/dopo sulla correzione scelta.
Servono inoltre regressioni shutdown, controlli completi del progetto e review
indipendente per una modifica del codice concorrente e persistente.
Nessuna integrazione, push o distribuzione eseguiti da questa prova.
