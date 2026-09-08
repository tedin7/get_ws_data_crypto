# Review aggiuntiva crypto — 8 settembre 2026, 02:59 Europe/Rome

Due nuovi difetti dimostrati sul codice letto; nessuna modifica al repository.

## Revisione e perimetro

HEAD letto direttamente da `.git/HEAD` e relativo riferimento: `39701683917ebfa49b818e9df48a5ba3705164a8`.
Ultima rilettura del codice coinvolto: 02:59:30 Europe/Rome.

- `main.py` SHA256 `6824a5e1f03b5a04eaa4218040c48208f6b760257c078347af4012fd862f117c`
- `archiver.py` SHA256 `59ff7428b93427361fcb1e56df707c0f4104fad949eedaa0e45f455bb7ab2f6d`

Letti main, archiver, test pertinenti e rapporti RAPPORTO.md/CHECKPOINT.md del precedente audit. Seguiti i chiamanti di save_price_data (handle_ticker e close; close da reconnect e finally di main) e compress_xz (process_file, invocato da run_once/main_loop). Nessun AGENTS.md trovato in /, /root o repository/sottodirectory cercate. Nessun comando Git, servizio, rete, configurazione o dato operativo consultato. Le prove hanno estratto le sole funzioni con AST, evitando import applicativi e loro effetti collaterali.

## P1 — Il retry dopo una scrittura parziale corrompe una riga e dichiara il buffer salvato

**File:** `/root/get_ws_data_crypto/main.py:88-96`, gestione errore a 100-103.

L'append può fallire dopo aver scritto solo parte di un record. L'eccezione conserva il buffer, ma non ripristina il file: al tentativo successivo il primo record viene concatenato al frammento già scritto. Quando questo tentativo riesce, il buffer viene svuotato anche se il file contiene una riga JSON invalida. È un difetto diverso dalla duplicazione già ammessa dal commento a riga101.

**Prova locale eseguita:** metodo save_price_data estratto dalla revisione sopra; sink StringIO che alla quarta write scrive un carattere e solleva OSError, poi accetta tutte le scritture. Buffer sintetico `[{'price':42}]`; due invocazioni consecutive producono:

```text
file = '{"price": 4{"price": 42}\n'
buffer = []
json.loads(prima_riga) -> JSONDecodeError: Expecting ',' delimiter
```

Un errore disco durante un append costituisce il caso reale equivalente; non è stato provocato sul filesystem operativo. Il revisore padre ha verificato separatamente che i consumatori Price Action `scripts/convert_ws_to_backtest.py:40-44` e `scripts/backfill_from_ws_archive.py:44-47` scartano JSONDecodeError: la riga coinvolta viene quindi persa dalla conversione. Questi consumatori non sono stati riletti da questo sottoagente.

**Rimedio minimo:** nel percorso condiviso di scrittura registrare la posizione iniziale del batch e, in caso di errore, ripristinare/troncare a quella posizione prima di consentire il retry, assumendo e verificando un solo writer; conservare il buffer e impedire il normale retry se il rollback fallisce. Verificare una scrittura parziale seguita da recupero, oltre agli errori prima dell'apertura già coperti dai test.

## P2 — fsync precede il completamento dell'archivio XZ

**File:** `/root/get_ws_data_crypto/archiver.py:64-76`; rimozione sorgente a 185-196.

compress_xz chiama fsync mentre il LZMAFile è ancora aperto. La chiusura successiva emette ulteriori byte e chiude il file sottostante. process_file rinomina e verifica il risultato, poi cancella il JSONL originale senza un nuovo fsync sull'archivio completato. La verifica legge dalla cache e non dimostra persistenza su disco.

**Prova locale eseguita:** funzione estratta, lzma reale, livello0, 100 righe sintetiche in directory temporanea con prefisso crypto- sotto la directory autorizzata. L'unica fsync è stata osservata con os.fstat sul suo descrittore:

```text
size al momento di fsync = 0 byte
size dopo la chiusura = 92 byte
lzma.decompress(archivio) == sorgente: True
```

Questo dimostra che fsync non copre i byte finali. **Rischio condizionato a crash del sistema o perdita di alimentazione** dopo cancellazione del sorgente: l'archivio potrebbe non essere durevole. Nessuna perdita reale o crash simulato; la conseguenza dipende anche dal filesystem.

**Rimedio minimo:** completare e chiudere LZMA, poi aprire/sincronizzare il file XZ definitivo prima di eliminare il sorgente; sincronizzare anche la directory per rendere durevole la pubblicazione tramite rename. Verificare l'ordine close → fsync archivio → rename/pubblicazione durevole → rimozione sorgente.

## Limiti

Review circoscritta al codice locale e a micro-riproduzioni sintetiche; nessuna suite, build, installazione o verifica runtime. Gli alberi possono cambiare dopo l'ultima rilettura; applicare i rilievi solo dopo confronto degli hash. Nessuna patch proposta/applicata e nessuna affermazione di integrità dei dati operativi.
