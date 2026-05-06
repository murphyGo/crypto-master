# Implementation Summary: strategy-promotion-lab

This unit starts as a promotion scoring layer over existing feedback-loop,
backtest, and robustness evidence. Source code remains in the workspace root.

Initial implementation target:

- `src/feedback/promotion_lab.py`
- `tests/test_feedback_promotion_lab.py`

The first pass is intentionally side-effect free: it computes a recommendation
from already available candidate evidence. Persistence, dashboard actions, and
operator workflow wiring are tracked as later construction steps.

Observation persistence now lives in `PromotionObservationStore`. It writes
per-candidate JSON snapshots under `<data_dir>/feedback/promotion_lab`, keeps
the first-seen timestamp stable across repeated evaluations, updates the latest
decision/score/factors, and uses the project atomic-write helper.

The Feedback Loop dashboard now loads promotion observations, merges
recommendation and score into the candidates table, and shows the latest
promotion factors/blockers in candidate detail.
