# Initial snapshot read cost — NFR amendment, 2026-11-11

DEBT-083; dashboard-operator-ui with persistence-data-integrity. Existing
BDL-NFR-02–08, FR-028–032/036/038/042 and US-012/014/020/023 stay unchanged.
Functional and infrastructure stages are not reopened: complete data, error
states, freshness, scheduling and deployment settings have no new semantics.

[Answer]: The user's “진행시켜” continues the remaining initial-latency task.
The measured parser optimization is a routine implementation choice under the
existing approved bounded-reading design. Preserve validation/proof/budgets and
same-capacity delivery; do not request a new product or cost decision.

## Evidence and selected change

Current v71 direct initial snapshot projection reads 13 files,37,038,485 bytes
and98,830 snapshots in3.854591s wall/3.825856s CPU. A separate cProfile run
attributes8.484s of11.364s instrumented time to json_array_bytes, including
4,330,745 regex searches. Identical output hashes and source coverage verify
that the two trials read the same generation. Profiling overhead is not latency.
Activity takes4.771s wall/2.663s CPU; its different contention and reducer work
are separate from this parser optimization.

1. Recognize complete **unescaped** JSON strings with one bounded C regex token.
   Escaped strings and strings crossing read blocks retain the current explicit
   quote/escape state machine. Avoid repeated/nested regex groups and unbounded
   search buffers. No grammar/schema validation moves out of the decoder.
2. Track a span in each fixed-size input block and copy it only when an object
   ends or crosses a block. An object wholly inside one block needs one slice,
   instead of extending a bytearray for every structural token. Accumulated
   record bytes are checked before copying, with the same record_bytes limit.
3. Preserve block-level cooperative yields, iterator close/file release, captured
   prefix checks, final generation checks, array separators/trailing content and
   downstream full JSON/Pydantic validation of every historical row. No row is
   skipped and latest/tie/equity sampling rules stay unchanged.
4. No persistent cache format, cache identity, retention, dependency or process is
   added. Existing block/record/state/cache caps remain. The all-source checkpoint
   digest naturally invalidates old cache prefixes after source deployment.

## Required verification

Differential raw-record and error tests against the frozen baseline; deterministic
valid nested/Unicode/escape inputs across block sizes; corrupt old rows, malformed
arrays, exact/oversized record limits, append/replacement/truncation and close at
cooperative boundaries. Retain exact snapshot projection parity, not just counts.
Benchmark representative many-small-row and long/escaped-record shapes with warm
imports/OS declared, alternating baseline/candidate on fixed immutable inputs.
Measure transient memory as well as runtime; no timing threshold in unit tests.

Then run bounded-reader/dashboard/history targeted tests, full pytest, changed-file
Black/Ruff, full mypy and implementing-agent review. Same-capacity deployment needs
exact source/image/configuration proof and ordinary engine health. Measure complete
Home/Trading readiness and retain every failure; parser speed alone cannot close
the original native/cold/depleted/1GiB/four-session qualification gates.
