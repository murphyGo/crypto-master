# Streaming Safety Input Entities

| Entity | Role |
|---|---|
| Safety evaluation | One explicit UTC snapshot time, source coverage/age and optional replay extras; distinct from presentation time. |
| Source event stream | Canonical retained ActivityEvent records in source order, one rich model at a time. |
| Safety inputs | Existing counter/drawdown fields with identical fixed-time meanings. |
| Live kill condition | Exact existing cycle/gate/account identity, with advisory exclusion; never an approximate count. |
| Safety result | Existing score, band and factors consumed by notifications and configured pause gate. |
| Read failure | Explicit unavailable/exhausted evaluation; never SAFE/zero fallback and never a new execution permission. |

Physical buffering, quotas, coverage/version verification and failure integration
belong to NFR design. No canonical writer or persistent domain fact is added.
