# Code Generation Plan: notifications-ops

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Configuration Management | 1 | `exchange-integration` |
| Fly.io Deployment | 8 | |
| EngineConfig Env Override | 10 | `trading-core` |
| Log Retention Policy | 10 | `persistence-data-integrity` |
| Notification Push Backend | 11 | `proposal-runtime` |
| Telegram Notification Backend | 12 | |
| EngineConfig Remaining-Fields Env Override | 13 | `trading-core` |
| Email Notification Backend | 13 | |
| SMTP_SSL Alternative | 14 | |
| Diagnostic Clarity | 15 | `proposal-runtime` |
| Observability + Logger Test-Friendliness | 26 | `quality-governance` |

## Completed Code Generation Steps

- [x] Implement configuration behavior used by runtime, credentials, and notifications.
- [x] Add Fly.io deployment packaging and runtime process support.
- [x] Add log retention behavior and notification push backends.
- [x] Add Telegram, email, and SMTP_SSL notification support.
- [x] Improve diagnostic clarity, observability, and logger test friendliness.

## Evidence

- Requirements: FR-015, NFR-004, NFR-011, NFR-012.
- Primary paths: `src/proposal/notification.py`, `Dockerfile`, `fly.toml`, `start.sh`, `docs/deployment.md`.
- Cross-checks: phase 8, phase 10, phase 11, phase 12, phase 13, phase 14, phase 15, and phase 26 reports.
- Session logs: related Phase 1, 8, 10, 11, 12, 13, 14, 15, and 26 entries under `docs/sessions/`.

## Future Work

Add future notification, deployment, credential, runtime process, or operations
changes as new unchecked steps here.
