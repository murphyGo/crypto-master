# Code Review Skill

Python 코드의 품질 이슈와 모범 사례 준수 여부를 자동으로 분석합니다.

## Arguments

- `$ARGUMENTS` - 다음 중 하나:
  - `git` - git에서 변경된 파일 리뷰 (staged + unstaged)
  - `session:<path>` - 세션 로그의 "Files Modified" 섹션에 나열된 파일 리뷰
  - `files:<path1>,<path2>` - 특정 파일들 리뷰
  - `dir:<path>` - 디렉토리의 모든 Python 파일 리뷰

## Objective

실제 소스 코드를 분석하여 일반적인 이슈, 보안 취약점, 모범 사례 위반을 사전에 발견합니다.

```
/code-review
─────────────
• 실제 코드 분석
• 사전 예방적 (이슈 발견)
• 자동화된 검증
• /dev-ai-report Step 5에서 실행
```

---

## Execution Steps

### Step 1: 리뷰할 파일 식별

#### If `git`:
```bash
git diff --name-only HEAD
git diff --name-only --cached
```
- staged와 unstaged 변경사항 결합
- `*.py` 파일만 필터링
- `*_test.py`는 별도 처리를 위해 분리

#### If `session:<path>`:
- 세션 로그 파일 읽기
- "Files Modified" 섹션 파싱
- 파일 경로 추출

#### If `files:<paths>`:
- 쉼표로 구분된 경로 분리
- 파일 존재 여부 검증

#### If `dir:<path>`:
- `<path>/**/*.py` Glob
- 테스트 파일 분리

### Step 2: 에러 핸들링 체크

각 Python 파일에서 스캔:

| 패턴 | 이슈 | 심각도 |
|------|------|--------|
| `except:` (bare except) | 너무 넓은 예외 처리 | High |
| `except Exception:` without logging | 예외 삼킴 | Medium |
| `pass` in except block | 무시된 예외 | High |
| `raise` without `from` | 체인 없는 re-raise | Low |

### Step 3: 리소스 관리 체크

정리 없는 리소스 획득 스캔:

| 패턴 | 확인 사항 | 심각도 |
|------|----------|--------|
| `open()` without `with` | context manager 미사용 | High |
| `requests.get/post` without timeout | 타임아웃 누락 | High |
| DB connection without close | 연결 미닫힘 | High |
| Thread/Process without join | 리소스 누수 | Medium |

### Step 4: 보안 체크

보안 이슈 스캔:

| 패턴 | 이슈 | 심각도 |
|------|------|--------|
| `password = "..."` | 하드코딩된 비밀번호 | Critical |
| `secret = "..."` | 하드코딩된 시크릿 | Critical |
| `api_key = "..."` | 하드코딩된 API 키 | Critical |
| `"sk-..."`, `"api_..."` | 문자열 내 API 키 | Critical |
| `pickle.loads` on untrusted data | 안전하지 않은 역직렬화 | Critical |
| `eval()`, `exec()` | 코드 인젝션 위험 | Critical |
| SQL string concatenation | SQL 인젝션 가능성 | Critical |
| `subprocess.shell=True` | 쉘 인젝션 위험 | High |

### Step 5: 엣지 케이스 & 잠재적 버그 체크

일반적인 엣지 케이스와 버그 패턴 스캔:

| 패턴 | 이슈 | 심각도 |
|------|------|--------|
| `if x is None` after `x.attr` | None 체크가 너무 늦음 | High |
| `len(list)` without None check | 잠재적 None 리스트 | Medium |
| Mutable default argument | 뮤터블 기본 인자 | High |
| `==` for None comparison | `is None` 사용해야 함 | Low |
| f-string with `{obj}` without `__str__` | 잠재적 repr 출력 | Low |

### Step 6: 타입 힌트 체크

타입 관련 이슈 스캔:

| 패턴 | 이슈 | 심각도 |
|------|------|--------|
| Public function without type hints | 타입 힌트 누락 | Low |
| `Any` type overuse | 타입 안전성 감소 | Low |
| `# type: ignore` without reason | 설명 없는 타입 무시 | Low |

### Step 7: 성능 & 메모리 체크

성능 및 메모리 이슈 스캔:

| 패턴 | 이슈 | 심각도 |
|------|------|--------|
| `+` for string concatenation in loop | 비효율적 문자열 연결 | Medium |
| List comprehension with side effects | 부작용 있는 컴프리헨션 | Medium |
| `global` keyword usage | 전역 상태 변경 | Medium |
| Large list instead of generator | 메모리 비효율 | Low |

### Step 8: 코드 품질 체크

코드 품질 이슈 스캔:

