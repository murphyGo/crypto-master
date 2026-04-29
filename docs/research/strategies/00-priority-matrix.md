# 00 — Strategy Priority Matrix (Synthesis)

> 6개 리서치 문서(`01-ict-smc.md` ~ `06-crypto-specific.md`, 총 ~146 기법)의 통합 우선순위 매트릭스.
> `StrategyImprover` (`src/ai/improver.py`)가 새 기법 후보를 생성할 때 이 표를 참조해 **자동화 친화도·신뢰도·크립토 적합도·결합 잠재력** 기준으로 정렬된 시그널 풀에서 변형·조합을 시도한다.
>
> 본 문서는 source doc의 사실을 재해석한 것이며, 모든 점수는 source doc 인용에 근거한다 (예: `doc 02 §13.3 Tier 1`).

---

## 1. Scoring Rubric

각 기법을 4개 차원에서 1–5 척도로 평가, 합산하여 `composite_score` (max 20) 산출.

### 1.1 `automation_score` (1–5) — 알고리즘 변환의 명확성
- **5**: 완전 결정론적. 한 줄 수식 또는 close-based 비교로 시그널 발화 가능 (e.g., `close > Donchian(20)`, `RSI(2) < 10`).
- **4**: 표준 indicator + 임계값 + simple state. 라이브러리 함수 1–3개 합성으로 구현 가능 (e.g., MACD signal cross, BB Squeeze).
- **3**: pivot/swing detector나 multi-step state machine 필요. lookback 파라미터에 결과 민감 (e.g., H&S, Order Block, Wyckoff Spring).
- **2**: 주관적 패턴 인식. trendline·neckline·cup의 모양을 algo가 잘못 그리기 쉬움 (e.g., Diamond, Three Drives, Cup&Handle).
- **1**: tape reading / 차트 해석. 현재 우리 OHLCV+derivatives 데이터로 결정론적 추출 불가 (e.g., Footprint absorption, Bart 패턴 후행 확정).

### 1.2 `reliability_score` (1–5) — 경험적 증거의 질
- **5**: 권위 있는 통계 인용 + 70%+ Bulkowski/peer-reviewed (e.g., IH&S 83%, Rectangle Top 85%).
- **4**: 백테스트 인용 또는 Bulkowski Tier 1–2 (`doc 02 §13.3`).
- **3**: 커뮤니티 공인 + 일부 backtest 보고 (e.g., TTM Squeeze, Donchian System 2).
- **2**: 통계 빈약, 사례 위주 (e.g., Three Drives, Diamond Top — Bulkowski rank 25/39).
- **1**: anecdotal-only / 학술 검증 부재 (e.g., 대부분 ICT/SMC 컨셉 — `doc 01 §10` "no empirical edge proof", IPDA, CISD).

### 1.3 `crypto_fit` (1–5) — 24/7 · no-circuit-breaker · high-vol regime 강건성
- **5**: 24/7에 본질적으로 적합 (e.g., funding rate, OI, liquidation, on-chain, BTC.D).
- **4**: 표준 OHLCV 기반이며 ATR로 변동성 정규화 가능 (e.g., Donchian, ATR breakout, EMA stack).
- **3**: 약간의 anchor 조정 필요 (e.g., ORB, VWAP — UTC 00:00 anchor 정해야 함).
- **2**: forex/주식 가정 강함, weekend/holiday noise 큼 (e.g., ICT Killzones, ICT/SMC 일반).
- **1**: 단일 open/close 가정 또는 circuit-breaker 의존 (e.g., gap-fill 전통식, weekly close 가정).

### 1.4 `combo_potential` (1–5) — 다른 시그널과의 confluence 가치
- **5**: 다른 모든 directional 전략의 master filter (e.g., HTF EMA200, Funding+OI Combo Regime, MVRV Z-Score, BB Walking).
- **4**: 강력한 secondary filter (e.g., RSI divergence, Volume profile POC, ADX gate, Killzone).
- **3**: 표준 confluence 요소 (e.g., Volume spike, OB+FVG, Fib Golden Pocket).
- **2**: 한정 케이스 confluence (e.g., harmonic D-point, kimchi premium).
- **1**: 단독 시그널, 다른 것과 결합해도 가치 추가 적음 (e.g., Bart 패턴 — pattern 자체가 confluence 거부).

### 1.5 `data_dependency`
- **free**: OHLCV + 거래소 무료 API (Binance/Bybit raw). `CCXT` 만으로 충족.
- **freemium**: Coinglass / DefiLlama / SoSoValue / Farside / alternative.me / TradingView CRYPTOCAP — 무료 tier로 시작 가능, Pro에서 정밀.
- **paid**: Glassnode / CryptoQuant Pro / Hyblock / Nansen / Bookmap — 구독 필수 또는 $29+/월.

---

## 2. Master Priority Table (sorted by composite_score, descending)

