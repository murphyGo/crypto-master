# Cross-Check Skill

설계 문서와 구현의 일치 여부를 검증하고 준수 리포트를 생성합니다.

## Arguments

- `$ARGUMENTS` - 검증할 컴포넌트 또는 Phase (예: `collectors`, `summarizer`, `phase2`)

## Objective

구현이 설계 문서(CLAUDE.md, DESIGN.md, docs/requirements.md)의 요구사항과 일치하는지 체계적으로 검증하고, 갭을 식별하여 개발 계획 업데이트를 위한 실행 가능한 리포트를 생성합니다.

---

## Execution Steps

### Step 1: 입력 검증

1. **인자 파싱**:
   - 컴포넌트 이름 또는 Phase 식별자

2. **경로 존재 확인**:
   - `CLAUDE.md`
   - `DESIGN.md`
   - `docs/requirements.md`
   - `docs/development-plan.md`

3. **범위 식별**:
   - 인자를 관련 요구사항 및 구현 파일에 매핑

### Component-to-File 매핑 가이드

| Component | 관련 파일 | 요구사항 |
|-----------|----------|---------|
| collectors | `src/collectors/*.py` | FR-001, FR-002, FR-003 |
| summarizer | `src/summarizer.py` | FR-004, FR-005 |
| notifier | `src/slack_notifier.py` | FR-006, FR-007 |
| cli | `src/main.py` | FR-008, FR-009, FR-010 |
| config | `src/config.py` | NFR-004, NFR-005 |

### Step 2: 요구사항 로드

1. **요구사항 문서 읽기**: `docs/requirements.md`

2. **요구사항 추출**:
   - 기능 요구사항 (FR-XXXX)
   - 비기능 요구사항 (NFR-XXXX)
   - 상태 정보

3. **요구사항 체크리스트 생성** (카테고리별 정리)

### Step 3: 구현 분석

1. **범위 내 구현 파일 읽기**:
   - `src/` 디렉토리의 소스 코드
   - 테스트 파일 (커버리지 분석용)

2. **요구사항과 코드 매핑**:
   - 코드 주석에서 요구사항 ID 참조 검색
   - 함수 구현을 요구사항에 추적
   - 요구사항별 테스트 커버리지 검증

3. **비기능 요구사항 체크**:
   - 에러 처리 패턴
   - 보안: 환경 변수 사용
   - 로깅 구현

### Step 4: 준수 매트릭스 생성

각 요구사항에 대해 상태 결정:

| 상태 | 기준 |
|------|------|
| ✅ Complete | 완전히 구현됨, 테스트됨, 문서화됨 |
| ⚠️ Partial | 구현되었으나 테스트/문서/엣지케이스 누락 |
| ❌ Gap | 구현되지 않음 |
| 🔄 Deferred | 명시적으로 연기됨 (사유 포함) |

### Step 5: 갭과 액션 식별

1. **각 Gap (❌)에 대해**:
   - 누락된 내용 문서화
   - 영향 평가
   - 개발 계획 추가 제안

2. **각 Partial (⚠️)에 대해**:
   - 남은 작업 문서화
   - Critical vs Enhancement 분류

3. **제안 태스크 생성**:
   ```
   GAP-001: [설명] → Phase X에 추가
   ```

### Step 6: Cross-Check 문서 생성

1. **파일명 생성**: `docs/cross-checks/<component>-check.md`

2. **섹션 작성**:
   - 범위 개요
   - 모든 요구사항이 포함된 준수 매트릭스
   - 제안 액션이 포함된 갭 분석
   - Partial 구현 상세
   - 테스트 커버리지 요약
   - 권장사항

### Step 7: 개발 계획 업데이트 제안

갭이 발견된 경우 제안된 변경사항 제시:

```
## 제안된 개발 계획 업데이트

### Cross-Check에서 발견된 새 태스크

**Phase X.Y - [새 태스크 제목]**
Source: GAP-001 from cross-check
- [ ] [갭에서 도출된 항목 1]
- [ ] [갭에서 도출된 항목 2]

development-plan.md에 추가? (yes/no)
```

### Step 8: 요약 리포트

```
## Cross-Check 완료

**Component**: [identifier]
**Date**: YYYY-MM-DD

### 준수 요약
| 상태 | 개수 | 비율 |
|------|------|------|
| ✅ Complete | N | X% |
| ⚠️ Partial | N | X% |
| ❌ Gap | N | X% |
| 🔄 Deferred | N | X% |

### 생성된 액션
- 갭 → 개발 계획: [개수]
- Partial → TECH-DEBT: [개수]
- 식별된 테스트 갭: [개수]

### 생성된 문서
- Cross-Check: `docs/cross-checks/[filename]`

### 권장 다음 단계
1. [우선 액션]
2. [차순위 액션]
```

---

## 요구사항 상태 기준

### Complete (✅)
- 코드가 요구사항을 구현함
- 단위 테스트 존재 및 통과
- 에러 케이스 처리됨
- 문서화됨 (주석 또는 docs)

### Partial (⚠️)
- 핵심 기능은 동작하지만:
  - 엣지 케이스 처리 누락
  - 테스트 불완전
  - 성능 미검증
  - 문서화 누락

### Gap (❌)
- 요구사항이 코드에서 해결되지 않음
- 원인:
  - 구현 중 누락
  - 의존성에 의해 블록
  - 현재 범위 외

### Deferred (🔄)
- 계획에서 명시적으로 "deferred"로 표시
- 문서화된 사유 있음
- 향후 Phase에 계획됨

---

## 다른 Skill과의 연동

### Cross-Check 트리거
- `/dev-ai-report` Phase 완료 후 자동
- 재검증을 위한 수동 호출

### Cross-Check 출력 대상
- **개발 계획**: 갭에서 새 태스크
- **TECH-DEBT**: Partial 구현
- **세션 로그**: 관련 세션에서 참조

---

## 가이드라인

### 범위 제어
- Cross-check당 하나의 컴포넌트
- 관련 없는 기능 결합하지 않음
- 준수 매트릭스 집중 유지

### 갭 우선순위
| 갭 유형 | 우선순위 | 액션 |
|---------|---------|------|
| 핵심 기능 | Critical | Phase 완료 블록 |
| 엣지 케이스 | High | 현재 Phase에 추가 |
| Nice-to-have | Medium | 다음 Phase로 연기 |
| 문서화 | Low | Tech debt에 추가 |

### 검증 방법
- **코드 리뷰**: 수동 검사
- **테스트 실행**: 관련 테스트 실행
- **정적 분석**: 패턴 체크
- **스펙 비교**: 라인별 검증

---

## Example Invocations

Collectors 검증:
```
/cross-check collectors
```

Summarizer 검증:
```
/cross-check summarizer
```

전체 Phase 검증:
```
/cross-check phase1
```
