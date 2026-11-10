# DEBT-090 resilience amendment — 2026-10-30

[Answer]: Use a bounded in-process registry, monotonic expiry and no automatic
adapter retries. No new process, service, dependency, credential or Fly capacity.

- At most 64 active scope deadlines, protected by a short synchronous lock; never
  hold it across I/O. Prune expired entries. If full, an unknown scope fails closed
  rather than evicting an active deadline. State contains scope identifiers and
  deadline numbers only. Process restart loses memory; existing CCXT pacing still
  applies, and this repair does not claim persistent or distributed IP enforcement.
- Read only Retry-After (seconds or HTTP date) from newly replaced CCXT response
  headers and the Binance `banned until <milliseconds>` marker from a bounded
  exception string. Reject nonpositive/nonfinite/invalid values. Prefer the largest
  valid hint; otherwise use 60 seconds for RateLimitExceeded and 120 seconds for
  DDoSProtection. Do not reuse pre-request stale headers. Convert wall-clock dates
  to durations once, then retain a monotonic deadline that can only be extended.
- No adapter sleeps/retries. Derivative callers retain their existing retry count,
  request budget and total refresh deadline, with retry-after metadata preventing
  immediate retry into a known ban. Every history-page invocation is guarded.
- Tests inject CCXT failures without network: all methods, both venues, all network
  subclasses, header/date/deadline parsing, concurrent calls, expiry/extension,
  reconnect/new-instance persistence, scope separation, capacity and cancellation.
  Engine integration must prove monitor attempts/account continuation and no orders
  when fresh prices are absent. Preserve all existing safety regression tests.
- Delivery uses an overlay on the verified v70 image with only changed runtime
  files. Same machine, CPU, memory, volume and settings; exact source hashes and
  health before/after, then observe a natural cycle. No deliberate exchange failures
  or extra market-data probes in production. Absence of a real ban cannot prove the
  fault branch; report injected-test and operational evidence separately.

Primary protocol reference: Binance USD-M general info
<https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/general-info>
(reviewed 2026-10-30: 429 rate limit, 418 IP ban, millisecond timestamps).
