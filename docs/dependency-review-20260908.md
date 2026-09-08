# Dependency review — 2026-09-08 — separate from storage changes

No requirements, running environment or Dependabot alert state was changed.
Snapshot requirements and main both pin msgpack 1.1.2, idna 3.11 and urllib3 2.6.3.
Main additionally updates requests, prometheus-client, charset-normalizer and certifi;
those changes must not be reverted by wholesale integration of the recovery branch.

## Upstream advisory comparison

This is a version/risk review, NOT verification of this repository's alert IDs or of
exploitability in its live service. The handoff's alerts #11/#10/#9/#8 are historical.
The connector did not expose a Dependabot-alert reader for current state.

| Pin | Primary advisory | Version comparison / required exposure |
| --- | --- | --- |
| msgpack 1.1.2 | GHSA-6v7p-g79w-8964, high | Falls in <=1.2.0. Crash requires reusing a streaming Unpacker after an error, on untrusted input. The upstream advisory still says patched version "None" and describes 1.2.1 as upcoming; the reviewed GitHub database reports 1.2.1 fixed. Confirm release/artifact availability before selecting an upgrade. |
| idna 3.11 | GHSA-65pc-fj4g-8rjx, moderate | Falls in <3.15. Crafted oversized internationalized names can cause expensive processing. Upstream gives 3.15 as the complete fix; 3.14 only covered part of the surface. |
| urllib3 2.6.3 | GHSA-mf9v-mfxr-j63j, high | Falls in >=2.6.0,<2.7.0. Specific streaming decompression/Brotli or drain_conn flows; fixed in 2.7.0. |
| urllib3 2.6.3 | GHSA-qccp-gfcp-xxvc, high | Falls in >=1.23,<2.7.0. Sensitive headers may cross origins in a low-level ProxyManager redirect flow; fixed in 2.7.0. |

The inspected main.py and archiver.py do not directly call msgpack.Unpacker,
idna.encode, urllib3's streaming/decompression API or ProxyManager's low-level API.
This is NOT a full dependency call-graph analysis: pybit and transitive paths were not
exercised, and real proxy settings, environment and installed packages were not inspected.
Public WebSocket mode is not proof that a vulnerable dependency is unreachable.

Recommend a distinct dependency review/branch: resolve compatible releases against
current main, install in a disposable environment, run the actual dependency/import/
pybit-shutdown suite and pip check/audit, then inspect the resulting alert state. Do not
silence or close alerts based only on lack of direct imports. No candidate upgrade was
applied or claimed tested here.

## Actual environment blockers

The general collector runner was executed; import/pybit-specific tests are blocked by
missing pybit, and test_main.py cannot import pkg_resources. An attempted isolated install
of pybit 5.14.0 failed to resolve in this environment. This does not prove the release is
unavailable publicly. Price Action's existing Parquet cases cannot run to completion
because neither pyarrow nor fastparquet is installed. None of these failures is evidence
that the new code fixed the security advisories.

## Primary sources read

- https://github.com/msgpack/msgpack-python/security/advisories/GHSA-6v7p-g79w-8964
- https://github.com/advisories/GHSA-6v7p-g79w-8964 (reviewed metadata differs on release status)
- https://github.com/kjd/idna/security/advisories/GHSA-65pc-fj4g-8rjx
- https://github.com/urllib3/urllib3/security/advisories/GHSA-mf9v-mfxr-j63j
- https://github.com/urllib3/urllib3/security/advisories/GHSA-qccp-gfcp-xxvc

Read-only follow-up commands, NOT executed against the live repository/environment:

```sh
gh api --paginate 'repos/tedin7/get_ws_data_crypto/dependabot/alerts?state=open'
# In a DISPOSABLE verification environment with the intended requirements installed:
python -m pip check
python -m pip_audit -r requirements.txt
```
