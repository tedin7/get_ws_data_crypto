# get_ws_data_crypto

A minimal Python client that streams public Bybit ticker data (BTCUSDT by default) over WebSocket and writes newline-delimited JSON to ws_data/.

Public mode is the default — no API keys required.

Features
- Public WebSocket (no credentials)
- Buffered writes to JSONL with flush interval
- Robust reconnect with backoff
- Tests for imports and data writing in public mode
- Dedicated archiver process to compress and checksum historical data
- CI and hygiene: gitleaks secret scan, Dependabot, PR/issue templates

Quick start (local venv)
```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -u main.py
```
Data will be written to ws_data/price_data_YYYY-MM-DD.jsonl and logs to ws_data/logs/ws_log.log.

Configuration
- Default symbol: BTCUSDT (edit in [config.py](config.py:1-42))
- TESTNET: False by default (edit in [config.py](config.py:1-42))
- Data and logs: ws_data/
- Buffer/flush/reconnect settings: see [config.py](config.py:1-42)

Do not commit real data
- ws_data/ and logs/ are ignored by default (.gitignore). Keep it that way.

Tests
```bash
. .venv/bin/activate
python -u tests/run_all_tests.py
```
You should see Import Test and Functionality Test both PASSED.
- Import test verifies core dependencies and modules import.
- Functionality test simulates ticker messages and verifies JSONL writes.

Docker (runtime and archiver)
There are two services defined in [docker-compose.yml](docker-compose.yml:1-33):

- app
  - Purpose: connects to Bybit Unified V5 public websocket and writes JSONL lines.
  - Image: python:3.11-slim (deps installed at container start).
  - Command: installs requirements then runs ["python", "-u", "main.py"].
  - Volumes:
    - ./:/app (live code mount)
    - ./ws_data:/app/ws_data (data and logs persisted to host)
  - Healthcheck: simple placeholder.

- archiver
  - Purpose: compress and checksum historical JSONL to .xz and .sha256 in ws_data.
  - Build: uses [Dockerfile.archiver](Dockerfile.archiver:1-25) (includes xz-utils).
  - Command: ["python", "-u", "archiver.py"].
  - Shares the same volumes as app.

Common operations:
```bash
# Start both services (build images as needed)
docker-compose up -d --build

# Tail app logs
docker-compose logs -f --no-color app

# Tail archiver logs
docker-compose logs -f --no-color archiver

# Stop everything
docker-compose down
```

Dockerfiles:
- App [Dockerfile](Dockerfile:1-13)
  - Buildable image that installs Python deps at build time and runs ["python", "main.py"].
  - Note: current compose app service uses python:3.11-slim with runtime pip install for convenience.
  - You can switch compose to build from this Dockerfile for reproducible, faster startups.

- Archiver [Dockerfile.archiver](Dockerfile.archiver:1-25)
  - Based on python:3.11-slim, installs xz-utils and tzdata, installs Python deps at build time, and runs ["python","-u","archiver.py"].

Security and hygiene
- Public-only; no API keys used or required
- Secret scanning via gitleaks configured with .gitleaks.toml and .pre-commit-config.yaml
- .gitignore excludes ws_data/ and local env artifacts
- SECURITY.md documents reporting policy and scope

CI and repo automation
- GitHub Actions at [.github/workflows/ci.yml](.github/workflows/ci.yml:1)
  - Installs dependencies and runs tests
  - Secret scan step uploads SARIF (gitleaks)
  - Required status job to gate merges
- Dependabot at [.github/dependabot.yml](.github/dependabot.yml:1) for pip and Actions
- Issue templates: [.github/ISSUE_TEMPLATE/bug_report.md](.github/ISSUE_TEMPLATE/bug_report.md:1), [.github/ISSUE_TEMPLATE/feature_request.md](.github/ISSUE_TEMPLATE/feature_request.md:1)
- PR template: [.github/pull_request_template.md](.github/pull_request_template.md:1)

Notes and tips
- Logs and data paths:
  - App runtime logs: ws_data/logs/ws_log.log
  - Archiver logs: ws_data/logs/archiver.log
- Default mode: mainnet public stream (TESTNET=False)
- If you enable the app Dockerfile in compose, prefer setting ENV PYTHONUNBUFFERED=1 to keep logs unbuffered.



Security model
- Public-only; no API keys are used or required
- Secrets scanning: gitleaks is configured via .gitleaks.toml and pre-commit

Contributing
See CONTRIBUTING.md. Please do not include any secrets or real data in PRs.

License
MIT — see LICENSE.
