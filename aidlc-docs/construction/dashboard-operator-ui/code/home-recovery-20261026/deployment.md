# Home recovery correction: deployment and verification

The user authorized individual commit/push and deployment/operational checks,
and then continued the concrete Home recovery task. This recipe preserves the
existing shared CPU 1 / 2048 MiB, machine `6835752b711958`, `/data` volume,
paper/Codex settings, engine interval and installed dependencies.

## Candidate gate

1. Run the final source/test gate and independent QA review.
2. Commit/push the bounded correction; confirm the remote SHA and preserve any
   concurrently added documentation commits. Recheck deployment identity before
   acting. If production or runtime source has advanced, reconcile first.
3. Build a minimal temporary context from the exact committed runtime delta,
   the unchanged `fly.toml`, and an overlay Dockerfile. The verified base is
   `registry.fly.io/crypto-master@sha256:a0e1bd753ba92935c7227bb7c1c5f52fa267eebe2784d1ece99c0a1fab070786`
   (v64 / `dca38fb`). Label the overlay with the exact candidate SHA and copy
   only its verified changed/added runtime files. Do not rebuild dependencies.
4. Deploy that source-labelled image using the existing runtime configuration,
   the existing machine only and `--ha=false`. No resource/env/credential flags.

## Operational evidence

- Compare every tracked runtime file against the running image, including new
  diagnostics/harness files; verify release/image/machine/instance and unchanged
  config/dependencies/volume.
- Verify public/internal health, stable engine/dashboard processes, the first
  natural engine cycle and error/event counts. Do not trigger a synthetic cycle.
- Run one existing-shape four-session Home/Trading protocol observation with
  enhanced classified-alert/first-shell evidence, at least ten minutes plus a
  complete natural cycle. Keep starts/outcomes, warm-up, failures, health,
  memory/high-water, threads and cycle records. Preserve unchanged CPU/cost gates.
- Capture the bounded diagnostic codes from the run; no raw records or secrets.
  A positive full-cycle sample does not certify cold/native/depleted/1 GiB gates.
- Recheck the previously delivered strategy fixes through existing read-only
  replay, without new proposals/orders or canonical data mutation.

## Recovery

If the new revision causes persistent health/process errors or loses bounded
behavior, restore the exact v64 base digest above with the same runtime config,
existing machine and volume, then repeat health/source/engine verification.
Do not roll back merely to erase an observed readiness failure already present
on v64; record the measured outcome and its diagnosed cause.
