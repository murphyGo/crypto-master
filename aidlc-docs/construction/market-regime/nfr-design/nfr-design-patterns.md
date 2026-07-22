# NFR Design Patterns: Funding+OI Crowding Filter

## Pure deterministic classifier

The classifier accepts a normalized immutable context, UTC `as_of`, and frozen
policy. It returns a frozen result and performs no I/O. Nearest-rank percentile
selection is implemented once and unit-tested at boundary ranks.

## Fail-open observation adapter

The runtime gate catches provider/classification failures, emits a sanitized
skip event, and returns the unchanged record. Disabled and shadow policies can
never produce a rejection terminal.

## Evidence firewall

Runtime enforcement is separated from operator configuration. A veto-capable
path must consume a validated evidence result tied to replay inputs; absent,
failed, or insufficient evidence cannot be treated as approval.

## Allowlisted event projection

Classification is projected into a fixed event payload. The projection has no
generic exception/raw-response field and serializes Decimal values as strings.

## Bounded work

Funding is sliced to the declared window and OI to the comparison range. The
classifier does not copy the full context into activity events. Runtime context
deduplication remains owned by the existing provider/service.

## Honest UI projection

Dashboard functions are pure readers over specific event types. They preserve
`unavailable`/skip states and label observation-only results explicitly.