| rank | technique | category | auto | rel | crypto | combo | data | composite | rationale |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Funding + OI Combo Regime Filter | crypto-native | 5 | 4 | 5 | 5 | freemium | 19 | `doc 06 §1.12` 모든 directional 전략의 master filter. |
| 2 | MVRV Z-Score Macro Filter | crypto-native | 5 | 4 | 5 | 5 | freemium | 19 | `doc 06 §2.3` BMPro 무료, bias gate로 모든 signal에 confluence. |
| 3 | Funding Rate Extreme MR (long-side overcrowding) | crypto-native | 5 | 4 | 5 | 4 | freemium | 18 | `doc 06 §1.1` Coinglass 무료, perp 특유 자가청산 메커. |
| 4 | BB Walking (negative filter) | filter | 4 | 4 | 5 | 5 | free | 18 | `doc 04 §12` 평균회귀 진입의 master kill-switch. |
| 5 | ADX(14) > 25 trend strength gate | filter | 5 | 4 | 4 | 5 | free | 18 | `doc 05 §7` Wilder 원전, 모든 trend/MR 토글의 표준 gate. |
| 6 | HTF EMA200 trend filter (Daily) | filter | 5 | 4 | 4 | 5 | free | 18 | `doc 05 §19.B` 모든 entry의 1순위 bias filter. |
| 7 | Donchian System 2 (55/20) Turtle | breakout | 5 | 4 | 4 | 4 | free | 17 | `doc 03 §5.2`/`doc 03 §16` 최상위 자동화 적합. Long-only on BTC/ETH validated. |
| 8 | Larry Williams Volatility Breakout (K=0.5) | breakout | 5 | 4 | 4 | 4 | free | 17 | `doc 03 §9` 한국 커뮤니티 검증, daily anchor만 정하면 1줄 룰. |
| 9 | Inverse Head & Shoulders | chart-pattern | 3 | 5 | 4 | 5 | free | 17 | `doc 02 §4.2` Bulkowski 83% / +38% — Tier 1 최강 reversal. |
| 10 | Rectangle Top Breakout | chart-pattern | 4 | 5 | 4 | 4 | free | 17 | `doc 02 §8` Bulkowski 85% bull / +51% — 박스 돌파의 Tier 1. |
| 11 | Double Bottom (Eve&Eve) | chart-pattern | 4 | 5 | 4 | 4 | free | 17 | `doc 02 §5.2` Bulkowski 78% / 88% bull — Tier 1. |
| 12 | Connors RSI(2) (Daily, SMA200 filter) | mean-reversion | 5 | 4 | 4 | 4 | free | 17 | `doc 04 §16` 명시적 룰셋, BTC daily 검증. |
| 13 | TTM Squeeze Fired | breakout | 4 | 4 | 4 | 5 | free | 17 | `doc 03 §7.2` momentum direction까지 결정. 4H/1D 모두 강함. |
| 14 | ATH Breakout (1D, weekly close) | breakout | 5 | 4 | 4 | 4 | free | 17 | `doc 03 §11`/`doc 03 §16` 4번째 자동화 적합. blue-sky momentum. |
| 15 | NUPL Sentiment Phase | crypto-native | 5 | 3 | 5 | 4 | freemium | 17 | `doc 06 §2.4` Capitulation/Euphoria 5-phase 구분. |
| 16 | Realized Price Trend Filter | crypto-native | 5 | 3 | 5 | 4 | paid | 17 | `doc 06 §2.6` 단순 bias gate. price < RP = bottom zone. |
| 17 | OI + Price Divergence | crypto-native | 5 | 3 | 5 | 4 | freemium | 17 | `doc 06 §1.4` 4-quadrant 분류로 microstructure 명확. |
| 18 | BTC.D Rotation (alt timing) | crypto-native | 5 | 3 | 5 | 4 | free | 17 | `doc 06 §3.4` 모든 alt 전략의 macro gate. |
| 19 | ETF Net Flow 5d Cumulative | crypto-native | 5 | 3 | 5 | 4 | freemium | 17 | `doc 06 §2.11` Farside/SoSoValue 무료, 2024+ dominant driver. |
| 20 | F&G Index Extreme Contrarian | crypto-native | 5 | 3 | 5 | 4 | free | 17 | `doc 06 §3.1` alternative.me JSON 무료. |
| 21 | USDT.D Inverse Signal | crypto-native | 5 | 3 | 5 | 4 | free | 17 | `doc 06 §3.9` BTC와 강한 inverse 상관. |
| 22 | ETH/BTC Ratio Rotation | crypto-native | 5 | 3 | 5 | 4 | free | 17 | `doc 06 §4.10` altseason leading. |
| 23 | Spot Volume / Perp Volume Ratio | crypto-native | 5 | 3 | 5 | 4 | freemium | 17 | `doc 06 §4.5` 추세 sustainability 필터. |
| 24 | Realized Volatility Regime | crypto-native | 5 | 3 | 5 | 4 | freemium | 17 | `doc 06 §4.11` Deribit DVOL or 직접 계산. |
| 25 | OI Spike + Price Stagnation | crypto-native | 5 | 3 | 5 | 4 | freemium | 17 | `doc 06 §4.4` compressed energy → breakout follow. |
| 26 | Weekend Volatility Pattern (size 0.5×) | filter | 5 | 3 | 5 | 4 | free | 17 | `doc 06 §3.8` 단순 시간 게이트. |
| 27 | Bull Flag | chart-pattern | 4 | 4 | 4 | 4 | free | 16 | `doc 02 §7.1` Tier 2 ~70% bull — flagpole 측정 단순. |
| 28 | Falling Wedge | chart-pattern | 3 | 5 | 4 | 4 | free | 16 | `doc 02 §2.2` Tier 1 ~74% — RSI div 결합 시 최강. |
| 29 | Liquidity Sweep + MSS (ICT 핵심 자동화) | ict-smc | 3 | 3 | 5 | 5 | free | 16 | `doc 01 §3.3 + §4.3` BSL/SSL pivot + close-break 검출 가능. |
| 30 | Supertrend (ATR(10)×3) | trend | 5 | 3 | 4 | 4 | free | 16 | `doc 05 §5` line이 stop 역할 겸함. ADX gate 필수. |
| 31 | Golden Cross / Death Cross (50/200 SMA, daily) | trend | 5 | 3 | 4 | 4 | free | 16 | `doc 05 §1` Quantified 33회 backtest — bias-only. |
| 32 | EMA Stack 8/13/21/55 (Fib) | trend | 5 | 3 | 4 | 4 | free | 16 | `doc 05 §2` 다중 EMA 정렬 confirmation, GMMA 변형 가능. |
| 33 | RSI Divergence (Regular, 4H+) | mean-reversion | 3 | 4 | 4 | 5 | free | 16 | `doc 04 §2` Cardwell 체계화. confluence layer로 활용. |
| 34 | MACD Signal Cross + Histogram | trend | 5 | 3 | 4 | 4 | free | 16 | `doc 05 §3` 12/26/9 default, zero-line 위 진입 강함. |
| 35 | Linear Regression Slope + R² | trend | 5 | 3 | 4 | 4 | free | 16 | `doc 05 §14` slope/R² 정량 — strength gate 우수. |
| 36 | Z-score Mean Reversion (lookback 50) | mean-reversion | 5 | 3 | 4 | 4 | free | 16 | `doc 04 §10` ADF/Hurst 검증 가능, 통계적으로 가장 엄밀. |
| 37 | NR7 / NR4-Inside-Bar Breakout | breakout | 5 | 3 | 4 | 4 | free | 16 | `doc 03 §12` Linda Raschke 원전, 1줄 룰. |
| 38 | VWAP Mean Reversion (intraday, 00:00 UTC) | mean-reversion | 4 | 3 | 4 | 5 | free | 16 | `doc 04 §7` institutional fair value, daily reset. |
| 39 | Bollinger %B + RSI Combo | mean-reversion | 5 | 3 | 4 | 4 | free | 16 | `doc 04 §5` dual confirmation으로 false signal 감소. |
| 40 | Liquidation Cascade Tape Reading | crypto-native | 4 | 3 | 5 | 4 | freemium | 16 | `doc 06 §4.1` $200M+ 1H spike → reversion long. |
| 41 | CVD Spot/Perp Divergence | crypto-native | 4 | 3 | 5 | 4 | freemium | 16 | `doc 06 §1.7` aggressor flow vs price 어긋남. |
| 42 | Stablecoin Supply Expansion (Dry Powder) | crypto-native | 4 | 3 | 5 | 4 | freemium | 16 | `doc 06 §2.2` DefiLlama 무료, 매수 자금 proxy. |
| 43 | Coinbase Premium Index | crypto-native | 5 | 3 | 5 | 3 | freemium | 16 | `doc 06 §3.2` 직접 계산 가능 (CCXT BTC-USD - BTC-USDT). |
| 44 | Puell Multiple | crypto-native | 5 | 3 | 5 | 3 | freemium | 16 | `doc 06 §2.7` BMPro 무료, miner cycle. |
| 45 | Exchange Netflow Reversal | crypto-native | 4 | 3 | 5 | 4 | freemium | 16 | `doc 06 §2.1` 7d window, ETF wallet noise 주의. |
| 46 | Estimated Leverage Ratio (ELR) | crypto-native | 4 | 3 | 5 | 4 | paid | 16 | `doc 06 §1.11` deleveraging 충격 예측. |
| 47 | Long/Short Ratio Extreme (Top + Global) | crypto-native | 5 | 3 | 5 | 3 | freemium | 16 | `doc 06 §1.6` Binance API 무료. retail vs smart. |
| 48 | Spot-Perp Cash & Carry Basis | crypto-native | 5 | 4 | 5 | 2 | freemium | 16 | `doc 06 §1.3` market-neutral carry. ETF era 우세. |
| 49 | Top Trader Position Ratio Divergence | crypto-native | 4 | 3 | 5 | 4 | freemium | 16 | `doc 06 §4.2` Binance API 무료. |
| 50 | TOTAL3 / OTHERS.D | crypto-native | 5 | 2 | 5 | 4 | free | 16 | `doc 06 §3.5` altseason late-phase warning. |
| 51 | Options Skew (Deribit) | crypto-native | 4 | 3 | 5 | 4 | freemium | 16 | `doc 06 §3.11` 25-delta skew 정량. |
| 52 | Halving Cycle Macro Position | crypto-native | 5 | 2 | 5 | 4 | free | 16 | `doc 06 §3.6` 2024+ ETF로 cycle 약화 가능성. |
| 53 | Funding Reset After Cascade | crypto-native | 4 | 3 | 5 | 4 | freemium | 16 | `doc 06 §4.7` cascade + funding reset 결합. |
| 54 | Aggregate OI ATH Warning | crypto-native | 5 | 2 | 5 | 4 | freemium | 16 | `doc 06 §4.9` deleveraging 임박 risk-off filter. |
| 55 | HODL Waves (1Y+ supply) | crypto-native | 5 | 3 | 5 | 3 | freemium | 16 | `doc 06 §4.3` BMPro 무료. macro filter only. |
| 56 | Inverse Head & Shoulders (재확인) | chart-pattern | 3 | 5 | 4 | 5 | free | 17 | duplicate-of-9 — see rank 9 |
| 57 | Triple Bottom | chart-pattern | 4 | 4 | 4 | 3 | free | 15 | `doc 02 §5.3` ~74% Tier 2. 빈도 낮음. |
| 58 | Cup and Handle | chart-pattern | 3 | 4 | 4 | 4 | free | 15 | `doc 02 §6.1` Tier 1 65–70%, V-cup 구분 어려움. |
| 59 | H&S Top | chart-pattern | 3 | 4 | 4 | 4 | free | 15 | `doc 02 §4.1` Tier 2 ~81% confirmed, throwback 68%. |
| 60 | Ascending Triangle | chart-pattern | 4 | 4 | 4 | 3 | free | 15 | `doc 02 §1.1` Tier 2 ~70% bull. |
| 61 | Descending Triangle | chart-pattern | 4 | 4 | 4 | 3 | free | 15 | `doc 02 §1.2` 64% bear breakout. |
| 62 | Bear Flag | chart-pattern | 4 | 3 | 4 | 4 | free | 15 | `doc 02 §7.2` ~67% in bear. funding squeeze 위험. |
| 63 | Wyckoff Spring | mean-reversion | 3 | 4 | 4 | 4 | free | 15 | `doc 04 §15.1` TR low sweep + reclaim — phase C 진입. |
| 64 | Wyckoff UTAD (Distribution) | mean-reversion | 3 | 4 | 4 | 4 | free | 15 | `doc 04 §15.2` Spring의 mirror. |
| 65 | Bollinger Squeeze (basic) | breakout | 5 | 3 | 4 | 3 | free | 15 | `doc 03 §7.1` width percentile 기반 단순 룰. |
| 66 | Keltner Channel Trend Riding | trend | 4 | 3 | 4 | 4 | free | 15 | `doc 05 §16` ADX gate 필수. |
| 67 | Pairs Trading (BTC/ETH spread) | mean-reversion | 4 | 4 | 4 | 3 | free | 15 | `doc 04 §11` cointegration 검증 가능, market-neutral. |
| 68 | EMA Pullback Entry (uptrend) | mean-reversion | 4 | 3 | 4 | 4 | free | 15 | `doc 04 §6` 추세 방향만 진입 — semi-trend-following. |
| 69 | Premium/Discount Zone (Fib 0.5) | ict-smc | 5 | 2 | 4 | 4 | free | 15 | `doc 01 §5.1` HTF impulse 0.5 기준 — 단순. |
| 70 | RSI(14) OB/OS (75/25 crypto) | mean-reversion | 5 | 3 | 4 | 3 | free | 15 | `doc 04 §1` 단독은 약함, BB walking 필터 필수. |
| 71 | MACD Divergence | mean-reversion | 4 | 3 | 4 | 4 | free | 15 | `doc 04 §3` 4H/Daily에서 강함. lagging. |
| 72 | Bollinger Band Reversion (Robust) | mean-reversion | 4 | 3 | 4 | 4 | free | 15 | `doc 04 §4.2` Naive 4.1은 catastrophic. |
| 73 | Ichimoku Cloud (Strong setup) | trend | 4 | 3 | 4 | 4 | free | 15 | `doc 05 §4` 5-line confluence, Kumo above/below 분류. |
| 74 | KAMA (10/2/30) | trend | 5 | 3 | 4 | 3 | free | 15 | `doc 05 §11` ER>0.3 게이트로 chop 회피. |
| 75 | HH/HL Structure (Dow Theory) | trend | 4 | 3 | 4 | 4 | free | 15 | `doc 05 §17` swing detector 정의 의존. |
| 76 | Inside Bar Breakout | breakout | 5 | 3 | 4 | 3 | free | 15 | `doc 03 §12.1` mother bar 양쪽 break trigger. |
| 77 | Liquidation Heatmap Magnet | crypto-native | 3 | 3 | 5 | 4 | freemium | 15 | `doc 06 §1.5` cluster 식별 알고. Hyblock 정밀. |
| 78 | Hash Ribbon | crypto-native | 4 | 3 | 5 | 3 | freemium | 15 | `doc 06 §2.8` 14 buy signals, 64% win — low frequency. |
| 79 | SOPR (STH-SOPR 1.0 cross) | crypto-native | 4 | 3 | 5 | 3 | paid | 15 | `doc 06 §2.5` STH<155일, Glassnode Standard 필요. |
| 80 | Spot Taker Buy/Sell Ratio | crypto-native | 4 | 3 | 5 | 3 | paid | 15 | `doc 06 §4.12` CryptoQuant Pro. |
| 81 | Stablecoin Exchange Reserve | crypto-native | 4 | 3 | 5 | 3 | paid | 15 | `doc 06 §4.8` CryptoQuant. |
| 82 | Volume Profile VAH/VAL/POC | breakout | 3 | 3 | 4 | 4 | free | 14 | `doc 03 §13` POC acceptance/rejection — confluence layer. |
| 83 | Anchored VWAP (event-anchored) | trend | 3 | 3 | 4 | 4 | free | 14 | `doc 05 §9` halving/ATH/ATL anchor → multi-AVWAP confluence. |
| 84 | HMA (16) slope flip | trend | 5 | 2 | 4 | 3 | free | 14 | `doc 05 §12` Hull 권장. crossover는 비추. |
| 85 | ALMA (9/0.85/6) | trend | 5 | 2 | 4 | 3 | free | 14 | `doc 05 §13` Gaussian weighted. responsive. |
| 86 | Stochastic %K/%D Reversal | mean-reversion | 5 | 3 | 3 | 3 | free | 14 | `doc 04 §8` 14/3/3 standard. embedded stoch 회피 필요. |
| 87 | Williams %R Reversal (zone exit) | mean-reversion | 5 | 3 | 3 | 3 | free | 14 | `doc 04 §13` -80/-20 cross trigger. |
| 88 | CCI ±200 Extreme | mean-reversion | 5 | 3 | 3 | 3 | free | 14 | `doc 04 §9` Lambert 원전, ±200 crypto 권장. |
| 89 | Fibonacci Golden Pocket (0.618–0.65) | mean-reversion | 3 | 3 | 4 | 4 | free | 14 | `doc 04 §14` HTF impulse 식별 후 confluence layer. |
| 90 | ORB (NY 13:30 UTC) | breakout | 4 | 3 | 4 | 3 | free | 14 | `doc 03 §6` US session ORB가 가장 신뢰. |
| 91 | Horizontal S/R Breakout | breakout | 3 | 3 | 4 | 4 | free | 14 | `doc 03 §1.1` pivot clustering 알고리즘 필요. |
| 92 | Round Number Breakout (BTC $10k) | breakout | 4 | 3 | 4 | 3 | free | 14 | `doc 03 §10` 0.5% 버퍼 + retest 필수. |
| 93 | Range/Box Trade | mean-reversion | 4 | 3 | 4 | 3 | free | 14 | `doc 03 §4` ADX<20 게이트 필수. |
| 94 | Ascending Channel mean-reversion | chart-pattern | 4 | 3 | 4 | 3 | free | 14 | `doc 02 §3.1` touch≥4 필수. |
| 95 | Descending Channel | chart-pattern | 4 | 3 | 4 | 3 | free | 14 | `doc 02 §3.2` ascending mirror. |
| 96 | Triple Top | chart-pattern | 4 | 3 | 4 | 3 | free | 14 | `doc 02 §5.3` 출처별 41–88% 편차. |
| 97 | Fair Value Gap (FVG, 단독) | ict-smc | 4 | 2 | 4 | 4 | free | 14 | `doc 01 §2` 3-bar imbalance 기계적 검출 가능. |
| 98 | Inversion FVG (IFVG) | ict-smc | 4 | 2 | 4 | 4 | free | 14 | `doc 01 §2.3` close-beyond 기준 명확. |
| 99 | BOS (Break of Structure) | ict-smc | 4 | 2 | 4 | 4 | free | 14 | `doc 01 §4.1` swing point + close-break. |
| 100 | CHOCH (Change of Character) | ict-smc | 4 | 2 | 4 | 4 | free | 14 | `doc 01 §4.2` swing point detector 의존. |
| 101 | SMT Divergence (BTC/ETH) | ict-smc | 4 | 2 | 4 | 4 | free | 14 | `doc 01 §8` rolling correlation 0.7+ 게이트. |
| 102 | Equal Highs/Lows (EQH/EQL) | ict-smc | 5 | 2 | 4 | 3 | free | 14 | `doc 01 §3.4` ≤0.1% tolerance 명시. |
| 103 | PSAR (trailing stop only) | trend | 5 | 2 | 4 | 3 | free | 14 | `doc 05 §6` Wilder. always-in chop. |
| 104 | DEMA / TEMA Cross | trend | 5 | 2 | 4 | 3 | free | 14 | `doc 05 §15` reduced lag = increased noise. |
| 105 | Active Address Network Growth | crypto-native | 4 | 2 | 5 | 3 | paid | 14 | `doc 06 §2.9` Glassnode, L2 noise 주의. |
| 106 | Miner Outflow Spike | crypto-native | 4 | 2 | 5 | 3 | paid | 14 | `doc 06 §2.10` CryptoQuant Pro 필요. |
| 107 | Funding Cross-Exchange Arb | crypto-native | 4 | 4 | 5 | 1 | freemium | 14 | `doc 06 §1.2` 자금이동 가능성, counterparty risk. |
| 108 | Kimchi Premium | crypto-native | 4 | 2 | 5 | 3 | free | 14 | `doc 06 §3.3` capital control로 mean revert 안 함. |
| 109 | OI USD vs Coin-margined Split | crypto-native | 4 | 2 | 5 | 3 | freemium | 14 | `doc 06 §3.10` reflexive risk indicator. |
| 110 | Aggregate Spot Inflow Rejection | crypto-native | 4 | 2 | 5 | 3 | paid | 14 | `doc 06 §4.6` panic flush 종료. |
| 111 | GBTC/ETF Discount/Premium | crypto-native | 4 | 2 | 5 | 3 | freemium | 14 | `doc 06 §3.12` 현재는 weak signal. |
| 112 | Trendline Breakout | breakout | 3 | 3 | 4 | 3 | free | 13 | `doc 03 §2` pivot-slope 정의 노이지. |
| 113 | ORB (15-min, UTC 00:00) | breakout | 4 | 3 | 3 | 3 | free | 13 | `doc 03 §6` anchor 의존, weekend 조심. |
| 114 | Symmetrical Triangle | chart-pattern | 3 | 3 | 4 | 3 | free | 13 | `doc 02 §1.3` ~54% directional — Tier 3. |
| 115 | Pennant | chart-pattern | 3 | 3 | 4 | 3 | free | 13 | `doc 02 §7.3` ~62–65%, flag와 유사. |
| 116 | Inverse Cup and Handle | chart-pattern | 3 | 3 | 4 | 3 | free | 13 | `doc 02 §6.2` 통계 부족, ~60%. |
| 117 | Diamond Bottom | chart-pattern | 2 | 4 | 4 | 3 | free | 13 | `doc 02 §10` 73–74% but 빈도 매우 낮음. |
| 118 | Order Block (단독, ICT) | ict-smc | 3 | 2 | 4 | 4 | free | 13 | `doc 01 §1` lookback 민감, freshness 추적 필요. |
| 119 | Asian Range Sweep | ict-smc | 3 | 2 | 4 | 4 | free | 13 | `doc 01 §9.2` daily anchor 분명, BTC에서 자주 작동. |
| 120 | OTE + Sweep Combo | ict-smc | 3 | 2 | 4 | 4 | free | 13 | `doc 01 §9.4` Fib 0.62–0.79 + LTF MSS. |
| 121 | Killzone Time Filter | filter | 5 | 2 | 2 | 4 | free | 13 | `doc 01 §6` UTC 시간 매칭만. forex 가정 약함. |
| 122 | Heikin-Ashi Smoothing | trend | 4 | 2 | 4 | 3 | free | 13 | `doc 05 §10` HA close ≠ real close 주의. |
| 123 | Ehlers Fisher Transform | trend | 4 | 2 | 4 | 3 | free | 13 | `doc 05 §18` oscillator counter-trend. |
| 124 | CME Bitcoin Gap Fill | crypto-native | 4 | 3 | 3 | 3 | free | 13 | `doc 06 §3.7` 77% fill, 2026 CME 24/7로 폐기 예정. |
| 125 | Internal vs External Structure | ict-smc | 3 | 2 | 4 | 3 | free | 12 | `doc 01 §4.4` lookback 50 vs 10 분리 — confluence. |
| 126 | Silver Bullet (NY AM 10–11) | ict-smc | 3 | 2 | 3 | 4 | free | 12 | `doc 01 §9.1` 시간 윈도우 + sweep + MSS + FVG 다단계. |
| 127 | Judas Swing (London open) | ict-smc | 3 | 2 | 3 | 4 | free | 12 | `doc 01 §9.3` London open 의존, 크립토 약화. |
| 128 | Power of 3 (PO3, daily) | ict-smc | 3 | 2 | 4 | 3 | free | 12 | `doc 01 §7` Asia/London/NY 3단계 의존. |
| 129 | Breaker Block | ict-smc | 3 | 2 | 4 | 3 | free | 12 | `doc 01 §1.3` sweep 선행 조건 추적. |
| 130 | Whale Wallet Tracking | crypto-native | 2 | 2 | 5 | 3 | paid | 12 | `doc 06 §1.9` Nansen labeling 오류 위험. |
| 131 | Footprint Absorption / Exhaustion | crypto-native | 1 | 3 | 5 | 3 | paid | 12 | `doc 06 §1.8` Bookmap 필요, OHLCV로 미흡. |
| 132 | Rising Wedge (downside) | chart-pattern | 3 | 1 | 4 | 3 | free | 11 | `doc 02 §2.1` 49% — Bulkowski rank 36/36 worst. |
| 133 | Diamond Top | chart-pattern | 2 | 2 | 4 | 3 | free | 11 | `doc 02 §10` 54% — Tier 3. |
| 134 | Broadening (Megaphone) | chart-pattern | 3 | 2 | 4 | 2 | free | 11 | `doc 02 §11` rank 25/39. busted trade가 그나마 낫다. |
| 135 | Rounding Bottom (Saucer) | chart-pattern | 2 | 3 | 3 | 3 | free | 11 | `doc 02 §9.1` 8.5개월 평균 — weekly 전용. |
| 136 | ABCD Harmonic | chart-pattern | 3 | 2 | 3 | 2 | free | 10 | `doc 02 §12.1` 가장 단순한 harmonic. |
| 137 | Gartley Pattern | chart-pattern | 2 | 3 | 3 | 2 | free | 10 | `doc 02 §12.3` ~70% on daily, well-formed. |
| 138 | Bat Pattern | chart-pattern | 2 | 3 | 3 | 2 | free | 10 | `doc 02 §12.4` ~65–70% with tight SL. |
| 139 | Butterfly Pattern | chart-pattern | 2 | 3 | 3 | 2 | free | 10 | `doc 02 §12.5` ~65% daily, overshoot reversal. |
| 140 | Mitigation Block | ict-smc | 3 | 1 | 4 | 2 | free | 10 | `doc 01 §1.4` Breaker보다 약함. 단독 비추. |
| 141 | Bart Pattern Counter-Trade | crypto-native | 2 | 2 | 5 | 1 | free | 10 | `doc 06 §1.10` 후행 confirm — R 비대칭. |
| 142 | Rounding Top | chart-pattern | 2 | 2 | 3 | 2 | free | 9 | `doc 02 §9.2` ~60%. 시간 길어 patience 요구. |
| 143 | Three Drives | chart-pattern | 2 | 1 | 3 | 2 | free | 8 | `doc 02 §12.2` 통계 부족, anecdotal — defer. |
| 144 | CISD (ICT 후기 컨셉) | ict-smc | 2 | 1 | 3 | 2 | free | 8 | `doc 01 §16` 자료 부족, mentorship transcript 필요. |
| 145 | NWOG / NDOG (Crypto opening gap) | ict-smc | 3 | 1 | 2 | 2 | free | 8 | `doc 01 §16` 24/7로 forex 전용 — skip. |
| 146 | Quarterly Theory (ICT 90분 모델) | ict-smc | 1 | 1 | 3 | 2 | free | 7 | `doc 01 §16` 검증 자료 부재 — skip. |
| 147 | IPDA (ICT 메타 가설) | ict-smc | 1 | 1 | 3 | 1 | free | 6 | `doc 01 §16` 검증 불가능한 메타 컨셉 — skip. |

