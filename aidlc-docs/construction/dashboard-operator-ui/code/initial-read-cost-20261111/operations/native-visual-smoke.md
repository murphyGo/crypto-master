# Native visual smoke — v72, 2026-11-11

Read-only checks used the installed `/Applications/Google Chrome.app` through
the computer-use accessibility and screenshot APIs before the four-session
protocol observation started at 07:15:26 UTC. Browser-host discovery was
unavailable; native app control succeeded. One task-owned tab was opened at
`https://crypto-master.fly.dev/`, navigated with the visible Trading link, and
closed after inspection. No operator controls or trading actions were used.

- Home: Paper/Aggregate selected; rendered command-center metrics and diagnostic
  table. Last cycle `ok`, snapshot `fresh`, 12 open positions and 13 sub-accounts.
  Runtime safety was `degraded` (70/100), with 29 correlation warnings shown as
  its factor. This domain warning was visible, not a rendering failure or an
  assertion that trading risk is absent.
- Trading: summary metrics, active-position and recent-history tables rendered.
  Scrolling showed the equity chart, axes and strategy legend. Reconciliation
  reported seven open trades, all monitorable. Some active-position current-price
  and P&L cells displayed `None`; this smoke does not certify cell-level financial
  semantics or reconciliation/aggregate equivalence.
- No incomplete-read alert or exception was visible in the inspected views.
  The initial Trading navigation briefly displayed the normal Running shell,
  followed by populated content on the next observation.

This is one visual smoke, with screenshots inspected in the tool conversation.
It is not a timed native p95 test, a process-cold experiment, an all-row data
oracle, or original 1 GiB qualification. The following protocol warmup occurs
after these views and must not be called a cold-load measurement. Browser chrome
and unrelated user tabs were not copied into repository artifacts.
