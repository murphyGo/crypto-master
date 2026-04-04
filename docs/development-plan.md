# Crypto Master - 개발 계획서

## 참조 문서

- `docs/requirements.md` - 요구사항 명세서
- `docs/inception.md` - 프로젝트 컨셉 문서

---

## 현재 상태

| 컴포넌트 | 상태 | Phase |
|---------|------|-------|
| 프로젝트 설정 | ❌ Missing | 1 |
| 설정 관리 | ❌ Missing | 1 |
| 거래소 추상화 | ❌ Missing | 2 |
| Binance 연동 | ❌ Missing | 2 |
| Bybit 연동 | ❌ Missing | 2 |
| 분석 기법 프레임워크 | ❌ Missing | 3 |
| Claude 연동 | ❌ Missing | 3 |
| 트레이딩 전략 | ❌ Missing | 4 |
| 모의 트레이딩 | ❌ Missing | 4 |
| 실전 트레이딩 | ❌ Missing | 4 |
| 백테스팅 | ❌ Missing | 5 |
| 피드백 루프 | ❌ Missing | 5 |
| 트레이딩 제안 | ❌ Missing | 6 |
| UI Dashboard | ❌ Missing | 7 |

**상태 범례**: ✅ Complete | 🔄 In Progress | ❌ Missing

---

## Phase 1: 프로젝트 설정 & 기본 인프라

**관련 요구사항**: NFR-001, NFR-004, NFR-005

### 1.1 프로젝트 구조 설정

- [ ] `src/` 패키지 구조 생성 (`src/__init__.py`)
- [ ] `pyproject.toml` 설정 (의존성, 메타데이터)
- [ ] `requirements.txt` 생성 (pip 호환)
- [ ] `.env.example` 템플릿 생성
- [ ] `.gitignore` 업데이트 (.env, __pycache__, .venv 등)

### 1.2 설정 관리 모듈

- [ ] `src/config.py` - 환경변수 로드 (python-dotenv)
- [ ] 필수 설정값 검증 로직
- [ ] 거래소별 API 키 설정 구조

### 1.3 공통 유틸리티

- [ ] `src/logger.py` - 로깅 설정 (파일 + 콘솔)
- [ ] `src/models.py` - 공통 타입 정의 (dataclass/Pydantic)
- [ ] 단위 테스트 설정 (`tests/__init__.py`, `pytest.ini`)

---

## Phase 2: 거래소 연동 기반

**관련 요구사항**: FR-016, FR-017, FR-018, FR-019, FR-020, NFR-009

### 2.1 거래소 추상화 레이어

- [ ] `src/exchange/base.py` - BaseExchange 추상 클래스 정의
- [ ] 공통 데이터 모델 정의 (OHLCV, Order, Position, Balance)
- [ ] 거래소 팩토리 함수 구현
- [ ] 단위 테스트 작성

### 2.2 Binance 연동

- [ ] `src/exchange/binance.py` - BinanceExchange 클래스 구현
- [ ] 과거 OHLCV 데이터 조회 (klines API)
- [ ] 현재가 조회
- [ ] 잔고 조회
- [ ] 주문 생성/취소/조회 인터페이스
- [ ] Rate Limit 처리
- [ ] 단위 테스트 작성 (API 모킹)

### 2.3 Bybit 연동

- [ ] `src/exchange/bybit.py` - BybitExchange 클래스 구현
- [ ] 과거 OHLCV 데이터 조회
- [ ] 현재가 조회
- [ ] 잔고 조회
- [ ] 주문 인터페이스
- [ ] 단위 테스트 작성

### 2.4 Tapbit 연동 — *deferred to later*

---

## Phase 3: 차트 분석 시스템

**관련 요구사항**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-005, NFR-010

### 3.1 분석 기법 프레임워크

- [ ] `src/strategy/base.py` - BaseStrategy 추상 클래스
- [ ] `src/strategy/loader.py` - 기법 로더 (md/py 파일에서 로드)
- [ ] `strategies/` 디렉토리 구조 생성
- [ ] 기법 메타데이터 스키마 정의 (이름, 버전, 설명)
- [ ] 단위 테스트 작성