---

## 3. Top 30 Picks for First-Wave Automation

### 3.1 Trend-Following Foundation (7 picks)

1. **Donchian System 2 (55-day entry / 20-day exit)** — `composite 17`. 1줄 룰 + ATR sizing으로 즉시 구현 가능. **Data**: free OHLCV. **Failure mode**: chop 시 연속 fakeout — `ADX(14) > 25` + `EMA200` filter로 활성/비활성 토글 필수.
2. **Supertrend (ATR(10) × 3)** — `composite 16`. line이 trailing stop 역할까지 — entry+exit 동시 솔루션. **Data**: free. **Failure mode**: sideways death-by-1000-cuts. `ADX > 25` gate 필수; multiplier ≤2 금지.
3. **Golden Cross (50/200 SMA daily)** — `composite 16`. macro bias-only 시그널. **Data**: free. **Failure mode**: 200일 SMA의 lag으로 cycle top 직후 death cross 빈발 — 단독 entry 금지, weekly Ichimoku confirmation과 결합.
4. **EMA Stack 8/13/21/55 (Fib)** — `composite 16`. 다중 EMA 정렬 시각·정량 검증 가능. **Data**: free. **Failure mode**: ribbon compression 시 (width/close < 0.5%) entry 보류 (chop 위험).
5. **MACD (12/26/9) Signal Cross + Histogram** — `composite 16`. signal/zero/histogram 3단계 entry 신호 분리. **Data**: free. **Failure mode**: zero line 근처 whipsaw — `MACD > 0` + `EMA(50)` filter.
6. **Linear Regression Slope + R²(20)** — `composite 16`. trend strength를 통계적으로 정량 (slope sign + R² > 0.7). **Data**: free. **Failure mode**: outlier 1개에 slope 왜곡 — log-price 사용 권장.
7. **Anchored VWAP (event-anchored at halving / ATH / ATL)** — `composite 14`. multi-AVWAP confluence가 institutional cost basis cluster. **Data**: free. **Failure mode**: anchor selection bias로 hindsight overfit — 미리 정한 anchor 목록만 사용.

