# Handoff di ripresa — tedin7/get_ws_data_crypto — 8 settembre 2026

Recuperare ottimizzazioni del collector/archiver e review su integrità delle scritture, durabilità XZ e UTC.

Documento canonico sul ramo `main`. Distingue codice salvato, proposte e verifiche mancanti; non certifica un rilascio applicativo. I documenti storici sono conservati e gli eventuali loro stati precedenti vanno letti insieme agli aggiornamenti qui sotto.

## Autorizzazioni e perimetro

La richiesta corrente autorizza la pubblicazione di questo handoff e dei branch di recupero, con push normale e senza rilasci automatici. Non autorizza a completare adesso le correzioni applicative, fondere codice incompleto nel ramo principale, avviare sessioni ferme, cancellare/archiviare chat, modificare dati storici, acquistare servizi o intervenire in produzione. Gli interventi operativi menzionati sotto appartengono alle sessioni originarie, non sono stati ripetuti.

Le sei unità di recupero originarie risultavano non in esecuzione al controllo di questa consegna. Le sessioni e le sorgenti locali sono conservate. Database, segreti, dati personali e artefatti voluminosi non fanno parte degli allegati selezionati.

## Revisioni da cui riprendere

Base del commit documentale: [`4c9bc9d9dec26772bd9282c3694fb19bd90906a4`](https://github.com/tedin7/get_ws_data_crypto/commit/4c9bc9d9dec26772bd9282c3694fb19bd90906a4), riletta dal remoto. Il ramo principale riceve soltanto questo documento. Ogni snapshot conserva il proprio genitore e il diff pertinente, senza fondere worktree divergenti.

| Filone | Branch di recupero | Commit snapshot | Base originale |
|---|---|---|---|
| audit | [`recovery/2026-09-08/audit`](https://github.com/tedin7/get_ws_data_crypto/tree/recovery/2026-09-08/audit) | [`753c64e200c7`](https://github.com/tedin7/get_ws_data_crypto/commit/753c64e200c725ad7f8074138489d268ffabd3a4) | `39701683917ebfa49b818e9df48a5ba3705164a8` |

Gli snapshot sono punti di ripresa, non branch da integrare integralmente. Il manifest elenca file copiati, impronte SHA-256, esclusioni e origine storica; i file non modificati restano nella storia Git. I percorsi server nei documenti storici indicano la provenienza: non servono per leggere codice e prove su GitHub.

- [Manifest audit](https://github.com/tedin7/get_ws_data_crypto/blob/753c64e200c725ad7f8074138489d268ffabd3a4/docs/recovery-evidence-20260908/snapshot.json)

## Lavoro salvato

- Diff dell’audit: XZ livello 6 configurabile, controllo SHA prima della rimozione, healthcheck leggero, arresto con attesa callback/flush, backoff monotonic dopo errori e limiti Compose conservati.
- Benchmark su campione reale 64 MiB: RSS 662,75→115,61 MiB (-82,6%), roundtrip SHA uguale. È RAM del benchmark di compressione, non del server intero.
- Il worktree di review collector è byte-identico ai file recuperati dall’audit; la sua provenienza è registrata nello stesso snapshot. Il collector fu attivato alle 03:00:14 nella sessione originale, senza garanzia di continuità dei tick nel riavvio.

## Incompleto e proposte da verificare

- P1 riprodotto: append parziale seguito da retry può creare JSON invalido e svuotare il buffer. Backoff limita i retry, non ripara l’atomicità né la crescita della RAM.
- P2: fsync precede il completamento LZMA, quindi non garantisce i byte finali prima della cancellazione del sorgente. Non è attestata una perdita reale.
- Conservata la patch proposta per il controllo UTC degli archivi .part; non applicata al codice. Definire prima proprietà del file e coordinamento collector/archiver.

Durante il push di recupero GitHub ha segnalato quattro avvisi Dependabot aperti sul ramo principale: msgpack (high, #11), idna (medium, #10), urllib3 (high, #9 e #8). Lo stato è stato verificato via API; non è una verifica della sfruttabilità nel servizio. Gli avvisi sono preesistenti al commit documentale e non sono stati corretti da questo incarico.

## Prove recuperate e loro limiti

- Audit: sei script della suite verdi, poi due casi retry e tre shutdown verdi. Le prove sintetiche di write/flush/fsync/close riproducono invece i difetti aperti.
- Le review e le impronte sono allegate; nessun test di questa pubblicazione certifica la correzione dei problemi di durabilità.

I risultati sopra sono storici e valgono per le revisioni o impronte indicate nei relativi rapporti/log. Dove manca un legame certo con l’ultimo diff, la verifica finale rimane aperta. Per il recupero sono stati confrontati gli snapshot con le sorgenti, controllati i file selezionati e i blob dei commit inediti per segreti/artefatti; le occorrenze delle scansioni nei test sono fixture, non credenziali operative. Non sono state ripetute suite applicative per il solo salvataggio documentale.

## File e prove leggibili da GitHub

- [Audit collector](https://github.com/tedin7/get_ws_data_crypto/blob/753c64e200c725ad7f8074138489d268ffabd3a4/docs/recovery-evidence-20260908/audit/getws-review.md)
- [Errori di scrittura](https://github.com/tedin7/get_ws_data_crypto/blob/753c64e200c725ad7f8074138489d268ffabd3a4/docs/recovery-evidence-20260908/audit/crypto-write-failure-review.md)
- [Durabilità e corruzione riprodotte](https://github.com/tedin7/get_ws_data_crypto/blob/753c64e200c725ad7f8074138489d268ffabd3a4/docs/recovery-evidence-20260908/controverifica/CRYPTO.md)
- [Proposta UTC](https://github.com/tedin7/get_ws_data_crypto/blob/753c64e200c725ad7f8074138489d268ffabd3a4/docs/recovery-evidence-20260908/controverifica/archiver-stale-part-utc.patch)

## Passi per terminare

1. Leggere main.py, archiver.py, review e riproduttori; partire dallo snapshot audit.
2. Definire un solo writer e il coordinamento con la rotazione; rendere recuperabile il confine di append, conservando il buffer anche se il rollback fallisce. Non limitarsi ad aggiungere un lock.
3. Completare LZMA prima del fsync del file e della directory, poi valutare la rimozione del sorgente; verificare gli errori in ogni passaggio. Valutare separatamente la patch UTC.
4. Eseguire tests/run_all_tests.py e i casi di errore pertinenti su dati sintetici. Verificare i consumer Price Action che oggi ignorano JSONDecodeError prima di attestare integrità completa.

## Dipendenze e accesso al server

Dati e archivi reali restano esclusi. Collector Docker, archiver e vecchia configurazione Supervisor sono servizi operativi: nessuna nuova attivazione o modifica ai limiti è inclusa. Dipendenza dati con price_action_bot.

## Sessioni coinvolte

Identificativi di provenienza, non istruzioni per riavviare le chat. I transcript completi restano conservati e non vengono pubblicati. Le conclusioni utili sono riportate in questo documento e negli allegati.

- audit-host: `01a07e21-8bf0-7d53-8f60-51a2a3e9bf73`.

Sottoagenti pertinenti recuperati:

- /root/finish_getws: `01a07e68-dba1-7af1-b437-3339bc9f1bdf`.
- /root/crypto_write_failures: `01a07e76-e787-7ce1-8060-8f6cd7cb1c64`.
- /root/archiver_durability: `01a07e9a-bd88-79d3-b3e5-a02b4eb2d5c0`.
- /root/collector_integrity: `01a07e9a-672e-7e42-b664-44e85731d0f1`.

Controrevisioni aggiuntive:

- host: `01a07e83-ac4f-7d03-a771-f21498a9bc1c`.

## Ripresa con accesso GitHub soltanto

Leggere questo handoff, aprire il commit snapshot scelto e confrontarlo con il ramo principale aggiornato. Se l’ambiente consente solo lettura, produrre patch unificate applicabili e comandi di verifica, separando ciò che è stato realmente eseguito da ciò che richiede il server. Non dichiarare modifiche, test, merge o deploy mai eseguiti.
