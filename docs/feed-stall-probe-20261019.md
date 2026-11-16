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

## Stato al commit 6b3fc2d, prima del seguito sotto

Correzione e controlli locali completati. Resta la review indipendente prima
dell'integrazione della modifica concorrente. Il servizio di revisione dei
passi ha risposto `monthly cap reached`; nessun nuovo incarico a pagamento
avviato. Nessuna integrazione, push o distribuzione eseguiti. Il runtime
produttivo, la versione installata e la stabilità live restano non verificati.

## Seguito: Argon e confronto con Proxmox

Consultato Argon nella [conversazione Gemini autorizzata dall'operatore](https://gemini.google.com/app/1efb6fd6bf713a65).
La consultazione ha ricevuto una descrizione tecnica del codice pubblico, senza
credenziali o dati di mercato. Non equivale a una review eseguita sul repository.

Due rilievi sono stati riprodotti e corretti sul candidato `6b3fc2d`:

- **Setup lento:** un costruttore da 90 secondi consumava la tolleranza iniziale;
  il recupero partiva a 95 invece di 155 secondi. La tolleranza per una
  sottoscrizione senza ticker parte ora dopo `ticker_stream`. Il reset della
  vecchia ricezione resta prima del costruttore, così un callback immediato
  non viene cancellato. Verificata anche sottoscrizione lenta, con e senza
  callback immediato.
- **Contesa con storage:** il watchdog attendeva il buffer lock occupato da un
  thread. La fixture usa eventi e un rilascio di emergenza a due secondi:
  prima quel rilascio era necessario, dopo il watchdog prosegue senza usarlo.
  Un lock dedicato `_receipt_lock` protegge soltanto il timestamp; nessuna
  scrittura su disco avviene sotto quel lock. Il callback registra una ricezione
  valida prima di attendere il buffer lock.

Argon ha anche ipotizzato che un flush lungo debba rinnovare la freschezza:
questa indicazione non viene applicata, perché contraddice il requisito che
misura le ricezioni. Il blocco del thread pybit durante il flush e l'attesa
sincrona in `close` restano limiti preesistenti, non garanzie risolte qui.
La race su un possibile reset futuro dopo il callback era ipotetica; il reset
attuale non è collocato dopo la sottoscrizione.

La suite di freschezza contiene ora 13 casi. Il test del costruttore lento e
quello di contesa fallivano prima delle rispettive correzioni; la successiva
prova della sottoscrizione lenta ha rilevato un ulteriore avvio prematuro del
timer, poi corretto. Tutti gli 11 script del progetto sono nuovamente verdi
in Python 3.13.5: `/tmp/crypto-feed-full-suite-final-review.log`.

### Sorgente effettiva su Proxmox

Lettura via `ssh proxmox`, senza modificare il servizio:

- Container `get_ws_data_crypto-app-1`, immagine `crypto-collector:9e0da7d`,
  avviato il 7 ottobre 2026, stato `running`, health `healthy`, Python 3.13.16.
- Codice montato da `/root/get_ws_data_crypto/releases/crypto-20261006/source`;
  dati separati in `/root/get_ws_data_crypto/ws_data`.
- SHA-256 del `main.py` installato:
  `e5d61c2867b31bb880244b74c197dffff6f5ba9e6d9a5ade7594d6aabadb8167`.
  SHA-256 dello storage installato:
  `38a65fb5442290144179557756cb0c35862a97e75829c91e5da4373c0a799ba2`.
  Entrambi coincidono con gli input della base locale `9e0da7d2`.
- Il checkout principale remoto è invece a `4e859160`, con modifiche e file
  non tracciati preesistenti. Non è la prova del codice montato e resta intatto.

L'identità della sorgente installata è quindi verificata per i due file
interessati. Questo non prova che il difetto si sia verificato su dati reali.
Il candidato resta separato dalla produzione; integrazione e rilascio aperti.

### Prova nel runtime Proxmox

Candidato copiato in `/tmp/crypto-feed-candidate-20261019` su Proxmox.
Eseguito un container separato con l'immagine già installata, senza rete,
filesystem in sola lettura, codice montato in sola lettura e `/tmp` volatile.
Nessun dato produttivo montato. Comando:

```sh
docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev \
  -v /tmp/crypto-feed-candidate-20261019:/app:ro -w /app \
  -e WS_DIR_PATH=/tmp/ws -e PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint python crypto-collector:9e0da7d tests/run_all_tests.py
```

Uscita 0: tutti gli 11 script verdi, incluse le 13 regressioni di freschezza.
Log locale `/tmp/crypto-proxmox-candidate-suite.log`. La prova qualifica il
candidato nell'immagine effettiva; non costituisce un rilascio e non prova
recupero in condizioni di rete reali. Le prove restano valide solo a codice,
fixture, dipendenze e immagine invariati.
