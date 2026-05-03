# Legacy Validation Summary

The legacy Phase 1-26 implementation was validated through the existing session
logs, phase cross-checks, debt records, and targeted/full pytest runs recorded
under `docs/sessions/` and `docs/cross-checks/`.

For new construction work:

- Record targeted checks in the relevant construction plan.
- Keep substantial verification evidence in `docs/sessions/`.
- Create or update a unit cross-check under `docs/cross-checks/`.
- Run broader `uv run pytest` when the blast radius justifies it.
