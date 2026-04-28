# Team Priority Queue

User-driven ad-hoc tasks. The `team-lead` reads this file at the start of every cycle and processes open items **before** falling back to the dev plan / TECH-DEBT / cross-check scan.

## How to use

1. Add a one-line summary to the **Open** list as `- [ ] <summary>`.
2. (Optional) Indent a sub-bullet with file pointers, expected output, or "stop when X" criteria.
3. Run `/team` (or `/loop /team` for autonomous iteration). The lead picks the first unchecked item, dispatches the appropriate specialists, and the `docs-auditor` flips the box to `[x]` after the work lands and moves the item to **Done** with a one-line outcome.

When **Open** is empty, the team falls back to its normal scan.

## Item format

```
- [ ] One-line summary in active voice.
  - (optional) Background / file pointers / expected output.
  - (optional) Stop criteria — when do we consider this resolved?
```

Keep summaries imperative ("Verify…", "Investigate…", "Wire…"). The lead may decline an item if it conflicts with a higher-priority gate (live-credentials, deployment, phase boundary) — in that case it surfaces a question to the user instead of processing.

## Open

- [ ] Fly 배포에 트레이딩이 0건. 원인 검증 — `data/runtime/activity.jsonl` 의 cycle / proposal / decision / open / close 이벤트 패턴, `EngineConfig`의 auto-approve threshold + symbol list, ProposalEngine 의 score 분포를 보고 결론을 내려달라. 결론은 셋 중 하나여야 함:
  - (a) 정상 무거래 — 시장이 threshold를 못 넘었음, 시스템은 정상.
  - (b) 버그 — score 계산 / 필터 / 발주 경로에 결함.
  - (c) 설정 — threshold 너무 높음 / symbol list 비었음 / 키 미설정 / 스케줄 안 도는 등.
  - 산출물: 1페이지 진단 리포트 + (b)/(c)면 수정 PR을 띄울 sub-task 제안.

## Done

(처리된 항목은 여기로 — `[x]` 체크 + 처리 일자 + 한 줄 결론)
