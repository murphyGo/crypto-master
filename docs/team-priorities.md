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

(none)

## Done

(처리된 항목은 여기로 — `[x]` 체크 + 처리 일자 + 한 줄 결론)

- [x] (2026-04-28) Fly 배포에 트레이딩이 0건. 원인 검증 — outcome (verified against `fly logs`, runtime addendum in session log): **(c) 설정 + 아키텍처** — `ProposalEngine._select_best_technique` 가 cold-start 에서 알파벳 순서로 **하나의** strategy 만 선택 → `bollinger_band_reversion` 만 매 cycle 실행 → band-piercing 신호가 거의 안 나와 매번 `neutral` 반환 → proposal 자체가 생성 안 됨 → threshold 게이트는 *도달도 못함*. Cycle-1의 threshold-lockout 가설(`composite ≤ 0.5 vs threshold 1.0`)은 산수상 맞지만 실제 런타임에서는 그 게이트 *위*의 short-circuit 에서 막힘. 다른 strategies (rsi / ma_crossover / chasulang_ict_smc 등) 는 분석 자체를 못 받음. **시정된 fix 경로**: 새 sub-task **Phase 10.6 Multi-Technique Per-Symbol Scan** (모든 applicable strategy 가 매 cycle 실행되도록) 가 primary fix. Phase 10.2 (env override) 는 운영성 측면에서 여전히 유용하지만, 권고했던 `threshold default 1.0 → 0.3` 변경은 이제 의미 없음 (제거할 것). Secondary findings 모두 런타임 검증으로 확정: (i) Fly 이미지에 Phase 9.4 (`rsi_4h`, `rsi_15m`) 미배포 → 재배포 필요, (ii) `ActivityLog` 등이 relative path 라 Fly volume(`/data`)이 아닌 ephemeral `/app/data/` 에 씀 → **Phase 10.5 Volume-Aware Default Paths** 별도 sub-task. 진단 리포트와 retro 는 `docs/sessions/2026-04-28-priorities-fly-zero-trades-diagnosis.md` 의 Runtime Verification Addendum 섹션 참조.
