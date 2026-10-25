# DEBT-087/088/089 rollout evidence

Runtime source: `f0f3e524eda0ac8b5dcab0b0aad9dfaf8e100291`; Fly v63.
Observation dates are October 25 UTC / October 26 KST.

- `predeploy.json`: v62 source hashes, process/configuration and health baseline.
  Historical error events in the captured tail are identified by timestamp;
  unrelated exchange error messages are omitted.
- `runtime-delta.json`: seven modified files and two additions; no runtime
  configuration, dependencies, policy or strategy-definition source changes.
- `Dockerfile.strategy-overlay`: exact overlay on the verified v62 image.
  The temporary context's `[build].dockerfile` selected this file. All other
  Fly runtime settings came from the tracked `fly.toml` unchanged.
- `postdeploy.json`: source hashes, release identity, health and first cycle.
- `operational.json`: follow-up plus deployed-method read-only scoring, cap
  payload and funding coverage checks against current persisted inputs.
- `qualification.json`: assertions checked against the captured evidence.

The first cycle generated no new proposal or cap rejection event. Empty
`proposal_checks` and `cap_checks` therefore mean **unobserved**, not event-test
passes. `deployed_readonly_replay` is explicitly separate: selectors/scoring use
controlled confidence, and cap rendering omits proposal joins and market marks.
No production engine cycle, strategy analysis, exchange access, order, repair,
cash update or policy application was triggered by those probes. The 24 input
hashes remained unchanged. Funding is unknown; carry is an assumed scenario.

See [rollout session](../../../../../docs/sessions/2026-10-26-strategy-evidence-production-rollout.md)
for authorization, individual commits, checks, preserved environment and limits.
