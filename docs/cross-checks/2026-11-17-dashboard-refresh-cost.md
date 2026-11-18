# Dashboard refresh-cost cross-check

Bounded slice under DEBT-083; BDL-NFR-02–08, FR-028–032/036/038/042,
US-012/014/020/023. Implementing-agent review only.

| Contract | Evidence | Result |
|---|---|---|
| Exact actual memory admission | Default size walk unchanged; cutoff used only in codec predicate; boundary/exhaustion tests | PASS |
| All codec values and limits preserved | Byte/error parity,242 comparisons,36 new tests | PASS |
| Financial/source payload unchanged | Six identical source/output hashes per query kind | PASS |
| Measured checkpoint rebuild improvement | Activity median3.076233→2.665976s; all trials retained | PASS for isolated probe |
| Regression/static verification |146 targeted,3197 full,Black/Ruff/mypy136 | PASS |
| Same-capacity delivery and process continuity | Source779b60e/Flyv73,183hashes/settings, same image/instance/start ticks through Nov18 late capture | PASS |
| Bounded four-session warm protocol |1627.271215s,325/325 complete,323/323 health; Home/Trading p95 0.628590/0.507615s;12-account natural cycle without errors | PASS for this sample |
| Initial5s readiness | Home complete14.572192s, first incomplete shell7.795116s; one initial pair | FAIL |
| Tail response evidence | Four cycle-overlap responses10.519957–12.306462s plus Trading2.338051s, all retained | OPEN |
| Memory and CPU scope | Guest649.605469MiB, dashboard growth17.582031MiB on2GiB; positive CPU balance, zero sampled throttle increments | Original1GiB/depleted qualification OPEN |
| Evidence and probe lifecycle | Exact start/outcome reconciliation, continuous collection, CPU brackets, all runner stages0, remote cleanup and later local task absence | PASS |

The source optimization does not close DEBT-083. Native/cold/depleted/original
1GiB and tail-latency qualification remain separate; no failed sample is relabeled.