### 3.2 Mean-Reversion Foundation (7 picks)

1. **Connors RSI(2) (Daily, SMA200 filter)** — `composite 17`. 명시적 룰셋, BTC daily 검증. **Data**: free. **Failure mode**: long-duration bear (2018, 2022)에선 SMA200 위 조건 거의 안 잡힘 — trade 빈도 낮음, hard -5% SL 추가 권장.
2. **Z-score Mean Reversion (Z<-2 / Z>+2, lookback 50)** — `composite 16`. 통계적으로 가장 엄밀, ADF/Hurst로 stationarity 검증 가능. **Data**: free. **Failure mode**: regime shift 시 mean drift — rolling p-value 매주 < 0.05 유지 확인.
3. **Bollinger %B + RSI Combo** — `composite 16`. dual confirmation으로 false signal 감소. **Data**: free. **Failure mode**: trending market에서 %B>1 5+ bars 머무름 — `BB walking` filter 결합 필수.
4. **VWAP Mean Reversion (intraday, UTC 00:00 anchor)** — `composite 16`. institutional fair value benchmark. **Data**: free. **Failure mode**: trend day(±5%+ move) 시 회귀 안 함 — 1H ADX>25면 비활성.
5. **RSI Divergence (Regular, 4H/Daily)** — `composite 16`. Cardwell 체계화된 분석법. **Data**: free. **Failure mode**: triple divergence 시 강추세 신호 — 같은 방향 3+ 연속 발생 시 진입 금지.
6. **Pairs Trading (BTC/ETH spread Z-score)** — `composite 15`. market-neutral, 시장 방향 무관 alpha. **Data**: free. **Failure mode**: cointegration breakdown — rolling ADF p-value 매주 재검증, p>0.05면 즉시 unwind.
7. **EMA Pullback Entry (uptrend, EMA20/50 bounce)** — `composite 15`. semi-trend-following hybrid. **Data**: free. **Failure mode**: 추세 끝물 first break 후 false bounce → trend 반전. `RSI > 40` + bullish reversal candle 필수.

