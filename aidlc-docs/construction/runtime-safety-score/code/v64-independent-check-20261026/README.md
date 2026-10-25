# Independent v64 verification

Adopted source: `dca38fbf25a9b96ec91400b628bc71513cf3357d`, Fly v64.

- `operational.json`: direct 180-file hash comparison, dependency/configuration,
  internal/public health, first completed cycle and separate prior strategy
  evidence replay. Captured 2026-10-25T17:41:02Z. No runtime write was performed.
- `source-validation.json`: independent tests/type/format checks for the adopted
  source. The alternative branch's 3,008-test count does not apply here.
- `origin_compare_result.json`: independent 184-case helper parity, exact
  adopted/candidate distinction and parser-edge reproduction. Candidate 8053ae0
  remains archived and unmerged; its earlier parity review is superseded for
  the broad JSON ValueError handling edge.

The first cycle emitted no proposal, so it does not prove natural safety-gate
execution. No original dashboard/native/depleted/guest acceptance is inferred.
See the [session](../../../../../docs/sessions/2026-10-26-runtime-safety-v64-independent-verification.md).
