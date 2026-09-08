# Verification performed — 2026-09-08

Starting revision: `753c64e200c725ad7f8074138489d268ffabd3a4`.
Work was executed against a local reconstructed subset. Original application files and
original test scripts were checked against GitHub Git-blob SHA-1 values before editing.
This is not a claim that a full repository clone, Docker build, CI run or server test ran.

## Executed results

- Baseline AST reproduction: partial append then retry leaves
  `{"price": 4{"price": 42}\n` and an empty buffer. Real LZMA reproduction observes
  fsync at 0 bytes, final archive 92 bytes, roundtrip equal.
- `tests/test_storage_integrity.py`: 37 passing tests. Real application methods and
  temporary FileIO/flock/LZMA; only the WebSocket import/configuration are substituted.
  Includes short/partial/zero writes, flush/fsync/close errors, rollback failure,
  intent publication/cleanup failures, inode/foreign suffix checks, late callbacks,
  thread concurrency, midnight batch ownership, reader locks and archive stage failures.
  Three tests terminate a real child process at intent/partial/full append boundaries
  and recover in the parent. These are process crashes, NOT simulated power loss.
- Separate `tests/test_archiver_utc.py`: four tests were run before and after the UTC correction; the pre-fix run fails
  on naive/aware comparisons and stale cleanup, and all four pass afterwards. Includes process timezone
  variation, exact age threshold, fresh/stale .part and lock precedence.
- Original archiver 4, healthcheck 4 and retry/backoff 2 tests pass.
- `tests/run_all_tests.py`: actually executed, overall FAIL. Six of nine scripts pass;
  test_import and test_shutdown are blocked by missing pybit; test_main by missing
  pkg_resources. test_functionality passes but exercises a copied mock writer, not the
  real collector. It is not counted as evidence of the new storage protocol.
- Price Action separate consumer patch: 17 new contract tests pass. JSON errors/missing
  fields/incomplete tail, pending markers, shared lock, divergent/identical raw/XZ,
  truncated XZ, representation change after discovery, no writes on invalid input,
  converter failure status and in-memory DataFrame checks.
- Price Action original `test_ws_archive_scripts.py`: two pass, three fail because a
  Parquet engine (pyarrow/fastparquet) is missing, both before and after the reader patch.
  No successful Parquet roundtrip or full Price Action suite is claimed.

## Not performed

No live WebSocket subscription, data-provider requests, service restart, Docker build,
production I/O, historical JSONL/XZ or Parquet changes, trading, cache cleanup, dependency
upgrade, merge, deploy, power-loss test or live-mount validation. Benchmark numbers in
historical handoffs were not repeated and are not attributed to this implementation.

The downloadable evidence bundle includes stdout/stderr logs, original source blob
hashes, complete proposed files, baseline reproducer and applicable patches. The separate
Price Action patch must be reviewed against its own snapshot and any concurrent work.
Storage contract v1 requires collector, archiver AND readers to cooperate; this branch
alone does not establish production readiness or exactly-once feed delivery.
