# Session: DEBT-064 + DEBT-066 close-out — runtime-reconciliation aux signals + in-memory mark-price cache

## Unit

- `runtime-reconciliation` (primary — `OpenTradeClassification.is_stale`
  auxiliary signal + `compute_closed_but_malformed_count` sweep +
  `compute_health_report` aux-signal surfacing)
- Secondary unit: `proposal-runtime` (cap-blocker consumer of the new
  mark-price cache — `_build_cap_blocker_payload` switches from
  `unrealized_pnl_percent=None` fallback to cache-read when fresh)

## Related Requirements

- FR-010: Trading engine open-trade ledger integrity — closest match for
  DEBT-064. The `is_stale` aux signal + `compute_closed_but_malformed_count`
  sweep both extend the existing ledger-integrity contract surfaced by
  `compute_health_report` without altering the `_load_open_trade_rows`
  open-row filter. Half-closed rows (the
  `close_unrecoverable_paper_trades` partial-failure shape — `status="closed"`
  with `exit_price IS NULL` or `exit_time IS NULL`) now have a health-report
  signal where they previously had none.
- FR-014: Store proposal history and outcomes — adjacent to DEBT-066. The
  mark-price cache surfaces a proposal-rejection diagnostic field
  (`unrealized_pnl_percent` on cap-blocker payloads) that R2 of the
  `proposal-funnel-audit` cycle had nulled out for hot-path latency
  reasons.
- NFR-007: Paper trade ledger integrity — same FR-010 surface viewed from
  the persistence contract side; the `closed_but_malformed_count` sweep
  closes the silent-corruption gap on partial-failure writes.
- FR-013: Generate trading proposals — adjacent to DEBT-066's
  cap-blocker consumer site; the diagnostic field restoration helps
  operators triage "is the blocking position underwater?" without
  forcing the dashboard / manual ticker lookup.

## Scope

Bundled DEBT-064 + DEBT-066 — both filed 2026-05-13 as Low-priority
runtime-reconciliation quant-review follow-ups (DEBT-064 surfaced from
quant-trader-expert Q1 during `runtime-reconciliation` unit close-out;
DEBT-066 surfaced from quant-trader-expert Q1 during
`proposal-funnel-audit` unit close-out). Both items independently shipped
the suggested-resolution verbatim — auxiliary signals on the existing
classifier output for DEBT-064 (not new enum states), and an in-memory
`dict[str, MarkPriceEntry]` cache populated at existing ticker-fetch
sites for DEBT-066 (zero new exchange calls).

- **DEBT-064 (runtime-reconciliation taxonomy aux signals)** — added
  `OpenTradeClassification.is_stale: bool = False` as an auxiliary signal
  independent of `state` (an `unrecoverable` row can also be stale).
  `DEFAULT_STALE_THRESHOLD_SECONDS = 7 * 24 * 3600` (7 days, configurable
  per-call). `classify_open_trade` gains optional `now` +
  `stale_threshold_seconds` kwargs. `_row_is_stale` uses `entry_time` as
  the `last_seen_at` fallback — a conservative lower bound, since
  `TradeHistory` has no `last_seen_at` field today and adding one is out
  of scope for this cycle. New `compute_closed_but_malformed_count(data_dir,
  sub_account_id) -> int` sweep iterates `status="closed"` rows with
  `exit_price IS NULL` or `exit_time IS NULL` and does not touch the
  existing `_load_open_trade_rows` open-row filter. `compute_health_report`
  surfaces both `stale_count` + `closed_but_malformed_count` per-sub-account
  and at totals level. Pinned by 10 new tests in
  `tests/test_runtime_reconciliation.py`.
- **DEBT-066 (in-memory mark-price cache)** — added `MarkPriceEntry`
  frozen dataclass (`price: Decimal`, `observed_at: datetime`) and
  `TradingEngine._mark_price_cache: dict[str, MarkPriceEntry]` instance
  attr next to `_market_regime_cache`. `_remember_mark_price(symbol,
  price)` write-through + `_get_cached_mark_price(symbol, *,
  max_age_seconds=300.0)` read with freshness gate. Populated at 3
  existing ticker-fetch sites — `_monitor` SL/TP path at L3243,
  `_monitor` orphan force-close path at L3147, and
  `_record_portfolio_snapshot` at L3431 — **zero new exchange calls**.
  `_build_cap_blocker_payload` consumes from the cache: long
  `(mark - entry)/entry × 100`, short `(entry - mark)/entry × 100`
  (matches `pnl_for_trade` sign convention). Cache-miss `None` fallback
  preserved as regression-safe behavior for the prior DEBT-066-pre-fix
  contract. Pinned by 7 net new tests in `tests/test_runtime_engine.py`
  (1 existing test renamed/refit, 6 new added).

## Changes

- `src/runtime/reconciliation.py` —
  `OpenTradeClassification.is_stale: bool = False` aux signal added;
  `DEFAULT_STALE_THRESHOLD_SECONDS = 7 * 24 * 3600` module constant;
  `classify_open_trade` gains optional `now` +
  `stale_threshold_seconds` kwargs; `_row_is_stale` uses `entry_time` as
  `last_seen_at` fallback (conservative lower bound — documented
  in-code); new `compute_closed_but_malformed_count(data_dir,
  sub_account_id) -> int` sweep over `status="closed"` rows with
  `exit_price IS NULL` or `exit_time IS NULL`; `compute_health_report`
  surfaces `stale_count` + `closed_but_malformed_count` per-account +
  totals. Existing `_load_open_trade_rows` open-row filter intentionally
  untouched.