### 3.3 Breakout Foundation (7 picks)

1. **Larry Williams Volatility Breakout (K=0.5, daily)** — `composite 17`. 한국 커뮤니티 검증 + 1줄 룰. **Data**: free. **Failure mode**: gap-down day의 target_long hit → bull trap. `MA(20, 1d)` filter 필수, K를 노이즈 비율로 동적 조정.
2. **TTM Squeeze Fired (BB inside KC → fire + momentum direction)** — `composite 17`. 방향까지 결정. **Data**: free. **Failure mode**: 짧은 squeeze (<6 bars) 후 fire는 noise — min squeeze duration 검증.
3. **NR7 / NR4-Inside-Bar Breakout** — `composite 16`. Linda Raschke 원전, 1줄 룰. **Data**: free. **Failure mode**: 2개 연속 NR7 → 좁아지는 wedge로 비추세 — 1회 NR7만 trigger.
4. **ATH Breakout (Daily, 2% buffer + weekly close confirm)** — `composite 17`. blue-sky momentum. **Data**: free. **Failure mode**: "double top fakeout" (2021/11 BTC $69k) — chandelier exit (highest_high(22) - 3×ATR(22)) 적용.
5. **ORB (NY 13:30 UTC, 30-min)** — `composite 14`. US session institutional flow. **Data**: free. **Failure mode**: OR range < 0.5×ATR이면 noise — 너무 좁은 OR skip.
6. **Bollinger Squeeze + Volume × 1.5** — `composite 15`. width percentile 기반 단순. **Data**: free. **Failure mode**: 양방향 fire (first fire 가짜) — momentum direction 또는 retest 확인 필요.
7. **Inside Bar Breakout (Mother bar 양쪽)** — `composite 15`. 단순 trigger. **Data**: free. **Failure mode**: "inside bar fake" — HTF EMA50 trend 일치할 때만 진입.

