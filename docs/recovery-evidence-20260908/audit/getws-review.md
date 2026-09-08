# Review finale get_ws_data_crypto — shutdown

Esito: patch completata e suite ufficiale verde, 6 script su 6.

## Correzione verificata

- `main.py`: il costruttore WebSocket passa `restart_on_error=False`. Il manager pybit installato può invocare `_reset()` e `_connect()` dopo `exit()` quando il riavvio interno è abilitato; il collector possiede già un ciclo esterno con backoff.
- Il ramo di riconnessione riusa `close()` sincrono: chiude il socket, attende il thread dei callback e salva il buffer prima del backoff. Non avvia una seconda chiusura concorrente se arriva SIGTERM durante un await di cleanup.
- Il percorso finale già presente cancella il task su SIGTERM e chiama `close()` tramite `asyncio.to_thread()`. Il buffer residuo dopo un errore di salvataggio provoca un errore esplicito.
- `tests/test_shutdown.py`, già presente nella patch da completare: cancellazione con ultimo callback in un thread reale; errore fsync con buffer preservato; errore pybit durante shutdown e cleanup di riconnessione, con vero `_WebSocketManager`, trasporto finto e `_connect` mock.
- `README.md`: documentato l'ordine di chiusura, attesa callback e salvataggio.

## Verifiche

Esecuzione unica della suite dopo questa correzione, nella copia isolata `/tmp/get-ws-efficiency-tests.ogtvpa`, con `/root/get_ws_data_crypto/.venv/bin/python -u tests/run_all_tests.py`, 2026-09-08 02:29:50–02:29:53 (timestamp del processo).

| Script | Risultato |
| --- | --- |
| test_import.py | OK |
| test_main.py | OK |
| test_functionality.py | OK |
| test_archiver.py | OK |
| test_healthcheck.py | OK |
| test_shutdown.py | OK |

Log: `/tmp/system-efficiency-20260908/getws-recovery-tests.log`.

Lock bloccante `/tmp/codex-recovery-20260908/heavy.lock` mantenuto per l'intera suite; runner sequenziale, timeout 60 secondi con kill dopo altri 5 secondi. Prima della suite: MemAvailable 12.915.604 kB, memory PSI some avg10 0.00. Limiti letti: chat 2 CPU/3 GiB, slice condivisa 6 CPU/8 GiB; nessuna modifica ai processi o ai limiti.

`git diff --check` verde; controllo whitespace anche del nuovo `tests/test_shutdown.py` verde. I file sincronizzati nella copia isolata corrispondono ai sorgenti verificati. Copiati soltanto i quattro file divergenti: `main.py`, `README.md`, `archiver.py`, `tests/test_shutdown.py`; l'archiver è la patch del coordinatore, non modificata durante questo intervento.

## Confini della verifica

Review del percorso constructor → polling → reconnect → close → callback → flush e del comportamento `_on_error`/`exit` nella pybit installata completata, senza problemi residui individuati nello scope. Le prove usano tick sintetici e directory temporanee; nessun Docker, rete, provider, `.env`, dato reale, avvio del collector, commit o push. La chiusura attende il termine del callback: callback o I/O bloccati restano dipendenti dai tempi del trasporto e del filesystem; non è stata simulata una sessione di rete reale.
