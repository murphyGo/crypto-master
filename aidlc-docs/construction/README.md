# AI-DLC Construction

This directory is the construction-stage workspace for new Crypto Master work.
The existing Phase 1-26 implementation is registered as brownfield-complete in
`aidlc-docs/inception/`; it is not replayed here.

Use this structure for new work:

| Path | Purpose |
|------|---------|
| `plans/` | Per-unit, per-stage task plans with `[ ]` / `[x]` checkboxes |
| `<unit>/functional-design/` | Functional design artifacts for behavior or contract changes |
| `<unit>/nfr-requirements/` | NFR requirement notes for safety, reliability, security, observability, or performance changes |
| `<unit>/nfr-design/` | NFR implementation design notes |
| `<unit>/infrastructure-design/` | Runtime, deployment, credential, or topology design notes |
| `<unit>/code/` | Code-generation summaries; application code stays in the workspace root |
| `build-and-test/` | Build, test, and verification instructions or summaries |

`docs/legacy/development-plan.md` remains a legacy chronological reference.
`docs/development-plan.md` is only a pointer to that archive. New work should be
selected by unit, planned in `plans/`, executed through the applicable
construction stage, and cross-checked by unit.