### 3.4 Crypto-Native Edges (7 picks)

1. **Funding + OI Combo Regime Filter** — `composite 19`. 모든 directional 전략의 master filter. **Data**: Coinglass freemium. **Failure mode**: regime 전환 구간에서 false readings — 7d MA로 smoothing.
2. **MVRV Z-Score Macro Filter** — `composite 19`. macro bias gate. **Data**: BMPro freemium. **Failure mode**: 2024+ ETF era에 MVRV ceiling이 과거보다 낮을 수 있음 (structural shift) — single-cycle calibration 갱신 필요.
3. **Funding Rate Extreme MR (long-side overcrowding)** — `composite 18`. perp 자가청산 메커니즘. **Data**: Coinglass/Binance 무료. **Failure mode**: ETF 강세장 (2024–25) tailwind에서 funding 0.1%+ 며칠 유지 — `BTC.D + spot inflow` 게이트로 보완.
4. **BTC.D Rotation Gate (alt long bias)** — `composite 17`. macro rotation timing. **Data**: TradingView 무료. **Failure mode**: stablecoin 발행이 BTC.D 흐림 — `USDT.D` 동시 모니터링.
5. **OI + Price Divergence (4-quadrant)** — `composite 17`. microstructure 시그널. **Data**: Coinglass 무료. **Failure mode**: USDT vs Coin-margined OI 분리 안 하면 lag 발생 — split metric 사용.
6. **F&G Index Extreme Contrarian (<15 long bias / >85 short bias)** — `composite 17`. **Data**: alternative.me 무료 JSON. **Failure mode**: 강한 추세장에서 Extreme이 수 주 지속 — single-day trigger 금지, 3 consecutive days 요구.
7. **Liquidation Cascade Tape Reading ($200M+ 1H spike)** — `composite 16`. **Data**: Coinglass 무료. **Failure mode**: news-driven cascade (거래소 default)는 회복 안 함 — major(BTC/ETH)에서만, news calendar 회피.

### 3.5 Confluence Filters (5 picks — 단독 entry 아님, 다른 시그널의 가중치 또는 게이트)

1. **HTF EMA200 Trend Filter (Daily)** — `composite 18`. 모든 entry의 1순위 bias filter. **Data**: free. **Use as**: directional bias gate (long/short/disabled).
2. **ADX(14) > 25 Trend Strength Gate** — `composite 18`. trend vs MR regime 토글. **Data**: free. **Use as**: trend 전략 활성, MR 전략 비활성 (또는 vice versa).
3. **BB Walking Detector (negative filter)** — `composite 18`. 평균회귀 진입의 master kill-switch. **Data**: free. **Use as**: walking detected → 모든 reversal 시그널 비활성화 (`doc 04 §12`).
4. **Killzone Time Filter (UTC bins)** — `composite 13`. London/NY-AM/NY-PM/Asia 분류. **Data**: free. **Use as**: ICT/SMC entry에 시간 게이트, 또는 weekend 사이즈 0.5× (`doc 06 §3.8`).
5. **Volume Profile POC/VAH/VAL Confluence** — `composite 14`. price acceptance/rejection zone. **Data**: free. **Use as**: 다른 entry signal이 POC에서 발생 시 confluence +1 가중치.

---

## 4. Bottom Tier — Defer or Skip (composite ≤ 11 또는 명시적 anecdotal-only)

