# Bounded source-generation recovery

Only `source_changed` receives up to three coalesced builder attempts with a
thirty-second admission-based cooperative budget and 0.25/0.5 s retry delays.
Fresh discovery/full proof are retained. The original Future/Event survives
intermediate attempts; ready siblings can run during backoff. Exhaustion stays
latched until exact manual retry, within bounded terminal metadata capacity.
This intentionally changes v67's passive error-TTL healing after exhaustion.

Source verification: 3,048 full tests in 68.86 s; all 265 source/test/script
hashes unchanged during the final suite; independent 236 tests; five-file
Black/Ruff; mypy all 135 sources. Three real baseline failures are retained.
Actual activity/snapshot mutations match canonical outputs with checkpoints
disabled and explicitly prepared/enabled. Local two-session Streamlit 1.57.0
fragment checks corroborate same-generation progress; deployed/native behavior
requires its own observation.

The synthetic 34-second writer model exhausts at 18.75 s and stays terminal
after stability. It proves finite behavior, not operational success. Do not
claim a hard thirty-second IO deadline or production latency improvement.
Long-lived incomplete pages after quiescence are a rollback consideration.

`developer/`, `qa/`, `full-gate.json` and `source-qualification.json` record
source evidence. `evidence-manifest.json` pins artifact bytes. The sandbox UV
cache-access failure happened before test execution and is retained separately;
the approved rerun passed. Prior operational failures and original qualification
gates remain open. See the construction plan and session/cross-check documents.
