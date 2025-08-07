# Contributing

Thanks for your interest in contributing!

Project principles
- Public-only WebSocket ticker collection; no API keys in this repo
- Keep the repo clean: no real data, logs, or secrets

Getting started
```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -u tests/run_all_tests.py
```

Before you open a PR
- Run tests: python -u tests/run_all_tests.py
- Ensure pre-commit is installed and run: pre-commit run --all-files
- Verify no large/binary files added; ws_data/ and logs/ must not be committed

PR checklist
- [ ] No secrets or real data included
- [ ] Tests pass in public mode
- [ ] README/Docs updated if behavior changed

Code style
- Keep it simple and explicit; prefer small PRs

Security
- Never include credentials in code, tests, or CI variables
- If you suspect a vulnerability, follow SECURITY.md reporting instructions
