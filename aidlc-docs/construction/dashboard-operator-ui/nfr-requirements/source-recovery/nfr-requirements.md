# Requirements retained

Reliability: recover only transient changed generations within finite shared
attempt/time bounds; terminal fallback remains visible. Scalability: one worker,
four admissions, bounded error metadata and one watcher. Performance: four-second
foreground, two-second complete freshness, thirty-second stale limit; current
cold/warm page acceptance is unchanged. Security: no credentials/paths/query IDs
in new diagnostics. Integrity: rediscovery and full source checks every attempt.
Usability: existing loading and manual Refresh semantics except the authorized
finite source_changed recovery phase. Original cold/native/depleted/1024 MiB
gates are not relaxed; all prior failures remain.