| 패턴 | 이슈 | 심각도 |
|------|------|--------|
| `# TODO` without `DEBT-` | 추적되지 않은 TODO | Low |
| `# FIXME` without `DEBT-` | 추적되지 않은 FIXME | Medium |
| `# HACK` | 설명 없는 핵 | Medium |
| `print()` in non-test code | 남겨진 디버그 출력 | Low |
| Magic numbers | 설명 없는 리터럴 | Low |
| Unused imports | 사용하지 않는 import | Low |

### Step 9: 테스트 커버리지 체크

새로/수정된 함수마다:

| 체크 | 방법 | 심각도 |
|------|------|--------|
| 테스트 존재 | `*_test.py`에서 `test_<func_name>` 찾기 | Medium |
| 에러 경로 테스트 | 예외 assertion 있는 테스트 찾기 | Medium |
| pytest 사용 | `pytest` 패턴 확인 | Low |

### Step 10: 리포트 생성

```markdown
## Code Review Report

**Scope**: [N개 파일 리뷰됨]
**Date**: YYYY-MM-DD HH:MM

---

### Summary

| Category | ✅ Pass | ⚠️ Warn | 🔴 Fail |
|----------|---------|---------|---------|
| Error Handling | X | Y | Z |
| Resource Management | X | Y | Z |
| Security | X | Y | Z |
| Edge Cases & Bugs | X | Y | Z |
| Type Hints | X | Y | Z |
| Performance & Memory | X | Y | Z |
| Code Quality | X | Y | Z |
| Test Coverage | X | Y | Z |
| **Total** | **X** | **Y** | **Z** |

**Status**: ✅ All Clear / ⚠️ Warnings Found / 🔴 Issues Found

---

### Issues Detail

#### 🔴 Critical/High Severity

| # | File:Line | Category | Issue | Suggestion |
|---|-----------|----------|-------|------------|
| 1 | collectors/arxiv.py:45 | Resource | open() without with | `with open() as f:` 사용 |

#### 🟡 Medium Severity

| # | File:Line | Category | Issue | Suggestion |
|---|-----------|----------|-------|------------|
| 2 | summarizer.py:78 | Error | Exception 삼킴 | 로깅 추가 |

#### 🟢 Low Severity

| # | File:Line | Category | Issue | Suggestion |
|---|-----------|----------|-------|------------|
| 3 | main.py:12 | Quality | TODO without DEBT | DEBT-XXX 참조 추가 |

---

### Self-Review Checklist (자동 생성)

| Item | Status | Evidence |
|------|--------|----------|
| 모든 예외가 적절히 처리됨 | ⚠️ | bare except 2개 발견 |
| 리소스 정리 완료 | ✅ | with 문 사용됨 |
| 하드코딩된 시크릿 없음 | ✅ | 탐지 안됨 |
| 엣지 케이스 처리됨 | ⚠️ | None 체크 1개 누락 |
| 타입 힌트 추가됨 | 🔴 | 3개 함수 누락 |
| 테스트가 에러 경로 커버 | ⚠️ | 1개 에러 경로 미테스트 |

---

### TECH-DEBT Candidates

기술 부채로 추적해야 할 이슈:

```markdown
### DEBT-XXX: collectors/arxiv.py의 bare except

**Category**: Reliability
**Priority**: Medium
**Location**: `src/collectors/arxiv.py:45,67`

**Description**:
너무 넓은 예외 처리로 인해 디버깅이 어려움

**Remediation**:
특정 예외 타입 지정 및 로깅 추가

**Estimated Effort**: 15분
```

TECH-DEBT.md에 추가? (yes/no)
```

---

## Ignore Directives

코드에 주석으로 리뷰에서 제외할 수 있습니다:

```python
# code-review:ignore-next-line
password = os.getenv("PASSWORD")  # 환경변수에서 읽음, OK

# code-review:ignore-block-start
# 레거시 코드, Phase 3에서 리팩토링 예정
def old_function():
    ...
# code-review:ignore-block-end
```

---

## Severity Definitions

| Severity | Meaning | Action |
|----------|---------|--------|
| 🔴 Critical | 보안 취약점 또는 데이터 손실 위험 | 커밋 전 반드시 수정 |
| 🔴 High | 버그 가능성 또는 리소스 누수 | 커밋 전 수정 권장 |
| 🟡 Medium | 코드 품질 이슈 | 수정 또는 TECH-DEBT로 기록 |
| 🟢 Low | 스타일/컨벤션 이슈 | 쉬우면 수정, 아니면 무시 |

---

## Example Invocations

git 변경사항 리뷰:
```
/code-review git
```

세션 로그에서 리뷰:
```
/code-review session:docs/sessions/2024-04-03-phase2-testing.md
```

특정 파일 리뷰:
```
/code-review files:src/collectors/arxiv.py,src/summarizer.py
```

디렉토리 리뷰:
```
/code-review dir:src/collectors
```
