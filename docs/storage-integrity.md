# Collector / archiver storage contract v1

Status: proposed implementation, exercised on synthetic local files only. No deployment,
production data repair, or hardware power-loss validation is implied. Based on collector
snapshot `753c64e200c725ad7f8074138489d268ffabd3a4`.

## Ownership and participants

All participants must use the same local POSIX filesystem and the same persistent lock
inodes. The collector holds `ws_data/.collector.lock` exclusively for its active lifecycle;
a second collector fails before connecting. Append, recovery and archive/delete operations
hold an exclusive `<source>.lock`. Consumers must hold a shared lock with the SAME path
for their entire read. Lock files are never removed or replaced: their inode is the shared
synchronization identity, not their age or textual contents.

The lock is advisory. Legacy collectors, legacy archivers, legacy readers, manual writes,
network filesystems without equivalent locking/durability semantics and symlink/untrusted
directory manipulation are outside this contract. A mixed-version rollout is unsafe.
Both Docker services must actually share the same underlying data and lock directories;
reading Compose does not prove that the live mounts or processes satisfy this condition.
No service restart, mount change or rollout was executed for this work.

## Append boundary, retry and restart

A batch is serialized before touching its JSONL, without changing record fields, timestamp
format or daily filenames. `<source>.append.pending` is an atomic, fsynced intent containing
protocol version, source device/inode, pre-append byte offset, exact base64 payload and its
SHA-256. This is one pending batch, not a second archive of the history. Source creation,
intent publication and intent deletion each include directory synchronization.

An append uses unbuffered file I/O and handles short writes. It must finish write, flush,
fsync and close before the batch is acknowledged. Any write/flush/fsync/close error attempts
a checked truncate to the saved boundary and another fsync. Failed rollback leaves the
same batch, the entire unacknowledged buffer, intent and per-file lock retained. Future
attempts inspect identity, length and suffix; they do not blindly append the buffer again.
Foreign suffixes or a changed inode fail closed, without truncating unknown data.

On restart, under the singleton lock and BEFORE connecting to WebSocket, pending intents
are validated. A matching complete suffix is synced and acknowledged without replay;
a known partial suffix is rolled back and replayed. Corrupt intents or ambiguous source
identity block startup. A cleanup-only retry does not replay an already completed batch.
An existing historical incomplete JSONL tail is reported, not silently repaired.

The collector clears only the committed prefix of its buffer. A failed batch keeps its
original file across midnight; only a subsequent batch selects the next daily filename.
A day with an existing `.xz` is never recreated by appending a new raw file. The existing
naive local timestamps/day naming are intentionally unchanged; this is NOT a UTC migration.

## Archive publication and source removal

The archiver acquires the exclusive per-file lock, rechecks eligibility after its scan,
and skips pending intents. Age alone never authorizes access to another writer's file.
A new partial archive is created exclusively; recent partials are not overwritten.

Required order:

1. Hash the locked source and durably publish the source manifest.
2. Finish/close LZMA into a still-open raw file, then flush/fsync/close that raw file.
3. Verify the full decompressed SHA and unchanged source identity/metadata/hash.
4. Publish `.xz` by rename, fsync the final archive and its directory. Existing matching
   archives also require synchronization, not only a successful cached read.
5. Publish the compressed-file hash manifest durably, recheck source ownership, unlink
   the source and fsync its directory.

Before source removal, any error retains the original. If the directory fsync AFTER
unlink fails, the operation reports FAILED, while the already verified/synced archive is
retained; the source is not falsely reported as still present. A retry must reconcile
actual paths rather than blindly deleting/recompressing. Source unlink errors are no
longer swallowed as success. Hash sidecars keep their original informational format.

Stale `.part` clock normalization is reviewed as a separate change. It does not replace
locking and does not reinterpret timestamp fields in existing market data.

## Consumer contract / Price Action

Consumer snapshot reviewed: `tedin7/price_action_bot` at
`e27b60b066cf29befdd514edecb4a31544cd8b9b`, scripts
`convert_ws_to_backtest.py` and `backfill_from_ws_archive.py`. Neither may silently skip
invalid JSON or missing required fields and then report a complete conversion. A reader
must hold the shared source lock, refuse a pending append, select the representation under
that lock and reject divergent raw/XZ pairs. Identical pairs represent one input, not two.

The separate consumer patch is a prerequisite for this coordinated protocol. No existing
Parquet, tick archives, GA cache, database, trading task or provider job is changed by the
collector patch. Existing Price Action numeric/outlier sanitization and its day/schema
policy remain distinct from detecting syntax/ownership errors.

## Explicit limitations

This is not exactly-once market-feed delivery. Ticks not yet staged in a durable batch are
still volatile. Prolonged storage failure can grow the in-memory buffer; no tick-dropping
limit or disk spooling/backpressure policy has been silently added. A finite buffer or
transport pause requires a separate data-loss/reconnect policy.

The protocol verifies the appended suffix and cooperative ownership, not arbitrary
out-of-band changes anywhere in the old prefix. SHA agreement is not provenance or proof
that historical records were semantically correct. No automatic historical cleanup occurs.

Fault injection and subprocess termination demonstrate program ordering and process-crash
recovery on the test filesystem. They do not simulate a kernel crash, power loss, failing
controller, full-volume soak, or guarantee hardware persistence. The original runner still
requires the real pinned runtime dependencies and its pybit-specific shutdown tests.

References: Python `lzma.LZMAFile` documentation (caller-supplied raw file remains open);
Linux `fsync(2)` documentation (directory entry persistence requires a directory fsync).
