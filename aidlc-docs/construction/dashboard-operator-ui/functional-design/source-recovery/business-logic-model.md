# Source-generation recovery flow

A normalized read admits one shared logical job. All clients hold compact
progress for that same generation. A verified payload may complete only after
ordinary full discovery/read/source verification and normal budgets.

Only source_changed enters finite transient recovery: discard the unsuccessful
iterator/state, keep the original Future/Event and admission, then reschedule
behind ready siblings. Rebuild with fresh discovery; never reuse failed partial
output. While work remains, use existing rebuild_pending availability so one
watcher waits for final settlement. A successful verified publication clears
matching error state and records its actual completion age.

After three total attempts or the original thirty-second recovery window,
source_changed becomes a latched terminal outcome. Preserve any old payload's
age and stale/unavailable classification. Exact-generation manual Refresh may
clear that latch. Corruption, resource limits and cleanup faults stay terminal.
This is the user-authorized exception to the previous explicit-only retry
policy in home-recovery/page-progress designs; no other error is auto-retried.
