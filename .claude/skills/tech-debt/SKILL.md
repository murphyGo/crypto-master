# Tech Debt Skill

기술 부채 대시보드를 표시하고 부채 항목을 관리합니다.

## Arguments

- `$ARGUMENTS` - 다음 중 하나:
  - (비어있음) 또는 `all` - 전체 대시보드 표시
  - `critical`, `high`, `medium`, `low` - 우선순위로 필터
  - `category:<name>` - 카테고리로 필터 (예: `category:security`)
  - `aged` - 에스컬레이션 임계값 초과 항목 표시
  - `promote DEBT-NNN` - 특정 부채 항목을 개발 계획으로 승격
  - `promote auto` - 에스컬레이션 기준에 따라 자동 선택 및 승격

## Objective

기술 부채의 종합적인 뷰를 제공하고 부채 항목을 개발 태스크로 승격할 수 있게 합니다.

---

## Execution Steps

### Step 1: 인자 파싱

| 인자 | 모드 |
|------|------|
| (비어있음), `all` | 대시보드 모드 |
| `critical`, `high`, `medium`, `low` | 필터 모드 |
| `category:<name>` | 필터 모드 |
| `aged` | 필터 모드 |
| `promote DEBT-NNN` | 승격 모드 (특정) |
| `promote auto` | 승격 모드 (자동 선택) |

---

## Dashboard Mode

### Step 2: TECH-DEBT 로드

1. **읽기**: `docs/TECH-DEBT.md`
2. **파싱**: 모든 섹션:
   - Summary 테이블
   - 우선순위별 Active 항목
   - Resolved 항목

### Step 3: 통계 계산

각 active 부채 항목에서 추출:
- DEBT ID, 제목, 우선순위, 카테고리
- 추가 날짜, 경과일
- 위치, Blocked by (있는 경우)

### Step 4: 필터 적용 (필터 모드인 경우)

| 필터 | 동작 |
|------|------|
| `all` (기본) | 모든 active 항목 표시 |
| `critical` | Critical 우선순위만 |
| `high` | High 우선순위만 |
| `medium` | Medium 우선순위만 |
| `low` | Low 우선순위만 |
| `category:<name>` | 카테고리로 필터 |
| `aged` | 에스컬레이션 임계값 초과 항목 |

### Step 5: 대시보드 생성

```
## TECH-DEBT Dashboard

**Service**: ai-report
**Generated**: YYYY-MM-DD HH:MM

---

### Health Status: 🟢 Good / 🟡 Warning / 🔴 Critical

[건강 지표 기반 설명]

---

### Summary

| Priority | Count | Oldest | Avg Age |
|----------|-------|--------|---------|
| Critical | 0 | - | - |
| High | N | Xd | Yd |
| Medium | N | Xd | Yd |
| Low | N | Xd | Yd |
| **Total** | **N** | - | **Zd** |

---

### Escalation Alerts

| DEBT ID | Priority | Age | Threshold | Status |
|---------|----------|-----|-----------|--------|
| DEBT-001 | High | 16d | 14d | ⚠️ 승격 권장 |

---

### Active Items by Priority

#### Critical Priority
_Critical 항목 없음._

#### High Priority
| ID | Title | Category | Age | Location |
|----|-------|----------|-----|----------|
| DEBT-001 | [제목] | Performance | 16d | `src/file.py:NN` |

#### Medium Priority
| ID | Title | Category | Age | Location |
|----|-------|----------|-----|----------|
| DEBT-002 | [제목] | Testing | 25d | `src/file.py:NN` |

---

### Quick Actions

- 경과 항목 승격: `/tech-debt promote DEBT-001`
- 자동 승격: `/tech-debt promote auto`
- 특정 우선순위 보기: `/tech-debt high`
```

---

## Promote Mode

### Step 2P: 승격 후보 선택

#### If `promote DEBT-NNN`:
1. **찾기**: 지정된 부채 항목
2. **검증**: 존재하고 active 상태인지
3. **진행**: Step 3P로

#### If `promote auto`:
1. **에스컬레이션 기준 적용**:
   - Critical 우선순위 → 항상 승격
   - High 우선순위 + 14일 초과 → 승격
   - Medium 우선순위 + 21일 초과 → 고려
   - 같은 카테고리에 3개 이상 → 가장 오래된 것 승격

