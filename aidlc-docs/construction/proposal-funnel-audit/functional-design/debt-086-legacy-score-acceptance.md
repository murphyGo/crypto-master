# DEBT-086: observed score acceptance and legacy unknowns

`gate_rejected_unknown` remains the compatibility bucket for decided records
without a final state. Its historical name does not prove that the score gate
was passed. The raw count and persisted records remain unchanged.

`score_accepted_total` includes explicit score acceptance and known downstream
states, including shadow records, but excludes unknowns. The additive derived
`score_acceptance_unknown_total` reports that missing evidence. The legacy
`gate_rejected_total` still sums every gate-named bucket for compatibility.

Dashboard conversion and home/account summaries use the canonical observed
acceptance total. Generated proposals use `counts.total` once, including scored
and unknown rows, so acceptance is an observed share of all records rather than
an inferred historical pass rate. Unknown count is visible beside observed
acceptance and remains in the raw state table/heatmap. Unknowns are excluded
from the post-acceptance gate rejection chart. Existing opened/fill semantics
are outside this correction.

No schema migration, history rewrite, runtime gate change or deployment is
needed. Tests cover legacy explicit score rejection without final state,
pending legacy rows, all explicit post-score enum states, mixed denominators,
shadow records, all-unknown history and byte-for-byte read-only aggregation.
