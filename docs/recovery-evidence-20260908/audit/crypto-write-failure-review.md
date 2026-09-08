# Collector crypto: errori di scrittura e frequenza dei retry

## Ambito e decisione

Review di `BybitWebSocketClient.handle_ticker()` → `save_price_data()` e dei due chiamanti di chiusura in `/root/get_ws_data_crypto/main.py`; prove esclusivamente sintetiche in directory temporanee. La precedente correzione shutdown/reconnect e le patch preesistenti vengono conservate. Nessun dato reale, `.env`, rete, Docker, servizio persistente, commit o push.

La correzione applicata riguarda soltanto il backoff: dopo un errore di salvataggio il callback aspetta `FLUSH_INTERVAL` usando `time.monotonic()`. I tick continuano a entrare nel buffer. La chiamata diretta da `close()` ignora la pausa e continua a segnalare con `RuntimeError` eventuali righe rimaste. Il percorso ordinario di scrittura, il formato JSONL e il controllo di durabilità restano invariati. Il nuovo test controlla la soglia esatta, il recupero, l'assenza di ritardo dopo un successo e il tentativo forzato in chiusura.

## Causa e semantica degli errori

- `json.dump()` scrive più frammenti in un `TextIOWrapper`. Un errore può lasciare una o più righe complete e parte della successiva nel file. Il `with` chiama anche `close()`, che può tentare un ulteriore flush dei dati ancora nel buffer del writer e può fallire a sua volta.
- `flush()` trasferisce i dati dal buffer Python al sistema operativo: non fornisce atomicità della transazione e non garantisce persistenza fisica. Un errore può lasciare un prefisso già scritto.
- `fsync()` può fallire dopo che tutte le righe sono state accettate dal filesystem. Da un errore non segue che il file sia rimasto invariato; anche il caso di successo seguito da errore di close conserva oggi l'intero buffer.
- Nel codice attuale il retry riapre sempre in append e riscrive tutto il buffer. Un prefisso già appeso viene duplicato; una riga incompleta può essere concatenata al nuovo JSON e diventare illeggibile. L'errore può dunque essere seguito da un successivo salvataggio apparentemente riuscito e dal buffer svuotato, senza riparare il file.
- Prima della mitigazione ogni tick successivo alla soglia ritenta immediatamente, perché né il buffer né l'ultimo flush riuscito vengono aggiornati. Con errori ripetuti il costo cumulato di serializzare un buffer crescente può essere quadratico nel numero di tick; il backoff limita la frequenza, non la crescita del buffer.

## Concorrenza e limiti della soluzione scartata

La pybit installata invoca i callback sincronicamente dal thread `wst` (`_on_message` → `_process_normal_message` → callback). `close()` fa exit e join prima del salvataggio; il reconnect riusa la stessa chiusura. Nei chiamanti attuali non esistono due writer interni concorrenti: un lock nuovo non risolverebbe il problema osservato.

Un checkpoint solo in RAM con path/dev/inode/offset e riscrittura in-place potrebbe evitare il retry in append durante la stessa esecuzione, ma non basta come protocollo affidabile: non distingue un append esterno sullo stesso inode, non sopravvive al riavvio, e deve coordinarsi con la rotazione per data e con l'archiver che può comprimere e rimuovere un file diventato vecchio. Un rollback con truncate ha inoltre un proprio percorso di errore e deve conservare lo stato finché il ripristino non è riuscito. Non è stato introdotto nessuno di questi meccanismi nel collector operativo.

Per una correzione completa va prima stabilita la proprietà esclusiva del file e il coordinamento con l'archiver, poi un confine di commit recuperabile che identifichi il blocco e i byte già appesi. La scelta tra checkpoint persistente, staging o diverso supporto richiede questo contratto; una semplice fsync in più o un try/except locale non lo sostituisce. WAL, nuovi framework, formato, schema e retention restano fuori da questo intervento.

## Prove e stato

Copia candidata: `/tmp/crypto-write-failure-review.m3388700`.

- `main.before.py`: fotografia del sorgente prima della mitigazione, SHA-256 `5e676aa9f1539e5f7b7b8ed850adff7b534706fbf9b74479fb628da5f22b200d`.
- `reproduce_write_failures.py`: quattro fault injection separate su write dopo un prefisso, flush, fsync e close. Verifica il buffer conservato dopo l'errore e rileva duplicazione o riga invalida dopo il retry; non è un test rosso inserito nella suite ufficiale.
- `tests/test_write_failures.py`: regressione del backoff e della chiusura forzata, con tick sintetici e configurazione temporanea.
- `checks.log`: log della prova, dopo acquisizione del lock condiviso.

Le prove sono state accodate una sola volta al lock bloccante `/tmp/codex-recovery-20260908/heavy.lock`, con un worker. Il gate prima dell'esecuzione richiede MemAvailable almeno 4 GiB e memory PSI some avg10 al massimo 5. Il timeout di 60 secondi parte dopo l'acquisizione del lock. Nessun limite o cgroup viene modificato.

ESITO FINALE, 2026-09-08 02:53 CEST: prove completate, gate risorse superato. Reproducer confermato su tutti i quattro stage: il write parziale lascia una riga JSON invalida; flush/fsync/close lasciano due copie di ciascun record dopo il retry. I due test sul backoff e i tre sullo shutdown sono verdi (0,018 s + 0,034 s). Log e reproducer autosufficiente conservati anche in `/tmp/system-efficiency-20260908/crypto-write-failures/`; comando per riprodurre: `/root/get_ws_data_crypto/.venv/bin/python /tmp/system-efficiency-20260908/crypto-write-failures/reproduce_write_failures.py` (da eseguire rispettando il lock e il gate risorse).

Applicati atomicamente soltanto `main.py`, `tests/test_write_failures.py` e l'aggiunta del nuovo script in `tests/run_all_tests.py`. Il SHA del main operativo prima dell'applicazione coincideva con la fotografia iniziale; i tre file applicati coincidono byte per byte con quelli della copia candidata. SHA-256 main finale: `6824a5e1f03b5a04eaa4218040c48208f6b760257c078347af4012fd862f117c`. `git diff --check` verde. Lo stato del repository conserva gli undici file già modificati e aggiunge solo il nuovo test. Nessun riavvio del collector.

Non sono state ripetute le prove verdi non interessate dalla modifica: la precedente suite completa 6/6 resta la verifica documentata prima di questa mitigazione; questa modifica ha aggiunto la verifica mirata dei retry e ha rieseguito solo lo shutdown pertinente. Il runner ufficiale ora include sette script, ma non viene presentato come suite completa rieseguita.

**Rischio residuo esplicito:** duplicazione e righe invalide dopo append parziale non risolte; buffer crescente durante errori prolungati, possibile esaurimento memoria; dati non ancora salvati restano vulnerabili alla terminazione del processo. Nessun limite che scarta tick è stato aggiunto. Il backoff limita soltanto i tentativi automatici da nuovi tick; close continua a forzare un tentativo anche entro l'intervallo.
