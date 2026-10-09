# DEBT-078 persistence and compatibility design

The trade-history tracker owns atomic recovery and acknowledgement updates. Paper/live rehydration records recovered bounds with pending=true, and exposes an optional monitor acknowledgement hook. Existing/custom Trader implementations keep working through capability detection. When persistence raises OSError, log and continue current exit/time-stop behavior; an unacknowledged row remains conservative on restart. The monitor does not read reverse performance links to decide provenance.

Proposal repair re-reads the ledger and marks only rows whose bounds are still missing at write time, preserving concurrently completed normal bounds. Dry-run tools write neither bounds nor provenance. Existing tests cover live exchange calls; new cases use mocked exchanges and temporary ledgers. No live runtime data or infrastructure change is part of validation.
