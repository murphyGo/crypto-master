# Verified Segment Checkpoints: Functional Design Plan

- **Unit / stage:** `dashboard-operator-ui` / Functional Design (proposed change to restart/persistence contract).
- **Requirements / stories:** FR-029/031/032/036/042, NFR-003/007/008/011/012, BDL-NFR-01..08; US-012/014/020/023.
- **Debt / history:** DEBT-083 Critical/active; legacy Phase 7/8.2/10.4/19.3.
- **Context:** v61 / `7f185bc` retains shared CPU 1 / 2048 MiB. Million empty-service cold p95 7.872s fails 5s. Five-second four-session stress fails a health deadline after 210s. Native Browser unavailable. Twenty-second navigation qualification is separate and in progress.
- **Authorization:** Continue remaining improvement/documentation. CPU/cost proposal remains deferred. The presented base derived-persistence contract is approved for NFR continuation; its NFR mechanics are not approved or activated.

## Steps

1. [x] Analyze actual remaining latency, source/digest behavior, canonical writer and current read-only/restart contracts.
2. [x] Evaluate all functional question categories and preserve existing business rules; record concrete candidate choices below.
3. [x] Write business-logic-model, business-rules, domain-entities and frontend-components under `functional-design/verified-segment-checkpoints/`.
4. [x] Obtain explicit approval of this new functional contract before advancing it to NFR/infrastructure design.
5. [x] After approval, specify/approve physical encoding, disk/memory quotas, crash/source proofs and qualification before implementation. No candidate storage write occurs in this stage.

## Question coverage / candidate choices

These choices describe the concrete design for review; they are not recorded as operator approvals.

- **Business logic:** [Answer]: Exact file-generation reductions merge into the existing complete read model; financial definitions/periods stay unchanged.
- **Domain model:** [Answer]: Add disposable derived checkpoints and their compatibility/coverage identity; add no trading fact.
- **Rules:** [Answer]: Every changed file validates in full; no size-only append optimization or approximate counters.
- **Data flow / persistence:** [Answer]: Propose a separately bounded derived namespace on the existing volume; original files remain untouched. Candidate disk ceiling 64 MiB needs NFR design; process limits remain unchanged.
- **Integration:** [Answer]: Existing data service/reader only; no new external service, exchange, credentials or CPU class.
- **Error handling:** [Answer]: Corrupt/incompatible/absent checkpoint falls back to canonical bounded reading; incomplete required coverage remains explicit.
- **Scenarios:** [Answer]: Unseeded bootstrap, process restart, mutable file replacement/truncation, rollover, cross-file cycles/companions, UTC ties and window expiry all need separate evidence.
- **Frontend:** [Answer]: Existing controls/statuses and independent siblings; no storage controls/details in the operator flow.
- **Approval:** [Answer]: Operator `나머지도 계속 진행해줘` continues both presented remaining functional candidates into NFR design. New physical budgets/failure rules still need their own concrete review; no storage/code change is activated.

## Completion

- [x] Concrete reviewable artifacts prepared
- [x] Functional contract approved and approval recorded
- [x] NFR/infrastructure stage completed before source changes
- [ ] Implementation and all original acceptance verified before DEBT-083 closure

## Approval checkpoint

- Exact continuation: `나머지도 계속 진행해줘`.
- Context: assistant explicitly reported incomplete acceptance and pending follow-up designs.
- Scope: approve the already-presented base Functional Design and continue NFR formalization/design; CPU/cost deferral and existing capacity remain.
- New numeric budgets and any failure-flow amendment are not pre-approved.
- Recorded at: 2026-10-25T11:21:35.006589+00:00 (record time, not message timestamp).
