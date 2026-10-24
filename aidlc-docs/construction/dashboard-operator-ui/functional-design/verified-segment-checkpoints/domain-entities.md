# Domain Entities: Verified Segment Checkpoints

| Entity | Responsibility / identity |
|---|---|
| Source set | Current eligible members under existing retention, root and selection rules; directory membership is part of verification. |
| Source generation | File identity, captured length and nanosecond modification version, with source-relative record offsets. A changed generation is rebuilt in full. |
| Projection contract | Canonical model/reducer compatibility plus normalized query root, source, scope, mode/accounts and time-window semantics. |
| Segment checkpoint | Complete validated reduction for one whole file generation, its contract, integrity and coverage; bounded, disposable and outside canonical stores. |
| Merge state | Exact process-bounded cycle counters/ties, rejection-companion joins, latest/detail ranks, window descriptors and applicable aggregate state. Never a list of all rich source rows. |
| Publication | Immutable complete result only after full source proof, with source coverage and evaluation time separate from checkpoint age. |
| Checkpoint miss | Missing, changed, incompatible, corrupt or over-capacity acceleration; may recover by canonical bounded reading. |
| Coverage failure | Required source or exact-state proof unavailable; explicit incomplete result with independent verified siblings preserved. |

Checkpoint format, physical path, quotas and atomic publication belong to the
next NFR/infrastructure design. No durable trading-domain entity is added.
