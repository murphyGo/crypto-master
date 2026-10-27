# Internal entities

Normalized Query remains the coalescing identity. An admitted logical job owns
one Future, one compact generation Event, attempts, admission deadline, ready
time and recovery flag. Metadata is bounded by existing admission capacity.
An exhausted source_changed error is an identity-guarded terminal token protected
within the existing cache-entry bound. Cached payload and its original evaluated
age are separate from job/retry state. No runtime persistence schema changes.