### 3.2 기본 분석 기법 구현

- [ ] `strategies/sample_prompt.md` - 샘플 md 프롬프트 기법
- [ ] `strategies/sample_code.py` - 샘플 Python 코드 기법
- [ ] 기법 실행 및 결과 반환 로직
- [ ] 단위 테스트 작성

### 3.3 Claude 연동

- [ ] `src/ai/claude.py` - Claude CLI 래퍼 (`claude -p "..."`)
- [ ] 차트 분석 프롬프트 템플릿
- [ ] 응답 파싱 로직 (트레이딩 포인트 추출)
- [ ] 에러 처리 (CLI 실패, 파싱 실패)
- [ ] 단위 테스트 작성

### 3.4 분석 기법 성과 트래킹

- [ ] `src/strategy/performance.py` - 성과 데이터 모델
- [ ] 성과 기록 저장 (`data/performance/`)
- [ ] 성과 조회 및 집계 기능
- [ ] 단위 테스트 작성

---

## Phase 4: 트레이딩 전략 & 실행

**관련 요구사항**: FR-006, FR-007, FR-008, FR-009, FR-010, NFR-007, NFR-008, NFR-012

### 4.1 트레이딩 전략 모듈

- [ ] `src/trading/strategy.py` - 트레이딩 전략 계산기
- [ ] 손익비(R/R) 계산 함수
- [ ] 진입가/익절가/손절가 계산 함수
- [ ] 배율(레버리지) 설정 로직
- [ ] 포지션 사이즈 계산
- [ ] 단위 테스트 작성

### 4.2 모의 트레이딩 엔진

- [ ] `src/trading/paper.py` - PaperTrader 클래스
- [ ] 가상 자산(잔고) 관리
- [ ] 주문 시뮬레이션 (진입, 익절, 손절)
- [ ] 거래 이력 기록 (`data/trades/paper/`)
- [ ] 단위 테스트 작성

### 4.3 실전 트레이딩 엔진

- [ ] `src/trading/live.py` - LiveTrader 클래스
- [ ] 거래소 연동 주문 실행
- [ ] 사용자 확인 흐름 (실행 전 승인)
- [ ] 포지션 모니터링
- [ ] 거래 이력 기록 (`data/trades/live/`)
- [ ] 단위 테스트 작성

### 4.4 자산/PnL 관리

- [ ] `src/trading/portfolio.py` - 포트폴리오 관리
- [ ] 자산 이력 저장 (`data/portfolio/`)
- [ ] PnL 계산 (실현/미실현)
- [ ] 모의/실전 모드별 분리 저장
- [ ] 단위 테스트 작성

---

## Phase 5: 피드백 루프 시스템

**관련 요구사항**: FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027, NFR-006

### 5.1 백테스팅 엔진

- [ ] `src/backtest/engine.py` - Backtester 클래스
- [ ] 과거 데이터로 전략 시뮬레이션
- [ ] 거래 시뮬레이션 (슬리피지, 수수료 고려)
- [ ] 결과 저장 (JSON/CSV - `data/backtest/`)
- [ ] 단위 테스트 작성

### 5.2 성과 분석기

- [ ] `src/backtest/analyzer.py` - PerformanceAnalyzer 클래스
- [ ] 승률 계산
- [ ] 총 수익률 / 연환산 수익률
- [ ] 최대 낙폭 (MDD) 계산
- [ ] 샤프 비율 계산
- [ ] 리포트 생성 (md 형식)
- [ ] 단위 테스트 작성

### 5.3 Claude 기반 기법 개선

- [ ] `src/ai/improver.py` - StrategyImprover 클래스
- [ ] 성과 데이터 기반 개선 프롬프트 생성
- [ ] 새 기법 아이디어 생성 프롬프트
- [ ] 사용자 아이디어 입력 → 기법 생성
- [ ] 생성된 기법 저장 (`strategies/experimental/`)
- [ ] 단위 테스트 작성

