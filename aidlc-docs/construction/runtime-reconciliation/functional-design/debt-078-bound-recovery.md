# DEBT-078 bound recovery lifecycle

## Entities and rules

Add `TradeHistory.bounds_recovery_pending: bool = False`. Only a real missing-bound repair sets it: paper/live performance-linked rehydration, the performance-bound tool, or the proposal-bound repair tool. Persist recovered bounds together with the pending marker. Normal entry records and old rows with already-persisted bounds default false; a null performance_record_id conveys no repair information.

For SL/TP triggers at age >=24h, relabel only a pending recovered row or a row whose persisted bounds are still missing. A normal 26h position with valid bounds keeps the true trigger even with no reverse link. A successful non-breaching bound check acknowledges pending recovery and clears the marker persistently; a later trigger or restart therefore retains normal SL/TP attribution. A young repaired position that immediately breaches retains the normal reason. Other close reasons, price selection, SL/TP ordering, quantity, fees and PnL are unchanged.

Old repaired rows without explicit provenance cannot be retroactively distinguished from normal rows; this correction does not infer or migrate their history. No production repair tool is run in this task.
