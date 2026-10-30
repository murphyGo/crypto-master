# Dashboard source recovery rearming — 2026-10-30

- Unit: `dashboard-operator-ui`; related command center and notifications/ops.
- Debt: DEBT-083 Critical; latest source `596636b`, runtime v69/source120b440.
- Requirements: FR-028–032/036/038/042; NFR-003/007/008/011/012;
  BDL-NFR-02/03/04/06/07/08; US-012/014/020/023. Legacy7/8.2/19.3.
- Stages: bounded Functional/NFR amendment → source/tests → qualification →
  same-configuration delivery and operational observation.

[Answer]: User “계속 진행” follows the reported next work: correct recovery
after retry exhaustion and investigate initial latency. This continues the
existing fix/test/commit/push/same-capacity deployment authority. The previous
manual-only source_changed latch is explicitly superseded by this amendment.
No trading policy, live intent, source-proof relaxation, capacity or cost change.

## Contract and routine implementation choices

One admitted logical job still gets at most three attempts within its original
30 s cooperative recovery window. Exhaustion settles that job and its page
watcher. The failure retains a bounded token until
`max(original_admission + 30 s, failure_time + 2 s)`. Before eligibility, ordinary
requests return explicit unavailable/stale without work. At/after eligibility,
the next ordinary request may admit one new coalesced job and a new window.
No timer launches background jobs, and progress probes cannot admit or clear
anything. Idle failed pages keep the existing explicit retry control.

This limits a failed episode and spaces automatic episodes; it is not a sliding
three-attempts-per-30-seconds guarantee across window boundaries. An explicit
operator retry may bypass the cooldown, scoped to the exact captured token.
Corruption and other errors retain their existing ordinary two-second TTL and
manual retry semantics; they gain no in-job retries. Fresh/stale cache ages never
renew on failure. All new attempts rediscover and fully verify canonical input.

At most64 terminal tokens plus reserved active-job slots remain. Unexpired
source-change cooldowns cannot be evicted to evade their rate bound. Expired
tokens are evictable. One worker/four admitted jobs, fair retry scheduling,
foreground4s and all encoded/cache/source/state budgets remain unchanged.

## Work

- [x] Review rollback evidence, current service and prior Functional/NFR limits.
- [x] Record the authorized Functional/NFR amendment and explicit limits.
- [x] Add red regression for long mutation then stability, cooldown boundaries,
  coalescing, bounded metadata, old callbacks, freshness and read-only progress.
- [x] Implement timed error tokens and request-driven rearming; targeted tests.
- [x] Harden protocol observation against queued responses after timeout.
- [x] Profile initial query work and apply only a measured, parity-preserving
  improvement if supported; otherwise retain a concrete performance diagnosis.
- [x] Full regression, changed Python Black/Ruff and source-wide mypy.
- [x] Commit/push exact source, deploy same existing machine/resources and verify
  runtime hashes/configuration/health/first cycle before bounded observation.
- [x] Preserve every failed sample; update session/cross-check/state/debt/map.

## Operational limits

The amendment prevents permanent service-wide source-error latching across later
requests; it does not promise complete pages during sustained writes or repair
an already terminal idle page automatically. Home cold5s/warm2s and the original
native/depleted/1GiB gates remain unchanged. A new observed persistent failure,
health/process regression or violated resource bound triggers exact-image
rollback consideration. Restore v69's exact source120b440 image if needed.

## Disposition

Implementation/delivery cycle complete: sourceffe95b0 pushed, Flyv70 deployed,
182hashes/config verified.3,053tests/static gates pass. Two operation samples
remain failed: first host-sleep interruption; repeated727.327948s/144complete
pages/145healthy checks but one Binance418 engine error (11monitor passes).
No source_changed exhaustion occurred in the repeated sample; live rearming
branch is not claimed exercised. Later stable-input/fresh sessions and12-monitor
cycles pass separately. DEBT-083 remains Critical; DEBT-090 High is queued.
Initial Home13.10s, cold/native/depleted/original1GiB/cost gates remain open.
