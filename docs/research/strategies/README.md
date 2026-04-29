# Crypto 트레이딩 기법 리서치

이 디렉터리는 **자동 전략 생성기(`StrategyImprover`)와 피드백 루프(`FeedbackLoop`)**가 참조할 수 있는 트레이딩 기법 레퍼런스 모음입니다. 각 문서는 외부 리서치(공식 자료 / 커뮤니티 / 유튜브)를 종합해 **시그널 정의(Entry/Exit/SL) — 결합 필터 — 실패 케이스 — 출처** 구조로 정리되어 있습니다.

총 6개 카테고리, **약 146개 기법, 5,084 줄**.

## 인덱스

| # | 카테고리 | 파일 | 분량 | 기법 수 | 특징 |
|---|---|---|---|---|---|
| 01 | **ICT / SMC** | [`01-ict-smc.md`](01-ict-smc.md) | 697줄 | 25 | Order Block, FVG, Liquidity Sweep, BOS/CHOCH, Killzone, PO3, SMT, Silver Bullet |
| 02 | **클래식 차트 패턴** | [`02-chart-patterns.md`](02-chart-patterns.md) | 930줄 | 27 | Triangles, Wedges, Channels, H&S, Double/Triple Top, Cup&Handle, Flags, Diamond, Harmonics + Tier 랭킹 |
| 03 | **돌파매매 & 레인지** | [`03-breakout-range.md`](03-breakout-range.md) | 823줄 | 19 | S/R 돌파, Fakeout, Donchian Turtle, ORB, BB Squeeze, TTM, NR4/NR7, Volume Profile |
| 04 | **역추세 / 평균회귀** | [`04-mean-reversion.md`](04-mean-reversion.md) | 936줄 | 16 | RSI 다이버전스, BB Reversion, VWAP MR, Z-score, Pairs Trading, Wyckoff Spring, Connors RSI(2) |
| 05 | **추세추종 지표** | [`05-trend-indicators.md`](05-trend-indicators.md) | 952줄 | 18 | MA Cross, EMA Ribbon, MACD, Ichimoku, Supertrend, ADX/DMI, KAMA/HMA/ALMA, Anchored VWAP |
| 06 | **크립토 특화** | [`06-crypto-specific.md`](06-crypto-specific.md) | 746줄 | 41 (+4 composite) | Funding, OI, Liquidation Heatmap, CVD, Whale, Exchange Flows, MVRV/NUPL, BTC.D, Kimchi Premium, ETF Flows |

## 카테고리별 핵심 요약

### 01 — ICT / SMC
시장 구조와 유동성 기반 매매. 자동화 친화적인 부분(Order Block, FVG, Liquidity Sweep, BOS/CHOCH)과 주관적 해석이 섞이는 부분(IPDA, Quarterly Theory)을 명확히 구분. 부록에 BTC 실제 사례 워크스루 + Python pseudo-code (`IctSmcSignal.detect()`) 포함.

### 02 — 클래식 차트 패턴
Bulkowski 통계 기반 신뢰도 인용. Tier 1 (성공률 70%+) ~ Tier 4로 분류해 자동 시그널 우선순위에 바로 사용 가능. Crypto 환경에서의 실패 모드(저volume 페이크, 24/7 갭) 별도 정리.

### 03 — 돌파매매 & 레인지
Turtle System (Donchian 20/55), Larry Williams Volatility, ORB 등 검증된 돌파 시스템 + 역방향 페이크아웃 매매. ATR/Volume 필터 기반 자동화 적합성 랭킹 + Pine 스타일 의사코드 cheatsheet 포함.

### 04 — 역추세 / 평균회귀
Connors RSI(2), Cardwell divergence, Wyckoff Spring 등 핵심 평균회귀 + **강추세 필터(Bollinger Walking)**로 false-signal 회피. Z-score / 통계적 평균회귀(ADF, Hurst) 섹션은 BTC/ETH 페어 트레이딩에 직접 사용 가능.

### 05 — 추세추종 지표
지표 기본 파라미터(ADX(14), Ichimoku 9/26/52/26, Supertrend ATR(10)×3, KAMA 10/2/30, ALMA 9/0.85/6)를 정확히 명시. **자동화 YAML 스키마 제안**과 chop/whipsaw 회피 필터 스택 포함.

### 06 — 크립토 특화
파생상품 microstructure(Funding/OI/CVD/Liquidation) + 온체인(MVRV/NUPL/SOPR/Hash Ribbon/Puell) + 거시(BTC.D/Kimchi/ETF Flows). **무료 vs 유료 데이터 소스**가 기법별로 명시되어 있어 실제 데이터 파이프라인 구성 가능. 4개 Composite Recipe(Crowded Long Top / Macro Bottom / Altseason Trigger / Squeeze Imminent)로 다중 시그널 조합 예시 제공.

## 본 문서들의 사용처

`src/ai/improver.py:97` (`StrategyImprover`)가 Claude에게 새 기법 후보(`generate_idea`, `generate_from_user_idea`)를 만들게 할 때, 이 문서들을 컨텍스트로 제공해 **"검증된 트레이딩 기법 풀"**에서 변형/조합하도록 유도할 수 있습니다.

또한 `src/feedback/loop.py`의 `propose_new()` / `from_user_idea()` 진입점에서 **사용자 아이디어**를 이 카탈로그의 시그널 정의와 매핑해 구현 디테일을 채울 수 있습니다.

## 일관된 문서 구조

각 기법은 다음 섹션을 가집니다:

```
**개요**: 시장 가설/메커니즘 (2-3문장)
**시그널 정의**:
  - Entry: 정밀한 규칙 (예: "RSI(14) < 30 AND 종가 > 직전 저점 AND 1H EMA200 우상향 → long")
  - Exit/SL: SL 위치, TP 규칙
**파라미터**: 기본값 + 자주 쓰이는 변형
**결합 필터**: HTF 추세, volume, ATR, 시간대 등
**실패 케이스 / 함정**: 알려진 실패 모드
**출처**: 권위 있는 URL 2-4개
```

## 출처 정책

- 모든 인용 URL은 실제로 도달 가능한 권위 있는 자료 (Bulkowski, Investopedia, BabyPips, StockCharts, Glassnode/CryptoQuant/Coinglass 공식 블로그 등)
- 한국 유튜브 채널은 식별 가능한 경우만 인용 (개별 영상 URL은 검색 한계로 일부만 포함)
- Reddit / Twitter quant 자료는 권위 있는 thread만 선별 인용

## 알려진 갭 / 후속 리서치 과제

각 문서 말미의 부록에 정리되어 있으며, 주요 항목:

- ICT 후기 자료(CISD, Quarterly Theory) — 공식화된 자료 부족
- 크립토용 SMT pair (BTC/SOL, BTC/Total3) — 정량 연구 부재
- 한국 유튜브 채널 개별 영상 URL — 검색 도구 한계
- Reddit r/algotrading의 정형화된 백테스트 결과 — 직접 thread 인용 어려움

향후 새 기법이 발견되면 같은 카테고리 파일에 추가하거나, 새 카테고리 파일(`07-*.md`)을 생성하고 본 README에 등록.