### 5.4 자동화 피드백 루프

- [ ] `src/feedback/loop.py` - FeedbackLoop 오케스트레이터
- [ ] 루프 실행: 분석 → 개선 → 백테스팅 → 평가
- [ ] 성과 임계값 기반 자동 판단
- [ ] 기법 정식 도입 흐름 (사용자 승인)
- [ ] 루프 상태 저장 및 재개
- [ ] 단위 테스트 작성

---

## Phase 6: 트레이딩 제안 시스템

**관련 요구사항**: FR-011, FR-012, FR-013, FR-014, FR-015

### 6.1 제안 엔진

- [ ] `src/proposal/engine.py` - ProposalEngine 클래스
- [ ] 비트코인 트레이딩 제안 로직 (베스트 기법 적용)
- [ ] 알트코인 스캔 및 제안 로직 (다중 코인 분석)
- [ ] 제안 점수 계산 (성과 예측)
- [ ] 단위 테스트 작성

### 6.2 사용자 인터랙션

- [ ] `src/proposal/interaction.py` - 사용자 인터랙션 처리
- [ ] 제안 표시 형식 (CLI)
- [ ] 수락/거절 입력 처리
- [ ] 제안 이력 저장 (`data/proposals/`)
- [ ] 단위 테스트 작성

### 6.3 알림 시스템

- [ ] `src/proposal/notification.py` - 알림 모듈
- [ ] 콘솔 알림
- [ ] 파일 기반 알림 로그
- [ ] 단위 테스트 작성

---

## Phase 7: UI Dashboard

**관련 요구사항**: FR-028, FR-029, FR-030, FR-031, FR-032, NFR-003

### 7.1 Streamlit 앱 기본 구조

- [ ] `src/dashboard/app.py` - 메인 Streamlit 앱
- [ ] 앱 레이아웃 설정 (사이드바, 메인 영역)
- [ ] 페이지 네비게이션 구성
- [ ] 공통 스타일/테마 설정

### 7.2 분석 기법 현황 페이지

- [ ] `src/dashboard/pages/strategies.py` - 기법 현황 페이지
- [ ] 등록된 기법 목록 표시
- [ ] 기법별 성과 지표 표시
- [ ] 성과 추이 차트

### 7.3 트레이딩 현황 페이지

- [ ] `src/dashboard/pages/trading.py` - 트레이딩 현황 페이지
- [ ] 진행 중 포지션 표시 (모의/실전)
- [ ] 최근 거래 이력
- [ ] 자산 현황 및 PnL 요약
- [ ] 수익 곡선 차트

### 7.4 피드백 루프 현황 페이지

- [ ] `src/dashboard/pages/feedback.py` - 피드백 루프 페이지
- [ ] 실험 중 기법 목록
- [ ] 백테스팅 결과 표시
- [ ] 루프 진행 상태

### 7.5 Tapbit 연동 (Deferred)

- [ ] `src/exchange/tapbit.py` - TapbitExchange 클래스 구현

---

## 요구사항 매핑

| Phase | 관련 요구사항 |
|-------|--------------|
| Phase 1 | NFR-001, NFR-004, NFR-005 |
| Phase 2 | FR-016, FR-017, FR-018, FR-019, FR-020, NFR-009 |
| Phase 3 | FR-001, FR-002, FR-003, FR-004, FR-005, NFR-002, NFR-005, NFR-010 |
| Phase 4 | FR-006, FR-007, FR-008, FR-009, FR-010, NFR-007, NFR-008, NFR-012 |
| Phase 5 | FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027, NFR-006 |
| Phase 6 | FR-011, FR-012, FR-013, FR-014, FR-015 |
| Phase 7 | FR-028, FR-029, FR-030, FR-031, FR-032, NFR-003 |

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0 | 2026-04-05 | 초기 작성 | Claude |
