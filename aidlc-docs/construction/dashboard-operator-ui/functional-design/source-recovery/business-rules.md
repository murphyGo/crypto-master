# Recovery rules

1. Three attempts total; admission monotonic time never resets on rerender,
   error TTL, queue rotation or subsequent attempt.
2. Backoff is 0.25 then 0.5 seconds; the sole worker selects ready siblings
   instead of sleeping inside a delayed job.
3. No attempt skips generation checks, resets stale age, pins old siblings as
   complete or changes canonical output/window semantics.
4. Retain one shared Future/Event until final settlement; terminal callbacks
   compare exact identity and cannot clear a newer failure or other query.
5. Protect exhausted tokens from automatic eviction. Reserve terminal capacity
   for admitted work. At finite capacity, reject new admission explicitly.
6. Close and iterator cleanup failures must settle all affected waits safely;
   no replacement worker or per-session retry loops.
7. Recovery time is checked cooperatively. Blocking IO cannot be preempted,
   and no hard thirty-second wall-time promise is made.
