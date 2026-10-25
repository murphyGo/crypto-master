# Proposed Amendment: Safety Read Failure Isolation

**Status:** New functional delta proposed during NFR review; not implemented or
covered by the earlier base streaming/time approval. Approve with the concrete
NFR candidate before Code Generation.

## Verified current flow

`run_cycle` wraps scan, all proposal handling, position monitoring and snapshot
recording for one account in one broad try. A safety-input exception inside a
proposal currently reaches that guard and skips that account's remaining
proposals **and its monitor/snapshot**. Later accounts continue. Adding bounded
read failures without considering this would make the monitor gap more common.

## Selected proposed failure flow

Catch only the new typed safety-read-unavailable failure at the proposal-loop
boundary, before any new order from that proposal. Record the existing account
error/CYCLE_ERRORED with a stable reason, stop that account's remaining proposal
loop, then execute the account's existing position monitor and snapshot exactly
once. Later accounts retain the current isolation behavior. An ordinary monitor,
scan or exchange error still uses the existing outer guard. Actual task
cancellation is not converted into a recoverable safety error.

| Case | Proposed result |
|---|---|
| Complete valid safety inputs | Existing score, configured pause threshold, notification, order, monitor and snapshot sequence unchanged. |
| Typed input failure before notification | No opportunity notification or new order on this failed path; account error recorded; remaining account proposals stop; existing monitor/snapshot continue. |
| Typed input failure at post-incident pause check | Keep any already delivered notification and persisted proposal state as today. Do not invent a rejection/fill, retry an order or duplicate a notification. Record failure, stop remaining proposals, run monitor/snapshot. |
| Read slot busy / timeout / cap / changed source | Same typed failure flow; never use an old complete score to admit an explicit-extra request. |
| Monitor/snapshot themselves fail | Existing outer error handling; no second monitor invocation or automatic data repair. |
| Normal `stop()` versus task cancellation | Keep current stop-finishes-cycle semantics. Cancellation/teardown closes the reader cooperatively; no new trading action is introduced. |

This intentionally restores existing position-management work on a newly typed
read-failure path where the old broad guard skipped it. It does not change SL/TP
criteria, timing configuration, position size, live confirmation or score weights.
It can cause normal protective closes that the old exception path would skip;
that is an explicit behavior difference requiring review, not a hidden refactor.

## Safety checks required before rollout

Both safety-call sites must precede order execution. Test failed reads with pause
configured/enabled/disabled in paper/live, no new open/fill/duplicate notification,
unchanged persisted pre-error state, one monitor/snapshot on the failed account,
later-account continuity, independent monitor failure and actual cancellation.
Do not attach the worker's source/payload traceback to long-lived cycle errors.
