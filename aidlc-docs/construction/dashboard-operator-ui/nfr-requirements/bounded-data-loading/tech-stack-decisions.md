# Tech Stack Decisions: Bounded Dashboard Data Loading

**Status:** Requirements baseline approved; proposed implementation choices
are reviewed with NFR Design. No dependency or runtime store is changed.

| Concern | Proposed choice | Reason / boundary |
|---------|-----------------|-------------------|
| Application/UI | Existing Python and Streamlit | Preserve current navigation, operator controls and pure read-model seams. |
| Input | Existing monthly/legacy JSONL, proposal JSON files and trade/snapshot arrays | Original stores remain authoritative and unchanged. |
| IO primitives | Stdlib bounded binary reads, incremental UTF-8 decoding and JSON parsing, `os.scandir`/file descriptors | Avoid full-file strings, path lists and prefiltered rich-record arrays. Parser edge cases require tests before use. |
| Validation | Existing Pydantic models plus frozen/immutable result metadata | Validate one relevant record at a time; preserve legacy Decimal/UTC behavior and full semantic parity. |
| Aggregation | Streaming compact reducers and bounded top-k detail | Keep aggregate meaning separate from display limits; capacity exhaustion is explicit. |
| Cache | One locked process-owned service, bounded encoded result buffers | No per-session archive copy; bytes, entries, source generations and reducer state have independent caps. |
| Concurrency | One IO/reducer worker, bounded admission and same-query coalescing | One slow reader cannot multiply into four simultaneous archive scans. Worker code never calls Streamlit rendering functions. |
| Coordination/time | Stdlib locks/conditions/futures and monotonic deadlines | Keep worker lifetime within the existing dashboard process. Cooperative cancellation has stated limitations. |
| Presentation | Existing pandas/Streamlit helpers over bounded projections | Preserve complete-data values; annotate stale/partial coverage rather than fabricating healthy empty results. |
| Qualification | Existing pytest/AppTest and isolated stdlib resource/timing instrumentation | Local docs validation is separate from candidate performance and native runtime evidence. |

Redis, an external queue, a new database, persistent sidecars, retention changes
and engine-side projection writes are not selected. A durable index would
introduce schema/update/bootstrap correctness and operational work; revisit
through explicit design if the qualified cold targets cannot be met. Adding
memory alone does not satisfy the bounded-query requirement.

The earlier deployed/local Streamlit 1.65.0/1.57.0 mismatch is qualification
context, not a proven incident cause. Record exact candidate/runtime versions;
do not claim local AppTest success proves the deployed WebSocket/client path.
Dependency reproducibility and the concurrent DEBT-082 image repair remain
separate from this design's source/reader scope.