- `src/runtime/engine.py` — `MarkPriceEntry` frozen dataclass;
  `TradingEngine._mark_price_cache: dict[str, MarkPriceEntry]`
  instance attr next to `_market_regime_cache`;
  `_remember_mark_price(symbol, price)` write-through;
  `_get_cached_mark_price(symbol, *, max_age_seconds=300.0)` read with
  freshness gate; populated at 3 existing ticker-fetch sites
  (`_monitor` SL/TP at L3243, `_monitor` orphan force-close at L3147,
  `_record_portfolio_snapshot` at L3431); `_build_cap_blocker_payload`
  consumes from the cache with long/short sign convention matching
  `pnl_for_trade`; cache-miss `None` fallback preserved.
- `tests/test_runtime_reconciliation.py` — +10 tests pinning DEBT-064
  (positive/negative stale cases at the 7-day boundary, custom
  threshold override, missing `entry_time` fallback to
  `is_stale=False`, both null-branch closed-malformed cases —
  `exit_price IS NULL` and `exit_time IS NULL` — end-to-end
  `compute_health_report` aux-signals at per-account + totals level).
- `tests/test_runtime_engine.py` — +7 net new tests pinning DEBT-066
  (1 existing test renamed/refit + 6 new): cache population at each of
  the 3 ticker-fetch sites, fresh/stale read across the freshness gate,
  cache consumption inside `_build_cap_blocker_payload`, short-side
  sign convention, cache-miss `None` fallback regression-safe.
- `docs/TECH-DEBT.md` — moved DEBT-064 + DEBT-066 from Active to
  Resolved; Statistics Active 4 → 2, Low 2 → 0, Resolved (All Time)
  62 → 64; 2 Change History rows.
- `aidlc-docs/aidlc-state.md` — appended DEBT-064 + DEBT-066 bundled
  close-out note to the `runtime-reconciliation` row; Next Action
  updated to "No remaining runtime-reconciliation follow-ups (DEBT-064
  + DEBT-065 + DEBT-066 all resolved)".

## QA Verdict

🟢 + `mypy src` repo-wide-clean milestone preserved. Both items shipped
the suggested-resolution verbatim — no scope creep, no unrelated edits.
DEBT-064 is a per-row aux-signal addition that consciously falls back
to `entry_time` as the `last_seen_at` proxy (TradeHistory schema
unchanged). DEBT-066 is a 3-site write-through cache populated at
existing ticker-fetch sites with zero new exchange calls. Both items
preserve the prior fallback contracts (cache-miss `None`,
`is_stale=False` on missing `entry_time`) so the change is
strictly-additive.

## Verification

- `pytest -q`
  - Result: 2078 passed (was 2061; net +17 across the two items, zero
    regressions).
- `ruff check src tests`
  - Result: fully clean.
- `mypy src`
  - Result: `Success: no issues found in 88 source files` — **repo-wide
    clean milestone preserved** (first established by DEBT-067 +
    DEBT-070 bundled close-out earlier in this session; this cycle
    extends the green streak through a 17-test diff plus a new
    `MarkPriceEntry` frozen dataclass + new
    `compute_closed_but_malformed_count` callable).

## Risks

- **`is_stale` uses `entry_time` as the `last_seen_at` proxy.**
  `TradeHistory` does not persist a monitor-touched timestamp today,
  so the aux signal may over-flag rows the monitor loop recently
  touched but whose entry was long ago. This is a conservative
  lower-bound — false positives surface as health-report `stale_count`
  bumps which an operator can investigate; false negatives are
  impossible (anything genuinely stale by `entry_time` is also stale
  by `last_seen_at`). Documented in-code at `_row_is_stale`.
  Persisting a real `last_seen_at` from the monitor loop is a future
  enhancement (see Future Work — not filed as DEBT pending an explicit
  operator ask).
- **Mark-price cache stale entries intentionally retained.** No TTL
  purge — next write to the same symbol overwrites. Memory is bound by
  the traded-symbol universe (typically <50 symbols across all
  sub-accounts). Pruning on symbol-rotation is not currently warranted
  given the bound.

## Milestone Note

`mypy src` remains fully clean repo-wide for the second consecutive
cycle this session: `Success: no issues found in 88 source files`. The
milestone first established by DEBT-067 + DEBT-070 is now preserved
through a 17-test diff plus a new frozen dataclass + new module-level
constant + new public callable + new optional kwargs on an existing
public callable + new `dict[str, MarkPriceEntry]` instance attr — all
strictly-additive surfaces typed in line with the established repo
style. The next regression on `mypy src` is spottable on the next diff.

## Future Work (not filed as new DEBT)

- **Persist `TradeHistory.last_seen_at` from the monitor loop.**
  Currently `is_stale` uses `entry_time` as the conservative
  lower-bound proxy because `TradeHistory` has no `last_seen_at`
  field; a real monitor-touched timestamp would eliminate the
  false-positive surface noted in Risks above. **Explicitly NOT filed
  as DEBT in this cycle** — operators have not asked for it and the
  current conservative-fallback shape is producing actionable signals;
  flagged here only as a candidate follow-up so a future cycle's
  planner has the signal. Would require a schema migration on the
  existing `data/trades/paper/<sub_account>/history.jsonl` ledger and
  one-time backfill (assume the persisted `entry_time` for legacy
  rows).
- **Optional CI gate to lock the repo-wide-clean mypy baseline.**
  Still queued from the prior DEBT-067 + DEBT-070 cycle's session log
  (no progress this cycle, no new motivation either — the milestone is
  now preserved across two consecutive cycles which weakly raises the
  case for an automated lock).
- **Active TECH-DEBT queue now down to 2 items** — both Medium Slice 2
  umbrellas (DEBT-068 `cross-account-risk-policy` Slice 2;
  DEBT-069 `strategy-tuning` Slice 2). Zero Low informational items;
  zero High / Critical open items. The runtime-reconciliation unit
  has no remaining tracked follow-ups.
