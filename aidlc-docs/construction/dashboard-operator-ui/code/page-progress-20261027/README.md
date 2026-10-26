# Page-dependent recovery correction — 2026-10-27 KST

The reproduced defect is the watcher condition: a page waited for the entire
process queue to drain, even after its own result or admission opportunity was
ready. Earlier watcher-count assertions did not cover unrelated work remaining
active. The new regression reproduces both delayed cases on the baseline and
then verifies the correction with the same behavioral assertions.

Production changes are limited to `availability.py`, `data_service.py` and
`read_models.py`. Compact generation signals identify completed attempts without
retaining their Future/payload; queue-capacity checks are read-only and weakly
reference the service. Each render has a bounded set of signals and its own
one-shot rerun latch. Freshness, full source verification, worker/admission
limits, explicit terminal retry and trading behavior are preserved.

`developer-red.txt` retains the two baseline behavioral failures.
`developer-verification.json` and `qa-source-verdict.json` retain initial focused
source checks. `qa-fragment-smoke-result.json` exercises real local Streamlit
fragment closures for two sessions, including actual reruns and ignored repeated
old closures while unrelated work remains active. It is not native/timer evidence.

The first full regression run found three old bounded-page mocks that accepted
only the former one-argument call. The `*-initial` artifacts retain that failed
iteration; the two `*-page-fixture-followup.json` records document the single
optional-argument mock correction with all existing assertions preserved.
Production source hashes did not change. Final source qualification is stored
separately after the full rerun; do not use the initial failed run as a pass.

The prior v65 116/120 result and all older failures remain valid observations.
This correction addresses the reproduced page dependency bug; it does not
attribute every historical timeout to that bug or change the original cold,
native, depleted-CPU or 1024 MiB acceptance criteria.
