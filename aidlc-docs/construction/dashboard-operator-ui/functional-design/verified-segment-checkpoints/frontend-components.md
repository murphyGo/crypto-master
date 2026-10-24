# Frontend Contract: Verified Segment Checkpoints

Home/Trading keep their current controls, metrics, tables, charts and period
labels. Pages request projections through the process-owned data service;
individual sessions do not write checkpoints or start readers of their own.

Required data displays meaningful values only after complete coverage. During
bootstrap or rebuilding, the existing explicit loading/unavailable/stale states
and independently verified sibling sections remain available. A fast shell,
health response, old complete checkpoint or sampled curve does not count as
complete current data. Source/evaluation timestamps retain their meanings.

No cache-management control, raw file path, storage implementation detail,
exchange action or live-mode activation is added to the product flow. Native
viewport inspection and four-session page/memory qualification still apply.
