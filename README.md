# get_ws_data_crypto

A minimal Python client that streams public Bybit ticker data (BTCUSDT by default) over WebSocket and writes newline-delimited JSON to ws_data/.

Public mode is the default — no API keys required.

Features
- Public WebSocket (no credentials)
- Buffered writes to JSONL with flush interval
- Robust reconnect with backoff
- Tests for imports and data writing in public mode

Quick start (local venv)
```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -u main.py
```
Data will be written to ws_data/price_data_YYYY-MM-DD.jsonl and logs to ws_data/logs/ws_log.log.

Configuration
- Default symbol: BTCUSDT (edit in [config.py](config.py))
- TESTNET: False by default (edit in [config.py](config.py))
- Data and logs: ws_data/

Do not commit real data
- ws_data/ and logs/ are ignored by default (.gitignore). Keep it that way.

Tests
```bash
. .venv/bin/activate
python -u tests/run_all_tests.py
```
You should see Import Test and Functionality Test both PASSED.

Security model
- Public-only; no API keys are used or required
- Secrets scanning: gitleaks is configured via .gitleaks.toml and pre-commit

Contributing
See CONTRIBUTING.md. Please do not include any secrets or real data in PRs.

License
MIT — see LICENSE.
