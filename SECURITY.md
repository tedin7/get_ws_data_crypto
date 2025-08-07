# Security Policy

## Reporting a Vulnerability
- Please email the maintainers with a clear description and reproduction steps.
- Do not open public issues for security reports.
- Do not include secrets, PII, or real credentials in any report.

Scope
- Public-only WebSocket data collection; no private endpoints and no API keys.

Leak prevention
- Secrets scanning via gitleaks is configured.
- .gitignore prevents data/logs and .env from being committed.

Responsible disclosure
- We will triage and respond as quickly as possible. Thank you for responsibly reporting.