2. **후보 순위 지정** (긴급도 기준)
3. **최상위 후보 선택** 또는 사용자 선택을 위한 목록 제시:
   ```
   ## Auto-Promote Candidates

   | # | DEBT ID | Priority | Age | Reason |
   |---|---------|----------|-----|--------|
   | 1 | DEBT-001 | High | 16d | 14d 임계값 초과 |
   | 2 | DEBT-002 | Medium | 25d | 21d 임계값 초과 |

   승격할 항목 선택 (1-N) 또는 'cancel':
   ```

### Step 3P: 부채 항목 분석

1. **부채 항목 상세 읽기**:
   - Description, Impact, Remediation 단계
   - Estimated effort, Location

2. **대상 Phase 결정**:
   - 블로킹 중이면 현재 Phase
   - 개선 사항이면 다음 Phase

### Step 4P: Sub-task 생성

부채를 개발 계획 형식으로 변환:

```markdown
### X.Y - [DEBT-NNN] 해결: [짧은 제목]

**Source**: TECH-DEBT 승격
**Original Priority**: [Priority]

- [ ] [Remediation 단계 1]
- [ ] [Remediation 단계 2]
- [ ] 테스트 추가/업데이트
- [ ] DEBT-NNN resolved 표시
```

### Step 5P: 제안 제시

```
## Debt Promotion Proposal

### Source Item

**DEBT ID**: DEBT-NNN
**Title**: [Title]
**Priority**: [Priority] | **Age**: [X days]
**Category**: [Category]

**Description**:
[TECH-DEBT의 설명]

### Proposed Development Task

**Target**: Phase X, Sub-task X.Y

```markdown
### X.Y - DEBT-NNN 해결: [Title]

- [ ] [Task 1]
- [ ] [Task 2]
- [ ] 테스트 업데이트
- [ ] DEBT-NNN resolved 표시
```

development-plan.md에 추가? (yes/no)
```

### Step 6P: 문서 업데이트 (승인 시)

1. **development-plan.md 업데이트**:
   - 적절한 Phase에 새 sub-task 추가
   - `[DEBT-NNN]` 참조 포함

2. **TECH-DEBT.md 업데이트**:
   - 노트 추가: "YYYY-MM-DD에 Phase X.Y로 승격됨"
   - 해결될 때까지 active 유지

### Step 7P: 요약

```
## Promotion Complete

**DEBT Item**: DEBT-NNN - [Title]
**Promoted To**: Phase X.Y

### Changes Made
- development-plan.md: Sub-task X.Y 추가됨
- TECH-DEBT.md: 승격 노트 추가됨

### Next Steps
1. /dev-ai-report 실행하여 승격된 태스크 작업
2. 완료 시 DEBT-NNN resolved 표시
```

---

## Escalation Criteria

| Priority | Age Threshold | Action |
|----------|---------------|--------|
| Critical | 0 days | 자동 승격 |
| High | 14 days | 승격 권장 |
| Medium | 21 days | 승격 제안 |
| Low | 30 days | 승격 고려 |

### Additional Triggers

| Condition | Action |
|-----------|--------|
| 현재 작업 블록 | 즉시 승격 |
| 같은 카테고리 3개 이상 | 가장 오래된 것 승격 |
| 보안 관련 | 우선순위 상향 |

---

## Health Indicators

| Indicator | 🟢 Good | 🟡 Warning | 🔴 Critical |
|-----------|---------|------------|-------------|
| 총 개수 | < 5 | 5-10 | > 10 |
| Critical 항목 | 0 | 1 | > 1 |
| High 항목 > 14d | 0 | 1-2 | > 2 |
| 평균 경과일 | < 7d | 7-14d | > 14d |

---

## Example Invocations

전체 대시보드:
```
/tech-debt
```

우선순위로 필터:
```
/tech-debt high
/tech-debt critical
```

카테고리로 필터:
```
/tech-debt category:security
```

경과 항목 표시:
```
/tech-debt aged
```

특정 항목 승격:
```
/tech-debt promote DEBT-001
```

자동 선택 및 승격:
```
/tech-debt promote auto
```
