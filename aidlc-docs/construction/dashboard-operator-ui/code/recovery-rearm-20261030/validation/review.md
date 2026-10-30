# Recovery rearming source review

No additional correctness defect found in the reviewed change. This is a
review by the implementing agent using `.agents/skills/code-review/SKILL.md`,
not an independent-agent review. Scope: source commit `ffe95b0` versus its parent,
the recovery tests and availability/progress integration.

- `data_service.py:111`: a token is checked under the same condition as admission;
  the eligibility boundary permits one job, and concurrent callers reuse its
  Future/event. Fresh compatible results retain their original precedence.
- `data_service.py:163`: an expired same-query token releases its reserved slot;
  the combined active/error bound remains enforced. Other unexpired source tokens
  cannot be evicted to evade the cooldown. Existing ordinary-error eviction stays.
- `data_service.py:266`: manual retry compares token identity, not dataclass value
  equality. An older callback cannot erase a newer equal-valued token or job.
- `data_service.py:462`: failure eligibility is no earlier than the original
  window or the minimum error cooldown. Settlement closes the finite Future and
  its page signal; no timer or extra worker starts another episode. Source proof,
  cache age, capacity and first-attempt cooperative behavior remain unchanged.
- `observe_dashboard_protocol.py:225`: timeout remains an outcome. The old socket
  closes before a replacement opens, and elapsed time starts before reconnect.
  The outer runner stops on connection errors/cancellation; these are retained
  by the existing outcome/finally path rather than silently retried.

Residual risks remain explicit under DEBT-083: no automatic recovery for an idle
terminal page, transient incomplete pages during a long write wave, no general
server run-ID join in the observer, production dependency versions differ from
the locked local environment, and initial/native/depleted/original1GiB latency
and resource qualification are independent of the passing source tests.
