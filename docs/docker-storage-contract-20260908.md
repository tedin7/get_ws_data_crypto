# Coordinated Docker storage contract (2026-09-08)

This continues `fb06114d7d0845de67f31bd5ce2d15e1dea58f64`, not a rewrite of
historical archives. The four dependency updates from current main
`bfcb47422d2ca11dc92f4d2d0616d63387512ba0` are retained unchanged.
The previous verification document records earlier work, not these Docker results.

## Protocol v2; append intent format remains v1

The persistent `.archive.namespace.lock` protects creation of **logical day lock
anchors**. Readers open it read-only and hold a shared lock while discovering and
reading D and D+1. The writer/archiver acquires it exclusively before creating a
new `<source>.lock`, then acquires that day's exclusive lock before releasing the
namespace lock. Existing day anchors are never removed/replaced and can be locked
directly: reading old days need not block appends to unrelated existing days.

Readers then acquire all relevant existing day locks in sorted order, before
selecting raw/XZ representations or checking pending/failed markers. Missing day
anchors are safe to observe only while holding the namespace lock. Consumers
never create locks, so the data mount can and should be read-only. Pending intents
must be recovered by the owning collector, not interpreted as committed input.
A busy reader returns an explicit error without publishing Parquet; a retry takes
a fresh snapshot. A writer retains its existing batch/buffer on lock contention.

All participants must be upgraded together. The v1 writer does not participate in
the namespace gate and cannot be mixed with v2 readers. Persistent lock files are
not stale garbage; never delete them. File ownership, rollback, intent replay,
LZMA/footer/fsync order and per-file locking from storage-integrity.md still apply.
A committed read is a point-in-time snapshot, not proof that future late ticks
cannot arrive. Existing output sets are not silently refreshed or recertified.

## Docker mapping

Both collector services now explicitly bind `./ws_data` to `/app/ws_data` and
set the same `WS_DIR_PATH`. `config.py`, logging and healthcheck honor that path;
previously the writer ignored this environment variable while archiver honored it.
No existing source directory is moved. A custom standalone container may use a
different internal path provided the same underlying store is mounted there.

Price Action has an explicit offline Compose entrypoint with `/archives:ro` and
separate `/output:rw`; it never starts trading or database services. Its three
archive readers use the same protocol. `WS_ARCHIVE_MODE=immutable` is an explicit
escape hatch ONLY for externally frozen snapshots, never an automatic fallback
when locks are absent or unreadable.

The joint integration runner belongs to the private Price Action repository: it
checks out this public repository at an exact commit and builds all three actual
Dockerfiles. Thus private reader code is never copied into this public repository.
Only fresh synthetic directories/volumes are mounted, runtime networking is
blocked, and the actual collector callback/save/recovery and archiver functions
are used. Process-kill tests are not hardware power-loss tests. Named local volumes
and local bind mounts are in scope; NFS/SMB, Desktop sharing and production mounts
must not be inferred to work from Linux CI results.

## Reproducible standalone test

```sh
docker build -t collector-contract -f Dockerfile .
docker build -t archiver-contract -f Dockerfile.archiver .
docker run --rm --network none --tmpfs /tmp -e WS_DIR_PATH=/tmp/contract-ws \
  -v "$PWD/tests:/app/tests:ro" collector-contract python -u tests/run_all_tests.py
```

No `.env` from production is needed or read. No merge, deployment, live feed,
provider request, production archive access or historical cleanup is authorized
by this documentation. Exact final revisions/results are recorded in the PRs and
joint verification report, rather than inferred from the existence of test files.

References: Docker Engine bind-mount documentation; Linux `flock(2)`; Python
`importlib.metadata` (the legacy smoke test no longer requires `pkg_resources`).
