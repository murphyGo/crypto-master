# Cold readiness evidence, 2026-10-25

`paired-measurements.json` is the final twenty-pair comparison against
`bf44822`, using fixed generated inputs and a warm process with fresh services.
It is empty-query-cache evidence, not process-cold or native page acceptance.
Full payload/provenance hashes match for activity, snapshots and proposals;
the threshold comparison checks the deliberately compact lifetime scalar,
evaluation, digest and coverage. All samples, including slow samples, remain.
The driver records local Python/dependencies and fixture hashes.

`pre-refinement-partial-measurements.json` is an explicitly intermediate run.
Its synthetic proposal fixture failed canonical validation, was repaired and
fully validated, and the final suite reran all workloads. It is not final evidence.

`source-validation.json` identifies all six changed Python files and the final
checks. Drivers are archived as text for reproducibility. The deployment overlay
retains the exact v60 dependency image and copies only four dashboard files;
production capacity and `fly.toml` stay unchanged.

The independent server protocol test uses four real Streamlit WebSocket sessions,
not native browsers. It records full-script completion, metrics/table/chart
coverage, explicit incomplete states, latency and public health. Remote sampling
is read-only and observes the existing engine cadence. Neither this test nor the
2 GiB guest certifies native viewport or the originally declared 1 GiB guest.
