# NFR Requirement Baseline: streaming-activity-inputs

**Status:** Formalization of operator-approved functional rules and already
approved shared-VM BDL targets. This adds no new acceptance threshold; proposed
implementation constants belong to the following NFR Design review. No source,
storage, trading policy or deployment change is made at this stage.

| Requirement | Carried-forward meaning |
|---|---|
| Exactness | Preserve fixed-time canonical counts, source selection, UTC/ties, modes, financial semantics and consumer-specific results. New entry-time safety anchoring is explicit in the approved Functional contract, not falsely claimed identical default timing. |
| Bounded retention | No raw/archive or rich-event backlog; exact required state/provenance and every temporary buffer must be admitted before accumulation. Numeric constants are proposed in NFR Design. |
| Readiness | Original BDL-NFR-03: complete pages p95 <=5s cold / <=2s warm, >=20 samples per scenario. A fast incomplete shell is separately <=5s and never complete acceptance. |
| Memory | Original BDL-NFR-02: dashboard growth <=256 MiB; guest use <=768 MiB on the declared 1 GiB condition. Current 2 GiB observations do not certify it and no rebaseline is selected. |
| Continuity | Original BDL-NFR-04: four sessions >=10min, all health <5s, actual whole engine-cycle evidence and no concealed failures. Do not alter engine cadence. |
| Safety/availability | Hard unreadable/incomplete inputs never become healthy/zero data or a new trading permission. Cache failures may fall back only to bounded canonical reads; runtime failure flow is an explicit proposed amendment. |
| Compatibility | Keep canonical writers/retention, existing model contracts and legacy APIs. Runtime legacy malformed-row warning/skip policy and `None`/extra-list cache rules stay explicit. |
| Security | Preserve NFR-011/012, paper/live controls and CLI provider. Diagnostics allow stable reasons/counts/times only; no credential, raw payload, URL, source path or operator identifiers. |
| Operations | Same machine, volume, shared CPU 1 / 2048 MiB. No added service/cost. Failed or unqualified cold/depleted/native/declared-guest cases keep DEBT-083 active. |

Source of authority: approved Functional Design under this unit and
`dashboard-operator-ui/nfr-requirements/bounded-data-loading/nfr-requirements.md`.
Formalization does not pre-approve the new budget, failure-isolation or storage
mechanisms. Existing test passes and v62 deployment remain historical evidence.
