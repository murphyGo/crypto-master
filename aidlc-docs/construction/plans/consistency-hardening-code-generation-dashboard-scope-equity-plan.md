# Code Generation Plan: consistency-hardening — CH-05 Dashboard scope + aggregate equity (+ CH-19 caption)

## Task

Make the Home command center reflect the operator's scope selection
across all four panels (incidents, safety factors, candidate evidence,
exposure) and report aggregate equity as the sum of latest snapshots
per sub-account, not the equity of the global newest snapshot. Also
include configured-only sub-accounts in command-center discovery so a
freshly configured account becomes visible without first persisting a
trade. Folds in CH-19 (replace the legacy `docs/development-plan.md`
caption with the AI-DLC unit-of-work pointer) since both touch the
same `src/dashboard/app.py` surface.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice IDs: CH-05 (P1) + CH-19 (P2 fold-in)
- Primary owner units: `dashboard-operator-command-center`,
  `dashboard-operator-ui`

## Related Requirements

- FR-032 Streamlit Web App
- NFR-003 Streamlit UI
- NFR-012 Operational Observability

## Steps

- [x] `discover_command_center_sub_accounts` merges configured ids with
      persisted-state ids.
- [x] `latest_snapshot_equity` accepts `aggregate_per_sub_account` flag
      and sums latest-per-sub-account when set.
- [x] `build_command_center_status` filters `events`, `cycles`,
      `safety`, and `incident_rows` by scope; passes
      `aggregate_per_sub_account=True` only on aggregate scope.
- [x] `load_command_center_status` filters `candidate_records` by scope
      so candidate metrics match the panel filter.
- [x] Replace legacy active-queue caption with the unit-of-work pointer
      (CH-19).
- [x] Tests: aggregate-per-sub-account equity, scope filter
      end-to-end (incidents + equity).
- [x] Targeted dashboard regression: 130/130 across all dashboard test
      modules.
- [x] Lint/format/types clean for changed files (pre-existing
      covariance / Literal mode-default mypy errors confirmed
      unrelated by stash + re-run).
- [x] State row updated and spec.md slice rows marked shipped.
- [x] Session log written.

## Verification

- 130/130 dashboard tests pass (3 new regression tests).
- ruff/black clean. Pre-existing mypy errors in `src/dashboard/app.py`
  unrelated to CH-05 (covariance on `render_command_center_links`,
  Literal mode default).

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests added.
- [x] Plan steps closed.
- [x] State row updated.
- [x] Session log written.
