# AI Report Development Skill

개발 계획을 따라 AI Report 서비스를 점진적으로 개발합니다.

## Arguments

- `$ARGUMENTS` - (선택) 특정 Phase 또는 태스크 지정 (예: `phase2`, `2.1`)

## Objective

개발 계획에서 한 번에 하나의 sub-task를 실행하여 AI Report 서비스를 점진적으로 개발합니다. 요구사항 준수, 모범 사례, 단위 테스트를 통해 품질을 보장합니다.

---

## Execution Steps

### Step 0: Health Check (자동)

개발 시작 전 자동 상태 점검:

1. **TECH-DEBT 에스컬레이션 체크**:
   - `docs/TECH-DEBT.md` 읽기
   - 임계값 초과 항목 확인:
     - Critical: 모든 경과일 → Alert
     - High: > 14일 → Alert
     - Medium: > 21일 → Warn
   - 에스컬레이션 후보 발견 시 표시:
     ```
     ⚠️ TECH-DEBT Alert

     | DEBT ID | Priority | Age | Action Suggested |
     |---------|----------|-----|------------------|
     | DEBT-001 | High | 16d | /tech-debt promote 고려 |

     개발을 계속 진행? (yes/no/review-debt)
     ```

2. **Phase 완료 체크**:
   - `docs/development-plan.md`에서 완료된 Phase 스캔
   - `docs/cross-checks/`에서 기존 리뷰 확인
   - 미체크 Phase 발견 시:
     ```
     📋 Phase Review Pending

     Phase 1이 완료되었으나 cross-check 문서가 없습니다.
     지금 cross-check 실행? (yes/no/later)
     ```

**Note**: Health check alert는 정보 제공용입니다. "yes"로 진행하거나 먼저 이슈를 해결할 수 있습니다.

### Step 1: 환경 검증

1. **경로 존재 확인**:
   - `docs/development-plan.md`
   - `docs/TECH-DEBT.md`
   - `docs/requirements.md`
   - `CLAUDE.md`
   - `DESIGN.md`

### Step 2: 개발 계획 분석

1. **읽기**: `docs/development-plan.md`

2. **계획 파싱**:
   - 현재 상태 테이블 (컴포넌트 완료 상태)
   - 모든 Phase와 sub-task
   - 체크박스 상태: `[x]` = 완료, `[ ]` = 미완료

3. **다음 개발 대상 찾기** (위에서 아래로 스캔):
   - 완전히 체크된 `[x]` Phase/sub-task 스킵
   - "deferred" 또는 "— *deferred*"로 표시된 항목 스킵
   - 최소 하나의 미체크 `[ ]` 항목이 있는 **첫 번째 sub-task** 선택
   - 혼합 상태의 sub-task는 미체크 항목만 대상

### Step 3: 개발 대상 제시

식별된 sub-task를 다음 형식으로 제시:

```
## Next Development Target

**Phase**: [Phase 번호와 이름]
**Sub-task**: [Sub-task 번호와 제목]

### Items to Develop:
- [ ] 항목 1 설명
- [ ] 항목 2 설명
...

### Related Requirements:
- FR-XXX: [요구사항 설명]
- NFR-XXX: [요구사항 설명]

### Estimated Files:
- New: [생성할 파일 목록]
- Modified: [수정할 파일 목록]

이 개발을 진행? (yes/no)
```

**진행 전 사용자 승인 대기.**

### Step 4: 개발 (Plan Mode)

사용자 승인 후:

1. **Plan Mode 진입**: `EnterPlanMode` 도구 사용

2. **Research Phase**:
   - `docs/requirements.md`에서 관련 요구사항 읽기
   - `DESIGN.md`에서 설계 패턴 확인
   - 기존 코드베이스 탐색하여 패턴과 의존성 이해

3. **구현 계획 작성**:
   - 생성/수정할 파일
   - 요구사항에 맞춘 구현 접근법
   - 테스트 전략 (모든 새 기능에 단위 테스트)
   - 기존 코드와의 통합 지점

4. **Plan Mode 종료** 후 구현:
   - Python 모범 사례 엄격히 준수
   - 깔끔하고 관용적인 Python 코드 작성
   - 포괄적인 단위 테스트 포함
   - 테스트 실행하여 검증: `pytest`

### Step 5: Self-Review & 문서화

구현 성공 후:

**5.1 Code Review** (자동):
- 변경된 파일에 `/code-review git` 실행
- 🔴 Critical/High 이슈 발견 시 진행 전 수정 또는 TECH-DEBT에 문서화

**5.2 Session Log 생성** (`docs/sessions/YYYY-MM-DD-<phase>-<task>.md`):

```markdown
# Session Log: YYYY-MM-DD - Phase N.M - [Task Title]

## Overview
- **Date**: YYYY-MM-DD
- **Phase**: N - [Phase Name]
- **Sub-task**: N.M - [Sub-task Name]

## Work Summary
[완료된 작업에 대한 간략한 설명]

## Files Changed
- Created: [목록]
- Modified: [목록]

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| [What] | [Why] |

## Code Review Results
| Category | Status |
|----------|--------|
| Error Handling | ✅/⚠️/🔴 |
| Resource Management | ✅/⚠️/🔴 |
| Security | ✅/⚠️/🔴 |
| Type Hints | ✅/⚠️/🔴 |
| Tests | ✅/⚠️/🔴 |

## Potential Risks
- [식별된 위험]

## TECH-DEBT Items
- [추적할 새 항목, 있는 경우]
```