| Technique | Score | Reason |
|---|---|---|
| Three Drives | 8 | `doc 02 §12.2` Bulkowski 통계 부족, anecdotal-only. Defer. |
| CISD (Change in State of Delivery) | 8 | `doc 01 §16` ICT 후기 자료 흩어져 있음, mentorship transcript 필요. Defer. |
| Quarterly Theory (ICT 90분) | 7 | `doc 01 §16` 검증 자료 부재. Skip until validated. |
| IPDA | 6 | `doc 01 §16` 검증 불가능한 메타-개념. Skip. |
| NWOG / NDOG (forex gap models) | 8 | `doc 01 §16` 24/7 크립토 부적합. Skip. |
| Bart Pattern Counter-Trade | 10 | `doc 06 §1.10` 후행 confirm으로 R 비대칭. Defer until pattern detector 정밀화. |
| Mitigation Block (단독) | 10 | `doc 01 §1.4` Breaker보다 본질 약함. Defer; FVG/OTE confluence로만 사용. |
| Rounding Top | 9 | `doc 02 §9.2` ~60% + 8.5개월 길이. Crypto 4H 부적합. Defer to weekly. |
| ABCD / Gartley / Bat / Butterfly Harmonics | 10 | `doc 02 §12` 5-point 그리기가 algo 주관 — overfitting 위험. Defer. |
| Diamond Top | 11 | `doc 02 §10` 54% — Tier 3, 빈도 매우 낮음. Defer. |
| Broadening (Megaphone) | 11 | `doc 02 §11` rank 25/39 — busted trade가 그나마 나음. Defer. |
| Rising Wedge (downside) | 11 | `doc 02 §2.1` 49% — Bulkowski worst rank. Defer; falling wedge만 사용. |
| Rounding Bottom (Saucer) | 11 | `doc 02 §9.1` 8.5개월 평균 — weekly only, swing horizon 길어 우선순위 낮음. |
| Whale Wallet Tracking (Nansen) | 12 | `doc 06 §1.9` Nansen labeling 오류 + copy-trade lag. Defer until sample alpha 검증. |
| Footprint Absorption | 12 | `doc 06 §1.8` Bookmap 필요 — 우리 OHLCV+derivatives 데이터로 결정론적 추출 불가. Skip. |

---

## 5. Data-Source Dependency Map

### 5.1 OHLCV only (cleanest, runs from any exchange API via CCXT)
- **Trend**: Golden/Death Cross, EMA Stack, MACD, Ichimoku, Supertrend, PSAR, KAMA, HMA, ALMA, DEMA/TEMA, Heikin-Ashi, Linear Regression Slope, HH/HL Structure, Fisher Transform.
- **Mean Reversion**: RSI OB/OS, RSI/MACD/Stoch/CCI Divergence, BB Reversion, BB %B+RSI, EMA Pullback, Stochastic, CCI, Williams %R, Z-score, Pairs Trading, Connors RSI(2), Wyckoff Spring/UTAD, Fibonacci Retracement, BB Walking (filter).
- **Breakout**: Donchian (Turtle), LW Volatility (K=0.5), Horizontal S/R, Trendline, Range/Box, ORB, BB Squeeze, TTM Squeeze, Keltner Channel, NR7/NR4-IB, Inside Bar, ATH, Round Number, Fakeout fade.
- **Chart Patterns**: 27개 패턴 모두 (`doc 02`) — IH&S, Double Bottom/Top, Triangles, Wedges, Channels, Cup&Handle, Flags/Pennant, Rectangle, Rounding, Diamond, Broadening, Harmonics.
- **ICT/SMC (자동화 가능 부분)**: Order Block, FVG, IFVG, BOS, CHOCH, MSS, Liquidity Sweep, EQH/EQL, Premium/Discount, OTE, Killzone time filter, Asian Range Sweep, Silver Bullet, Judas Swing, PO3, Internal/External Structure.

### 5.2 OHLCV + Volume Profile / Orderbook (free with TradingView or self-computed)
- Volume Profile POC/VAH/VAL/LVN (`doc 03 §13`)
- Anchored VWAP at events (`doc 05 §9`)
- VWAP intraday MR (`doc 04 §7`)

### 5.3 Funding / OI / Liquidation (Coinglass freemium, Binance/Bybit raw API)
- Funding Rate Extreme MR (`doc 06 §1.1`)
- Funding Cross-Exchange Arb (`doc 06 §1.2`)
- Cash & Carry Basis (`doc 06 §1.3`)
- OI + Price Divergence (`doc 06 §1.4`)
- Liquidation Heatmap Magnet (`doc 06 §1.5`, Hyblock paid 정밀)
- Long/Short Ratio Top + Global (`doc 06 §1.6`)
- CVD Spot/Perp Divergence (`doc 06 §1.7`)
- Funding + OI Combo Regime (`doc 06 §1.12`)
- Liquidation Cascade (`doc 06 §4.1`)
- OI USD vs Coin-margined Split (`doc 06 §3.10`)
- OI Spike + Price Stagnation (`doc 06 §4.4`)
- Funding Reset After Cascade (`doc 06 §4.7`)
- Aggregate OI ATH Warning (`doc 06 §4.9`)
- Top Trader Position Ratio Divergence (`doc 06 §4.2`)
- Spot Volume / Perp Volume Ratio (`doc 06 §4.5`)

### 5.4 On-chain (Glassnode / CryptoQuant — freemium → paid)
- **Free (BMPro / LookIntoBitcoin)**: MVRV Z-Score, NUPL, Puell Multiple, Hash Ribbon, HODL Waves, Realized Price.
- **Paid (Glassnode Standard $29+ / CryptoQuant Pro $39+)**: STH-SOPR, aSOPR, Active Addresses, Exchange Netflow precision, Miner Outflow, Estimated Leverage Ratio, Stablecoin Reserve, Aggregate Spot Inflow, Spot Taker Buy/Sell Ratio.
- **Stablecoin (DefiLlama free)**: Stablecoin Supply Expansion, USDT.D.

### 5.5 Cross-Asset (TradingView CRYPTOCAP 무료, alternative.me, Farside, SoSoValue)
- BTC.D Rotation (`doc 06 §3.4`)
- TOTAL3 / OTHERS.D (`doc 06 §3.5`)
- USDT.D Inverse (`doc 06 §3.9`)
- ETH/BTC Ratio (`doc 06 §4.10`)
- Coinbase Premium (CCXT 직접 계산)
- Kimchi Premium (Upbit + USD/KRW, free)
- F&G Index (alternative.me JSON 무료)
- ETF Net Flow (Farside / SoSoValue 무료)
- Halving Cycle Position (블록 height — mempool.space 무료)
- CME BTC Gap (TradingView CME:BTC1! 무료)
- Realized Volatility (Deribit DVOL, Glassnode paid)
- Options Skew (Deribit Insights free, Coinglass free + paid)

---

## 6. Composite Recipes Worth Replicating

### 6.1 (from `doc 06 §5.1`) "Crowded Long Top" Composite — short bias activation
- funding 7d MA > 0.04% (8h)
- aggregate OI 7d %Δ > +15%
- top global long ratio > 0.65
- F&G > 75
- **Trigger**: 4 중 3+ → 신규 long entry 차단, short bias 활성.
- **Data**: Coinglass free + alternative.me free.
- **Use in StrategyImprover**: regime gate. 모든 long-side entry signal 발화 직전 평가; 충족 시 `signal.skip()`.

