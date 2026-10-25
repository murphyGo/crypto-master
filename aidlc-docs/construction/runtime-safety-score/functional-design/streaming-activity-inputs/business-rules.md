# Streaming Safety Input Business Rules

1. Financial/policy formulas, score factors, clipping, bands, penalty weights and
   configured pause thresholds remain unchanged. No exchange/live activation added.
2. A frozen explicit UTC evaluation time defines the same inclusive 24h window;
   its proposed entry-time anchor is an intentional reviewed difference from
   acquiring default time after materialization.
3. Preserve all simple event counters, stale-quote reason/message OR semantics,
   live/advisory filtering, cycle/gate/account fallback and distinct kill-condition
   keys exactly. Source order must not change an order-independent result.
4. Replay extras, duplicates and per-cycle cache rules remain. An explicit empty
   extra list retains its existing cache distinction from `None`.
5. Canonical runtime files, retention and `read_all()` ordering stay intact.
   New iterator consumers explicitly accept source order and close resources.
6. Keep only scalar counters and exact distinct-condition state, not full event
   payload history. Bound state, input and elapsed work in the next NFR stage;
   do not approximate counts when capacity is exhausted.
7. Fail incomplete hard reads explicitly through the existing guarded path; no
   fabricated healthy score or acceptance based on incomplete inputs. Preserve
   legacy malformed-row skip/warning behavior unless separately reviewed.
8. Proposed UTC anchoring, new bounded-failure behavior and live pause interaction
   require functional/NFR review and negative tests before source/rollout changes.