**5.3 TECH-DEBT.md 업데이트** (해당되는 경우):
- 구현 중 발견된 새 부채 항목 추가
- 코드 리뷰에서 미수정 이슈 추가
- 해결된 부채 항목 표시

### Step 6: 개발 계획 업데이트

문서화 후:

1. **체크박스 업데이트**:
   - 완료된 항목 `[x]`로 표시
   - sub-task의 모든 항목이 완료되면 sub-task 헤더도 완료로 간주

2. **현재 상태 테이블 업데이트**:
   - `✅ Complete` - 관련 모든 sub-task 완료
   - `🔄 In Progress` - 일부 sub-task 완료
   - `❌ Missing` - sub-task 시작 안됨

3. **추가 제안** (해당되는 경우):
   - 구현 중 추가 필요사항 발견 시 새 sub-task 제안
   - 형식: "Phase X에 추가 제안: [설명]"

4. **Phase 완료 자동 액션** (Phase 방금 완료 시):
   - 감지: 현재 Phase의 모든 sub-task가 `[x]`
   - 자동 cross-check 트리거:
     ```
     🎉 Phase [N] Complete!

     Phase [N]의 모든 sub-task가 완료되었습니다.
     요구사항 대비 자동 cross-check 실행 중...
     ```
   - `/cross-check` 로직 인라인 실행:
     - 구현 vs 요구사항 검증
     - 준수 매트릭스 생성
     - `docs/cross-checks/phase-N-[name].md` 생성
   - 발견된 갭 리포트:
     ```
     Cross-Check Results:
     - ✅ Complete: X 요구사항
     - ⚠️ Partial: Y 요구사항
     - ❌ Gap: Z 요구사항

     [갭이 있으면] 갭 항목을 다음 Phase에 추가? (yes/no)
     ```

### Step 7: 요약 리포트

완료 요약 제공:

```
## Development Complete

**Sub-task**: [Sub-task 번호와 제목]
**Status**: Complete

### Changes Made:
- Created: [새 파일 목록]
- Modified: [수정된 파일 목록]

### Tests:
- Added: [개수] 새 테스트
- All tests passing: Yes/No

### Documentation:
- Session Log: [파일명]
- TECH-DEBT: [추가/해결된 항목, 있으면]

### Feedback Loop Actions:
- TECH-DEBT: [추가/해결된 항목]
- Cross-Check: [Phase 완료 시 생성됨 / 필요 없음]

### Phase Completion: (해당되는 경우)
- Phase [N] 완료: Yes/No
- Cross-check 생성됨: [파일명]
- 준수율: [X]% complete
- 다음 Phase에 추가된 갭: [개수]

### Development Plan Updated:
- [체크박스 변경 목록]
- 현재 상태: [컴포넌트] → [새 상태]

### Next Sub-task Preview:
[다음 미완료 sub-task 간략 설명, 있으면]
```

---

## Guidelines

### Commit Policy

**자동 커밋 안함**: 자동으로 변경사항을 커밋하지 않습니다. 항상 사용자에게 변경사항을 보여주고 커밋 전 명시적 승인을 받습니다.

### Sub-task Selection Rules

1. **실행당 하나의 sub-task** - 한 번의 실행에서 여러 sub-task를 개발하지 않음
2. **연기된 항목 스킵** - "deferred" 또는 "— *deferred to Phase X*"로 표시된 항목은 개발 대상 아님
3. **부분 완료** - 일부 완료된 항목이 있는 sub-task는 남은 미완료 항목만 개발
4. **순차 순서** - 항상 문서 순서대로 Phase와 sub-task 처리 (위에서 아래로)

### Development Standards

1. **요구사항 준수**:
   - 모든 구현은 `docs/requirements.md`와 일치해야 함
   - 코드 주석에 요구사항 ID 참조 (예: FR-001, NFR-001)

2. **Python 모범 사례**:
   - PEP 8 스타일 가이드 준수
   - 타입 힌트 사용
   - 에러 처리 with context
   - pytest로 테스트

3. **테스트 요구사항**:
   - 모든 새 함수/메서드에 단위 테스트 필요
   - 성공과 에러 경로 모두 테스트
   - 파일 기반 테스트에 `tmp_path` 픽스처 사용
   - 외부 의존성 모킹

4. **코드 구조**:
   - 새 코드는 `src/` 패키지에
   - 기존 프로젝트 구조 패턴 따르기

### Development Plan Update Rules

1. **체크박스 업데이트**:
   ```markdown
   - [x] 완료된 항목    # 완료 시 체크
   - [ ] 대기 중 항목   # 미완료 시 미체크
   ```

2. **상태 매핑**:
   | 조건 | 상태 |
   |------|------|
   | 모든 sub-task 완료 | `✅ Complete` |
   | 최소 하나의 sub-task 완료 | `🔄 In Progress` |
   | sub-task 시작 안됨 | `❌ Missing` |

3. **새 Sub-task 추가**:
   - 제안만, 사용자 승인 없이 추가하지 않음
   - 근거와 함께 제안을 명확히 포맷

---

## Error Handling

- **미완료 sub-task 없음**: "개발 계획의 모든 sub-task가 완료되었습니다!" 리포트
- **테스트 실패**: sub-task 완료로 표시하지 않음; 실패 리포트 및 수정 제안
- **빌드 에러**: 진행 전 수정; 해결될 때까지 개발 계획 업데이트 안함

---

## Example Invocations

다음 대기 중인 태스크 개발:
```
/dev-ai-report
```

특정 Phase 작업:
```
/dev-ai-report phase2
```

특정 sub-task 작업:
```
/dev-ai-report 2.1
```