### 6.2 (from `doc 06 §5.2`) "Macro Bottom" Composite — spot DCA scale-up
- MVRV Z-Score < 1
- Puell Multiple < 0.6
- 200WMA 부근 또는 아래
- F&G < 20 for 7+ days
- 거래소 netflow 7d 음수
- **Trigger**: 5 중 4+ → spot DCA 활성, swing long 가중치 2×.
- **Data**: BMPro free + alternative.me + CryptoQuant 무료 일부.
- **Use in StrategyImprover**: macro bias multiplier. swing-horizon strategy 활성화.

### 6.3 (from `doc 06 §5.3`) "Altseason Trigger" Composite — alt long bias on
- BTC.D weekly close < 200WMA
- ETH/BTC weekly close > 50WMA cross up
- USDT.D weekly close < 50WMA cross down
- TOTAL3 weekly higher high
- **Trigger**: 4 중 3+ → alt long bias.
- **Data**: TradingView CRYPTOCAP free.
- **Use in StrategyImprover**: alt-asset universe 활성. BTC concentrated bias 해제.

### 6.4 (from `doc 06 §5.4`) "Squeeze Imminent" Composite — bidirectional stop entry
- 1H OI %Δ > +5% with price stagnation (< 0.3% range)
- aggregate liquidation cluster within 2% of price
- funding > 0.03% 또는 < -0.02% (extreme)
- **Trigger**: 3 모두 → 양방향 stop entry order, breakout direction follow.
- **Data**: Coinglass free.
- **Use in StrategyImprover**: pre-event volatility setup. ORB 변형으로 적용.

### 6.5 (NEW) "Trend Continuation Confluence" — high-prob trend re-entry
- HTF Daily EMA200 우상향 (long bias gate)
- ADX(14) > 25 (trend strength gate, `doc 05 §7`)
- 가격이 EMA20 또는 EMA50으로 풀백 (`doc 04 §6`)
- bullish reversal candle (engulfing / pin bar)
- spot taker buy/sell 1H ratio > 1.20 (`doc 06 §4.12`)
- Funding moderate (|funding| < 0.03%, not crowded)
- **Trigger**: 6 중 5+ → trend continuation long. SL = recent HL - 1 ATR.
- **Use**: 추세장에서 평균회귀와 모순되지 않는 pullback re-entry. BB walking detector와 호환.

### 6.6 (NEW) "Liquidity Sweep Reversal" — ICT + crypto-native fusion
- HTF Daily/4H bias clear (HH-HL 또는 LH-LL)
- 직전 swing extreme (BSL 또는 SSL) sweep — wick beyond, close back inside (`doc 01 §3.3`)
- LTF (5m/1m) MSS — close-break of opposite swing + FVG 형성 (`doc 01 §4.3`)
- liquidation cluster within 0.5% of swept extreme (`doc 06 §1.5`)
- volume spike on sweep candle (>1.5× 20-bar avg)
- **Trigger**: 모든 5 만족 → reversal entry at FVG midpoint. SL = sweep wick + 0.2×ATR. TP = opposite liquidity pool, 1:2 RR.
- **Use**: ICT의 가장 자동화 가능한 핵심을 liquidation heatmap으로 강화. Killzone (London/NY-AM) 내 발생 시 +1 confluence.

### 6.7 (NEW) "Volatility-Adjusted Breakout" — regime-aware breakout
- Realized Volatility 30D < 25th percentile (low-vol setup, `doc 06 §4.11`)
- TTM Squeeze ON for ≥ 6 bars (`doc 03 §7.2`)
- Donchian(20) 상단 또는 하단 임박 (within 0.5%)
- HTF Daily EMA200 trend filter
- volume on breakout candle > 1.5× 20-bar avg
- Funding+OI Combo not in "Crowded Long Top" regime
- **Trigger**: 모든 6 → bidirectional stop order. squeeze fire 방향 follow.
- **Use**: low-vol regime에서 high-vol regime 전환 포착. trend 전략과 mean-reversion 토글의 자연스러운 hand-off 지점.

---

## 7. Prompt Budget Note

- **Section 1 (Rubric)**: ~600 토큰
- **Section 2 (Master Table, 147 rows)**: ~6,000 토큰 — `StrategyImprover`가 grep/parse하기 위한 핵심 표
- **Section 3 (Top 30 Narrative)**: ~2,200 토큰
- **Section 4 (Bottom Tier)**: ~400 토큰
- **Section 5 (Data Map)**: ~1,000 토큰
- **Section 6 (Composites)**: ~1,400 토큰
- **Total approximate**: ~11,600 토큰 (≈ 46k 문자, 한글+영문 혼용 기준)

`StrategyImprover` 프롬프트에 본 문서 전체를 inject할 경우, Claude API context budget 200k 기준 ~5.8% 차지. 대부분의 use case에서 **Section 2 + Section 3 + Section 6**(~9,600 토큰)만 inject해도 충분 — Section 1/4/5는 reference로만 보유.

기법 1개 fetch 시 평균 비용: master table 1행(~40 토큰) + source doc reference(~50–200 토큰) = ~250 토큰. `StrategyImprover.generate_idea()`에서 row 5–10개 sample → 1.25k–2.5k 토큰의 candidate pool로 충분.

---

## 8. Ambiguity / Couldn't-Score Notes

다음 기법은 source doc이 점수 산정에 충분한 정보를 제공하지 않거나 정의가 모호해 best-effort 점수를 부여했음:

- **CISD, Quarterly Theory, IPDA** (`doc 01 §16`): ICT가 명시적으로 "검증 자료 부족" 표기 — `reliability=1`, `automation=1–2`로 처리해 매트릭스 하단 고정.
- **NWOG / NDOG**: `doc 01 §16`에서 "forex 자료는 풍부하나 24/7 검증 미진" — 크립토 fit 2로 강등.
- **Whale Wallet Tracking**: source가 "labeling 오류 위험"과 "copy-trading은 후행"을 동시 경고 — alpha 자체가 추출 가능한지 불확실해 `automation=2`로 처리.
- **Footprint Absorption / Exhaustion**: Bookmap 같은 desktop tool이 필요한 데이터 — 우리 OHLCV+derivatives 파이프라인으로 결정론적 추출이 어려워 `automation=1`로 강등.
- **Bart Pattern**: `doc 06 §1.10`의 "패턴 인식이 후행"이라는 자기 비판 — `combo_potential=1`로 처리해 단독 사용 비추천.
- **Triple Top**: `doc 02 §5.3`에서 "출처별 신뢰도 41–88% 편차" — `reliability=3`으로 중도 처리.

> **문서 끝.** 본 우선순위 매트릭스는 source docs (`01-ict-smc.md` ~ `06-crypto-specific.md`)의 사실 인용이며, 실제 trading edge는 backtest로만 검증된다. `StrategyImprover`는 본 표를 **시그널 변형/조합의 출발점**으로만 사용하고, 새 기법은 반드시 walk-forward 백테스트 + paper trading 검증 사이클을 거쳐야 한다.
