# 04. Counter-Trend / Mean Reversion Strategies (역추세 · 평균회귀 전략)

> **목적**: 자동 전략 생성기(automated strategy generator)가 알고리즘으로 변환할 수 있도록, 평균회귀 기법의 시그널 정의·진입/청산 규칙·파라미터·필터·실패 케이스를 정밀하게 정리한다.
>
> **시장 가설(Market hypothesis)**: 가격은 단기적으로 평균(moving average, VWAP, 밴드 중심 등)에서 이탈할 수 있으나, 군중 심리·유동성 공급·시장 메이커의 헤지로 인해 결국 평균으로 회귀(reversion to the mean)하는 경향이 있다. 이 가설이 깨지는 구간이 **강추세(strong trend) regime**이며, 평균회귀 전략의 최대 적이다.
>
> **크립토 특수성**:
> - 24/7 시장 → "장 마감 후 갭 회귀" 같은 주식형 효과는 없음
> - 변동성(volatility)이 주식·외환 대비 2-5배 → 표준 임계치(RSI 30/70)는 신호가 너무 잦음 → 20/80 또는 25/75로 조정 권장
> - Funding rate, 청산(liquidation) cascade, 거래소 outage 등 비정상 이벤트로 평균회귀가 지연/실패하는 빈도가 높음
> - 알트코인은 BTC/ETH 대비 trending이 강해 mean reversion 적용 시 ADX·HTF 필터 필수

---

## 목차

1. [RSI Overbought/Oversold Reversal](#1-rsi-overboughtoversold-reversal)
2. [RSI Divergence (Regular & Hidden)](#2-rsi-divergence-regular--hidden)
3. [MACD Divergence](#3-macd-divergence)
4. [Bollinger Band Reversion (Naive 버전과 함정)](#4-bollinger-band-reversion-naive-버전과-함정)
5. [Bollinger %B + RSI Combo](#5-bollinger-b--rsi-combo)
6. [Mean Reversion at Moving Averages (20/50/200 EMA)](#6-mean-reversion-at-moving-averages-205200-ema)
7. [VWAP Mean Reversion (Intraday)](#7-vwap-mean-reversion-intraday)
8. [Stochastic Oscillator Reversal](#8-stochastic-oscillator-reversal)
9. [CCI Extreme Reversal](#9-cci-extreme-reversal)
10. [Z-score / Standard Deviation Mean Reversion](#10-z-score--standard-deviation-mean-reversion)
11. [Pairs Trading / Spread Mean Reversion](#11-pairs-trading--spread-mean-reversion)
12. [Bollinger Band Walking (강추세 식별 — 역추세 회피)](#12-bollinger-band-walking-강추세-식별--역추세-회피)
13. [Williams %R Reversal](#13-williams-r-reversal)
14. [Fibonacci Retracement Entry](#14-fibonacci-retracement-entry)
15. [Wyckoff Spring / Upthrust](#15-wyckoff-spring--upthrust)
16. [Connors RSI(2) — 보너스: 단기 평균회귀](#16-connors-rsi2--단기-평균회귀-보너스)
17. [공통 함정 및 리스크 관리](#17-공통-함정-및-리스크-관리)

---

## 1. RSI Overbought/Oversold Reversal

**개요**:
RSI(Relative Strength Index)는 최근 N봉(보통 14)의 상승폭/하락폭 비율로 0-100 범위 모멘텀을 측정한다. 70 이상은 매수세 과열(overbought), 30 이하는 매도세 과매도(oversold)로 보고, 평균회귀 가설하에 반대 방향 진입을 트리거한다. 크립토에서는 변동성 때문에 80/20 또는 75/25로 임계치를 올려 false signal을 줄인다.

**시그널 정의**:
- **Long entry (oversold reversal)**:
  - `RSI(14) < 30` (or `< 25` for crypto) on entry candle
  - AND 종가(close) > 직전 봉의 저가(prior bar low) — bullish reversal candle 확인
  - AND HTF (1H or 4H) `EMA(200)` 우상향 (= 큰 추세는 상승)
  - AND `volume[t] > SMA(volume, 20)` — 자본 유입 확인 (capitulation 가능성)
- **Short entry (overbought reversal)**:
  - `RSI(14) > 70` (or `> 75`)
  - AND 종가 < 직전 봉의 고가
  - AND HTF EMA(200) 우하향
- **Exit / SL**:
  - SL: 진입봉의 swing low/high에서 1×ATR(14) 바깥
  - TP1: RSI가 50선 회귀 시 50% 청산
  - TP2: 가격이 EMA(20) 또는 Bollinger middle band 도달 시 잔여 청산
  - Time stop: 8-12 봉 내에 평균 회귀 미발생 시 강제 청산

**파라미터**:
- RSI length: 14 (standard), 7 for scalping, 21 for swing
- Threshold: 30/70 (standard), 25/75 or 20/80 (crypto), 10/90 (Connors RSI(2))
- HTF filter: 1H EMA200, 4H EMA200, Daily EMA200

**결합 필터**:
- `ADX(14) < 20` — 횡보장(ranging market) 확인 시에만 진입 (강추세 회피)
- Bollinger Band Walking 미발생 (#12 참조)
- 직전 5봉 내 funding rate spike 없음 (extreme funding은 short squeeze/long squeeze 위험)
- 주요 뉴스/CPI/FOMC 이벤트 ±2시간 회피

**실패 케이스 / 함정**:
- 강추세에서는 RSI가 70 위, 30 아래에 수일~수주 머무름 ("RSI가 추세에 갇힘") — Cardwell이 강조한 핵심 포인트
- 알트코인의 parabolic dump에서 RSI <20도 흔함 → 단순 oversold 진입은 falling knife
- 거래소 outage 직후 첫 reading은 신뢰도 낮음
- News-driven gap: RSI 역전 신호가 무효화됨

**출처**:
- [Kraken Learn: RSI Divergences](https://www.kraken.com/learn/rsi-divergences-what-they-how-they-work)
- [PMC: Effectiveness of RSI Signals in Crypto](https://pmc.ncbi.nlm.nih.gov/articles/PMC9920669/)
- [Altrady: RSI Trading Strategy](https://www.altrady.com/blog/crypto-trading-strategies/rsi-trading-strategy)
- [Mind Math Money: Ultimate RSI Trading Guide](https://www.mindmathmoney.com/articles/the-ultimate-guide-to-the-rsi-indicator-mastering-rsi-trading-strategies-and-settings-2025)

---

## 2. RSI Divergence (Regular & Hidden)

**개요**:
가격과 RSI의 방향성이 어긋날 때 발생하는 시그널. Regular divergence는 추세 반전(reversal), Hidden divergence는 추세 지속(continuation)을 시사한다. Andrew Cardwell이 체계화한 분석법으로, "divergence는 반전이 아닌 모멘텀 과확장(overextension)을 알릴 뿐"이라는 경고가 핵심이다.

**시그널 정의**:

### 2.1 Regular Bullish Divergence (반전 상승)
- 가격: Lower Low (LL) — 신저가
- RSI: Higher Low (HL) — 직전 저점보다 높은 저점
- **Entry**: 두 번째 LL 형성 후 RSI가 30선 위로 상향 돌파(crosses up through 30) + bullish engulfing/pin bar 확정
- **SL**: 두 번째 LL 아래 1×ATR
- **TP**: 직전 swing high 또는 EMA(50)

### 2.2 Regular Bearish Divergence (반전 하락)
- 가격: Higher High (HH)
- RSI: Lower High (LH)
- **Entry**: RSI가 70선 아래로 하향 돌파 + bearish reversal candle
- **SL**: 두 번째 HH 위 1×ATR
- **TP**: 직전 swing low 또는 EMA(50)

### 2.3 Hidden Bullish Divergence (상승 추세 지속)
- 가격: Higher Low (HL) — 풀백
- RSI: Lower Low (LL) — RSI는 더 깊이 빠짐
- 이는 상승추세 중 모멘텀 "리셋"이며 long continuation
- **Entry**: HL 확정 후 다음 봉이 직전봉 고가 돌파
- **SL**: HL 아래
- **TP**: 직전 swing high 돌파 후 trailing stop

### 2.4 Hidden Bearish Divergence (하락 추세 지속)
- 가격: Lower High (LH)
- RSI: Higher High (HH)
- **Entry**: LH 확정 후 직전봉 저가 이탈
- **SL**: LH 위
- **TP**: 직전 swing low 갱신 후 trailing

**파라미터**:
- RSI length: 14 (Cardwell 표준)
- Pivot lookback: 좌/우 각 5봉 (5/5 fractal pivot)
- Min divergence interval: 5-30 봉 (너무 가까우면 noise)

**결합 필터**:
- HTF 추세 일치: Hidden divergence는 HTF 추세 방향과 같아야 (예: 1H hidden bullish → 4H EMA200 우상향)
- Volume 증가 동반 시 신뢰도 ↑
- Support/resistance 영역에서 발생한 divergence가 가장 강함
- Cardwell warning: divergence 단독으로는 진입 금지, market structure + confirmation candle 필수

**실패 케이스 / 함정**:
- "Triple divergence" — 같은 방향으로 3-4번째 divergence가 연속 발생할 수 있음 (강추세 신호이므로 진입 금지)
- 지지선이 없는 자유낙하 구간의 bullish divergence는 자주 무효
- 시간프레임이 너무 짧으면(<15m) noise 비율 급증

**출처**:
- [Traders Log: RSI as Cardwell's Cornerstone](https://www.traderslog.com/rsi-indicator-trading-model)
- [Stockcanny: Hidden RSI Divergence](https://www.stockcanny.com/2026/01/what-is-hidden-rsi-divergence-and-how.html)
- [Tradealgo: RSI Indicator Guide](https://www.tradealgo.com/trading-guides/technical-analysis/rsi-indicator-guide)
- [MoneyShow: Trend Analysis Using the Ideal Indicator (Cardwell)](https://www.moneyshow.com/articles/daytraders-29562/)

---

## 3. MACD Divergence

**개요**:
MACD(Moving Average Convergence Divergence)는 EMA(12)-EMA(26) 차이값과 그것의 EMA(9) 시그널 라인으로 모멘텀을 측정. 가격과 MACD 라인 또는 히스토그램이 어긋날 때 추세 약화/반전을 시사. RSI divergence보다 노이즈는 적지만 시그널 빈도가 낮다.

**시그널 정의**:

### 3.1 Regular Bullish/Bearish Divergence
- **Bullish**: 가격 LL, MACD line HL → 매도 모멘텀 약화
- **Bearish**: 가격 HH, MACD line LH → 매수 모멘텀 약화
- **Entry**: divergence 확정 후 MACD line이 signal line을 cross over (long) / cross under (short)
- **SL**: 직전 swing low/high
- **TP1**: 1:1 R:R, **TP2**: 2:1 R:R 또는 직전 swing 반대편

### 3.2 Hidden Divergence
- **Hidden Bullish**: 가격 HL, MACD LL → 상승추세 지속
- **Hidden Bearish**: 가격 LH, MACD HH → 하락추세 지속
- **Entry**: HTF 추세 방향과 일치할 때만, MACD가 zero line을 재차 cross 후

### 3.3 MACD Histogram Divergence (조기 시그널)
- 히스토그램이 가격보다 먼저 peak/trough 형성 → MACD line divergence보다 1-3봉 빠름
- 단, false signal도 더 많음

**파라미터**:
- MACD: 12/26/9 (standard), 5/35/5 (faster, Linda Raschke variant)
- Pivot detection: 5봉 fractal
- HTF preference: 4H, Daily에서 가장 신뢰도 높음 (낮은 TF는 noise)

**결합 필터**:
- MACD line이 zero line 근처에서 발생한 divergence가 가장 강함
- RSI divergence와 동시 발생 시 confluence (= dual confirmation)
- ADX < 25 환경에서 reversal divergence가 잘 작동

**실패 케이스 / 함정**:
- MACD는 lagging indicator → divergence 확정 시점에 이미 가격이 많이 회복/하락한 경우 다수
- 강한 트렌드에서 MACD histogram이 zero line 위/아래 장기간 머무름 → divergence 신호 자주 발생하지만 무효
- Crypto pump 직전 fake bearish divergence가 흔함 (특히 4H 이하)

**출처**:
- [CoinGecko: Hidden Divergence Trading](https://www.coingecko.com/learn/hidden-bullish-bearish-divergence-trading)
- [Fidelity: MACD Indicator](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/macd)
- [Phemex: Best Divergence Trading Strategy](https://phemex.com/academy/what-is-the-best-divergence-trading-strategy)
- [AltcoinTrading.NET: Divergences in Crypto](https://www.altcointrading.net/divergences/)

---

## 4. Bollinger Band Reversion (Naive 버전과 함정)

**개요**:
Bollinger Bands는 SMA(20) ± 2·StdDev(20)으로 구성. 가격이 표준편차 ±2 범위 안에 ~95% 머문다는 가정 하에, 하단 밴드 터치 = 매수, 상단 밴드 터치 = 매도라는 단순 규칙이 "naive Bollinger reversion"이다. **이 단순 버전은 강추세에서 catastrophic failure를 일으킨다** — 이것이 #12 Bollinger Band Walking 개념의 출발점.

**시그널 정의 (개선된 버전)**:

### 4.1 Naive (실패 빈번 — reference only):
- 종가 < Lower Band → buy
- 종가 > Upper Band → sell
- → 강추세에서 walk the band 발생 시 연속 손실

### 4.2 Robust Bollinger Reversion:
- **Long Entry**:
  - `close[t] < Lower Band(20, 2.0)` (band piercing)
  - AND `close[t+1] > Lower Band` AND `close[t+1] > close[t]` (re-entry candle 확정)
  - AND `ADX(14) < 20` (ranging market)
  - AND HTF EMA(200) 횡보 또는 우상향
  - AND **NOT walking the band** (#12)
- **Short Entry**: 위 mirror image
- **Exit**:
  - TP1: 가격이 middle band (SMA20) 도달 → 50% 청산
  - TP2: 반대편 band 근접 → 잔여 청산 (full mean reversion)
  - SL: 진입봉 low/high의 1.5×ATR 바깥

**파라미터**:
- Length: 20 (standard, John Bollinger 권장)
- StdDev: 2.0 (95% range), 2.5 (extreme), 1.5 (tight)
- Crypto adjustment: 20/2.5 또는 24/2.0 (캔들 노이즈 감안)

**결합 필터**:
- BB Width(상-하 폭) / SMA20 < 직전 100봉 25th percentile → squeeze 직전, 진입 비추 (breakout 위험)
- BB Width 확장 phase에서만 진입
- Volume divergence: 가격은 신저가지만 volume 감소 시 reversion 확률 ↑
- RSI confirmation (#5 참조)

**실패 케이스 / 함정**:
- **Walking the band** (#12): 강추세에서 연속 5+ 봉 동안 band 외부 종가 → 단순 reversion 전략은 연속 손실
- BB squeeze 후 expansion 초기에는 mean reversion 금지 → trend-following만
- 5분봉 이하에서 noise로 인한 false touch 빈번
- News spike: band를 폭발적으로 깨뜨림 → SL 미체결로 큰 손실 (slippage)

**출처**:
- [StockCharts: Bollinger Bands](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/bollinger-bands)
- [Britannica Money: Bollinger Bands](https://www.britannica.com/money/bollinger-bands-indicator)
- [Medium: Bollinger Band Extremes Mean Reversion](https://medium.com/algorithmic-and-quantitative-trading/bollinger-band-extremes-a-high-probability-mean-reversion-trading-strategy-d36744d6ccb7)
- [Charles Schwab: Bollinger Bands](https://www.schwab.com/learn/story/bollinger-bands-what-they-are-and-how-to-use-them)

---

## 5. Bollinger %B + RSI Combo

**개요**:
%B = (Price - LowerBand) / (UpperBand - LowerBand) 으로 가격의 밴드 내 상대 위치를 0-1로 정규화 (1 위, 0 아래는 밴드 외부). %B와 RSI를 결합하면 "가격은 밴드 외부에 있고 + 모멘텀도 극단" 이라는 dual confirmation으로 false signal이 크게 감소한다.

**시그널 정의**:
- **Long Entry**:
  - `%B(20, 2) < 0` (가격이 lower band 외부) AT THE EXTREME
  - AND `RSI(14) < 30`
  - AND 다음 봉에서 `%B > 0` (밴드 내부 재진입) — bullish reclaim
  - AND HTF (1H) EMA200 우상향 또는 횡보
- **Short Entry** (mirror):
  - `%B > 1` AND `RSI > 70`
  - AND 다음 봉 `%B < 1`
  - AND HTF 우하향 또는 횡보
- **Exit/SL**:
  - TP1: `%B = 0.5` (middle band) → 50% 청산
  - TP2: 반대편 `%B = 1.0` 또는 0.0 도달 → 잔여 청산
  - SL: 진입봉 low/high 외 1×ATR

**파라미터**:
- BB: 20 / 2.0
- RSI: 14
- Crypto: BB 20/2.5, RSI 14 with 25/75 thresholds 권장
- Lower TF (5m, 15m): BB 20/2.0, RSI 7

**결합 필터**:
- `ADX < 20` — ranging market 확인 (필수)
- BB Width > 직전 50봉 평균 (squeeze 회피)
- Funding rate ±0.05% 이내 (crypto: extreme funding은 reversal 지연 risk)

**실패 케이스 / 함정**:
- Trending market에서 %B가 1.0 이상에 5+ 봉 머물면 short signal은 모두 거짓
- RSI가 OB/OS 영역 cross 시점이 가장 위험 (관성 가능성)
- LTF에서 dual confirmation도 noise 다수 → 15m 이상 권장

**출처**:
- [TradingView: Bollinger Bands %b](https://www.tradingview.com/support/solutions/43000501971-bollinger-bands-b-b/)
- [StockCharts: %B Indicator](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/b-indicator)
- [CoinEx Academy: Combine RSI & Bollinger Bands](https://www.coinex.network/en/academy/detail/3064-best-crypto-trading-strategy-rsi-bollinger-bands)
- [FMZ: Bollinger-RSI Dual Confirmation Strategy](https://www.fmz.com/lang/en/strategy/504546)

---

## 6. Mean Reversion at Moving Averages (20/50/200 EMA)

**개요**:
EMA는 동적 지지/저항(dynamic S/R)으로 작동하며, 추세 시장에서 가격이 이동평균으로 풀백 후 반등(bounce)하는 패턴이 흔하다. 20 EMA는 단기, 50 EMA는 중기 swing, 200 EMA는 장기 regime/trend filter로 사용. 이 전략은 mean reversion이지만 **HTF 추세 방향으로만 진입**하므로 엄밀하게는 trend-following pullback entry에 가깝다.

**시그널 정의**:
- **Long Entry (uptrend pullback)**:
  - HTF (4H/Daily) `EMA(200)` 우상향 + 가격이 EMA200 위
  - 가격이 `EMA(20)` 또는 `EMA(50)` 으로 풀백
  - touch 또는 약간 wick 후 bullish reversal candle (engulfing, pin bar, hammer)
  - RSI(14) > 40 (추세 모멘텀 유지) AND RSI 직전 oversold(<30) 후 회복
- **Short Entry (downtrend pullback)**: mirror image
- **Exit/SL**:
  - SL: EMA 라인의 0.5-1×ATR 바깥
  - TP1: 직전 swing high/low → 50% 청산
  - TP2: 추세 연장 측정값 (1.272 / 1.618 Fibonacci extension)

**파라미터**:
- EMA: 20, 50, 200 (golden ratio set), 또는 9, 21, 55 (Fibonacci set)
- Crypto: 4H EMA200을 macro trend filter로 가장 많이 사용
- "Confluence zone": 두 개 이상의 EMA가 겹치는 영역에서 신뢰도 ↑

**결합 필터**:
- Volume profile의 HVN (High Volume Node) 또는 prior support/resistance와 일치하는 EMA 영역
- HTF 추세 + LTF 풀백 multi-timeframe 정합
- 풀백 깊이: 0.382-0.618 Fib 영역과 일치 시 매우 강함

**실패 케이스 / 함정**:
- 추세 끝물에서 EMA 첫 break 후 false bounce (deadcat bounce) 후 추세 반전
- 횡보장에서는 EMA가 가격에 너무 붙어 의미 없음 → ADX > 20 + EMA slope > 임계치 확인
- Flash crash로 EMA 영역을 수십 % 이탈 → SL hit 후 회복 (whipsaw)

**출처**:
- [Altrady: EMA 20, 50, 200](https://www.altrady.com/blog/crypto-trading-strategies/ema-20-50-200)
- [Trading With Rayner: 200 Day MA Strategy](https://www.tradingwithrayner.com/200-day-moving-average/)
- [Capital.com: EMA Trading Strategy](https://capital.com/en-int/learn/technical-analysis/exponential-moving-average)
- [Alchemy Markets: EMA Mastering Trends](https://alchemymarkets.com/education/indicators/exponential-moving-average/)

---

## 7. VWAP Mean Reversion (Intraday)

**개요**:
VWAP(Volume Weighted Average Price)는 일중(또는 세션) 누적 (price × volume) / 누적 volume으로 계산되며, 기관 트레이더의 fair value 벤치마크다. 가격이 VWAP로부터 ±2σ, ±3σ 이탈 시 평균회귀 가능성이 높다. 크립토는 24/7이므로 보통 **00:00 UTC anchor** 사용 (Anchored VWAP).

**시그널 정의**:
- **Long Entry**:
  - `close < VWAP - 2·σ` (VWAP -2 deviation band 하단 이탈)
  - AND `volume[t] < SMA(volume, 20)` — capitulation 후 매도 압력 약화
  - AND 다음 봉에서 `close > prior close` (reversal candle)
  - AND HTF (1H/4H) 우상향 또는 횡보
- **Short Entry**: mirror, VWAP + 2·σ 위
- **Exit/SL**:
  - TP1: VWAP ±1σ band → 50% 청산
  - TP2: VWAP touch → 잔여 청산
  - SL: 진입봉 low/high의 1×ATR 바깥
  - Time stop: 세션 종료 (00:00 UTC) 시 강제 청산

**파라미터**:
- VWAP anchor: 00:00 UTC (daily reset, crypto 표준)
- Bands: VWAP ± 1σ, ±2σ, ±3σ (rolling stddev of price-VWAP)
- Best timeframe: 1m (entry tuning), 5m (signal), 15m (broader structure)

**결합 필터**:
- 거래량 풍부한 시간대 (UTC 12:00-22:00, US/EU 겹치는 시간)
- 주요 거래소 BTC/USDT 등 high-liquidity 페어만
- News event ±2 hours 회피
- Anchored VWAP from major event (e.g. 직전 거래일 high) 와 일치 시 confluence

**실패 케이스 / 함정**:
- 저유동성 알트는 VWAP이 noisy하고 신뢰도 낮음 (volume spike에 line이 jump)
- Trend day (daily 5%+ move): VWAP 멀리 이탈 후 회귀 안 됨 → 직접 chase하면 손실
- 세션 시작 직후(00:00-02:00 UTC) volume 누적 부족으로 VWAP 변동성 큼
- Asian time (00:00-08:00 UTC)에는 평균회귀 빈도가 낮은 경향

**출처**:
- [Hyrotrader: Mastering VWAP in Crypto Trading](https://www.hyrotrader.com/blog/vwap-trading-strategy/)
- [FerroQuant: VWAP Reversion Strategy](https://ferroquant.com/strategy/vwap-reversion)
- [Mudrex Learn: VWAP in Crypto 2025](https://mudrex.com/learn/vwap-in-crypto/)
- [Extreme to Mean: Reversion-to-Mean VWAP Strategy](https://extremetomean.com/the-reversion-to-mean-vwap-trading-strategy-how-to-snap-back-into-profits)

---

## 8. Stochastic Oscillator Reversal

**개요**:
Stochastic은 종가가 N-기간 최고-최저 범위에서 어디에 위치하는지 0-100으로 측정. %K = (Close - LowestLow) / (HighestHigh - LowestLow) × 100, %D = SMA(%K, 3). Fast Stochastic은 raw %K, Slow Stochastic은 추가 smoothing. 80/20을 OB/OS 임계치로 사용하며, divergence와 cross signal로 평균회귀 진입.

**시그널 정의**:

### 8.1 Slow Stochastic Reversal
- **Long Entry**:
  - `%K < 20` AND `%D < 20` (oversold zone 진입)
  - %K가 %D를 cross up (bullish cross)
  - %K가 20선 위로 cross up (zone 탈출 — 핵심 트리거)
  - HTF EMA200 우상향 또는 횡보
- **Short Entry**:
  - `%K > 80` AND `%D > 80`, %K가 %D 아래로 cross
  - %K가 80선 아래로 cross down

### 8.2 Stochastic Divergence (강화)
- **Bullish Div**: 가격 LL, Stoch %K HL (특히 oversold 영역에서)
- **Bearish Div**: 가격 HH, Stoch %K LH (overbought 영역)
- **Confirmation**: divergence 후 Stoch가 50선을 cross
- **Entry**: confirmation candle close 후

**파라미터**:
- Slow Stoch: %K period 14, %D period 3, smoothing 3
- Fast Stoch: 14/3 (no smoothing)
- Crypto: 14/3/3 standard, 21/5/5 for swing
- Threshold: 80/20 (standard), 90/10 (extreme)

**결합 필터**:
- ADX < 25 — ranging environment
- RSI confluence (RSI < 30 + Stoch < 20 = strong)
- Support/resistance 근처 발생
- 1H 이상 timeframe (LTF는 noise 과다)

**실패 케이스 / 함정**:
- Stoch는 추세장에서 oversold/overbought에 매우 오래 머무름 (RSI보다 더 빈번)
- "Embedded stochastic": %K가 80 위 또는 20 아래에 머물면 추세 강도 신호 → reversal 진입 금지
- LTF 빠른 cross로 false signal 폭발적 발생
- Hidden divergence 발생 시 reversal 진입은 손실 (continuation 신호)

**출처**:
- [StockCharts: Stochastic Oscillator (Fast, Slow, Full)](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/stochastic-oscillator-fast-slow-and-full)
- [OANDA: Stochastic Oscillator Trend Reversals](https://www.oanda.com/us-en/trade-tap-blog/trading-knowledge/spotting-trend-reversals-with-stochastic-oscillator/)
- [LuxAlgo: Ultimate Guide to Stochastic Divergence](https://www.luxalgo.com/blog/ultimate-guide-to-stochastic-divergence-trading/)
- [Wikipedia: Stochastic oscillator](https://en.wikipedia.org/wiki/Stochastic_oscillator)

---

## 9. CCI Extreme Reversal

**개요**:
CCI(Commodity Channel Index, Donald Lambert)는 (Typical Price - SMA(TP, 20)) / (0.015 × Mean Deviation). 평균 ±0.015·MD를 ±100으로 정규화. 일반적으로 ±100을 trend 시그널, ±200을 extreme 평균회귀 트리거로 사용. 크립토 변동성 감안 시 ±200 트리거가 더 안정적.

**시그널 정의**:

### 9.1 Standard ±100 Reversal (caution: trend signal로도 해석됨)
- 일반적으로 +100 cross up = 추세 시작 (NOT reversion)
- Mean reversion 해석: CCI가 +100 위에서 +100 아래로 cross down = exit overbought = short reversal trigger
- 마찬가지로 -100 cross up = long reversal trigger

### 9.2 Extreme ±200 Mean Reversion (crypto 권장):
- **Long Entry**:
  - `CCI(20) < -200`
  - AND CCI가 -200 위로 회복 (cross up through -200)
  - AND 다음 봉 종가가 직전봉 종가보다 위
  - AND HTF 우상향 또는 횡보
- **Short Entry**: mirror, CCI > +200 후 +200 아래 cross
- **Exit/SL**:
  - TP1: CCI = 0 (zero line, mean) → 50% 청산
  - TP2: CCI 반대편 ±100 도달
  - SL: 진입봉 low/high 1×ATR 바깥

### 9.3 CCI Divergence
- 가격 LL/HH, CCI HL/LH → reversal 신호
- ±100 영역에서 발생 시 가장 신뢰도 높음

**파라미터**:
- Length: 20 (standard, Lambert)
- Threshold: ±100 (standard), ±200 (extreme — crypto 권장)
- Constant: 0.015 (Lambert original)

**결합 필터**:
- ADX < 20 → ranging
- Volume spike + CCI extreme → capitulation 가능성
- Higher TF (4H+) divergence가 가장 강함

**실패 케이스 / 함정**:
- 강추세에서 CCI가 ±200 이상에 5+ 봉 머무름 (Bollinger walking과 유사)
- LTF에서 ±100 cross가 너무 잦아 진입 빈도 폭발
- News-driven extreme: CCI -300, -400 까지 가서 회귀 지연

**출처**:
- [StockCharts: Commodity Channel Index (CCI)](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/commodity-channel-index-cci)
- [Wikipedia: Commodity channel index](https://en.wikipedia.org/wiki/Commodity_channel_index)
- [Fidelity: What Is CCI?](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/cci)
- [TradingView: CCI Solution](https://www.tradingview.com/support/solutions/43000502001-commodity-channel-index-cci/)

---

## 10. Z-score / Standard Deviation Mean Reversion (통계적)

**개요**:
가격 또는 가격-평균 잔차(residual)를 표준화하여 Z-score = (price - μ) / σ 로 계산. Z = ±2 이면 95% 신뢰구간 외부 → 평균회귀 기대. 통계적으로 가장 엄밀한 평균회귀 접근이며, ADF test로 stationarity, Hurst exponent로 mean-reverting 강도 검증.

**시그널 정의**:
- **Long Entry**:
  - `Z(price, lookback=20) < -2.0`
  - AND ADF test p-value < 0.05 (stationarity 확인)
  - AND `Hurst exponent < 0.5` (mean-reverting 성질)
  - AND HTF EMA200 횡보 또는 우상향
- **Short Entry**: `Z > +2.0`
- **Exit/SL**:
  - TP: `Z = 0` (mean) → 청산
  - SL: `Z = ±3` (further extreme — 회귀 실패)
  - Time stop: 2× lookback 봉 내 미회귀 시 청산

**파라미터**:
- Lookback: 20-50 봉 (변동성에 맞게 조정)
- Z threshold: ±2 (entry), ±3 (SL/extreme)
- ADF test: rolling 100 봉 재계산
- Hurst lookback: 100-200 봉

**결합 필터**:
- Stationarity: ADF p < 0.05 (필수)
- Hurst < 0.5: mean-reverting (>0.5는 trending → 회피)
- Half-life of mean reversion: log(0.5) / log(1 + φ) where φ from AR(1) regression. 5-50 봉 적정.
- Position sizing: |Z|에 비례 (Z=-2면 1unit, Z=-3면 1.5unit)

**실패 케이스 / 함정**:
- **Regime shift**: ADF p-value가 갑자기 > 0.05로 변하면 평균이 이동 (regime change) — 진입 즉시 중단
- "Mean drift": rolling mean이 trending → Z-score 0이 자꾸 이동 → trailing mean으로 추적
- BTC/ETH halving, ETF news 같은 fundamental 이벤트는 Z-score 가정을 깨뜨림
- Crypto는 fat-tailed distribution → Z=±3도 흔함, Z=±4 가야 진정한 extreme

**출처**:
- [Amberdata: Constructing Strategy with Logs, Hedge Ratios, Z-Scores](https://blog.amberdata.io/constructing-your-strategy-with-logs-hedge-ratios-and-z-scores)
- [Amberdata: Verifying Mean Reversion with ADF and Hurst Tests](https://blog.amberdata.io/crypto-pairs-trading-part-2-verifying-mean-reversion-with-adf-and-hurst-tests)
- [Fensory: Mean Reversion Strategy in Crypto](https://www.fensory.com/knowledge/mean-reversion-strategy)
- [Stoic.ai: Mean Reversion Trading in Crypto](https://stoic.ai/blog/mean-reversion-trading-how-i-profit-from-crypto-market-overreactions/)

---

## 11. Pairs Trading / Spread Mean Reversion

**개요**:
Market-neutral 전략. 두 자산(보통 cointegrated pair: BTC/ETH, BTC/LTC, ETH/SOL 등)의 가격 또는 log price의 spread = A - β·B 가 stationary할 때, spread Z-score 극단에서 진입. Spread 회귀 시 청산. 시장 전체 방향과 무관한 alpha를 추구.

**시그널 정의**:
1. **Pair selection**:
   - Pearson correlation > 0.7 (수개월 rolling)
   - Engle-Granger or Johansen cointegration test → p < 0.05
   - Hurst < 0.5 on spread
2. **Hedge ratio (β)**:
   - OLS regression: log(A) = α + β·log(B) + ε
   - 또는 dynamic β: rolling Kalman filter
3. **Entry**:
   - `Spread = log(A) - β·log(B)`
   - `Z(spread, 60) < -2` → **Long A, Short B** (with β·B notional ratio)
   - `Z(spread, 60) > +2` → **Short A, Long B**
4. **Exit**:
   - `|Z| < 0.5` → 청산 (mean reversion 완료)
   - `|Z| > 3` → SL (regime shift 가능)
5. **Risk-balanced sizing**:
   - notional A = capital / 2, notional B = β × notional A

**파라미터**:
- Lookback for Z: 30-90 days (1H bars)
- Cointegration window: 90-180 days (rolling 재검증)
- Hedge ratio update: 매주 또는 매일 재계산
- Entry threshold: ±2, exit ±0.5 (Sharpe optimal 영역)

**결합 필터**:
- ADF test의 p-value가 매주 < 0.05 유지 확인 (cointegration 유효)
- 두 자산의 funding rate 차이가 너무 크면 carry cost 발생 → 회피
- BTC dominance가 급변하는 구간은 BTC/alt pair 회귀가 깨짐

**실패 케이스 / 함정**:
- **Cointegration breakdown**: 한 자산의 fundamental shock (ETH merge, SOL outage 등) → spread 영구 이동
- 두 자산 모두 같은 방향 폭락 (correlation → 1) → market-neutral 가정 무효
- 거래소별 가격 괴리: 한쪽 거래소 outage 시 spread artifact
- Funding rate 비대칭 → long-short carry가 누적 손실
- 알트 vs 알트 페어는 cointegration이 한 달 이내 깨지는 경우 흔함

**예시 (실제 사례)**:
- 2021년 9월 ETH/BTC 비율이 0.082 (Z = +2.3) 까지 치솟음 → ETH short / BTC long 1:1.4 hedge → 3주 후 0.074로 회귀, +9.5% 수익 (시장 방향 무관)

**출처**:
- [Amberdata: Crypto Pairs Trading Cointegration vs Correlation](https://blog.amberdata.io/crypto-pairs-trading-why-cointegration-beats-correlation)
- [QuantStart: Cointegrated ADF Test for Pairs Trading](https://www.quantstart.com/articles/Cointegrated-Augmented-Dickey-Fuller-Test-for-Pairs-Trading-Evaluation-in-R/)
- [QuantInsti: ADF Test for Pairs Trading Strategy](https://blog.quantinsti.com/augmented-dickey-fuller-adf-test-for-a-pairs-trading-strategy/)
- [Medium / Digital Alpha: Pairs Trading Statistical Arbitrage on Digital Assets](https://medium.com/digital-alpha-research/using-a-pairs-trading-statistical-arbitrage-approach-on-digital-assets-e29b10c6c651)

---

## 12. Bollinger Band Walking (강추세 식별 — 역추세 회피)

**개요**:
"Walking the band"는 강추세에서 가격이 Bollinger Band 외부 또는 외부 가장자리에 연속 머무르는 현상. 이는 평균회귀 가설을 정면으로 위배하므로, **역추세 진입 회피 필터(NEGATIVE filter)**로 사용한다. 여기서 다루는 시그널은 진입 트리거가 아니라 "역추세 진입 금지" 조건이다.

**시그널 정의 (역추세 회피 트리거)**:
- **Walking the upper band**: 직전 N봉(예: 5) 중 ≥3봉의 close > Upper Band(20, 2)
  - → **Short reversal 진입 금지**
  - → Long trend continuation 모드만 허용
- **Walking the lower band**: 직전 5봉 중 ≥3봉의 close < Lower Band
  - → **Long reversal 진입 금지**
  - → Short trend continuation 모드만 허용
- **Band 정상화 확인**: 가격이 middle band(SMA20)로 회귀하고 ADX peak에서 하락 시 walk 종료 → 다시 mean reversion 활성화

**파라미터**:
- Lookback for "walk": 5-7 봉 (most common: 5)
- Touches required: ≥3 close 외부 (또는 high/low로 기준)
- Confirmation: 추가 ADX > 25 + EMA(20) slope 가파름

**보조 식별자**:
- ADX(14) > 25 AND DI+/DI- 비율 > 1.5 (uptrend) or < 0.67 (downtrend)
- 하단 밴드가 계속 밀려 내려가거나 (downtrend) 상단 밴드가 밀려 올라감 (uptrend)
- "Lower band가 회복되어 위로 꺾일 때" = trend exhaustion 가능 신호 (Bollinger 본인 언급)

**활용 (역추세 모드 vs 추세 모드 자동 전환)**:
1. Walking detected → 모든 reversal 전략 비활성화 (RSI/Stoch/CCI/BB reversal 등)
2. ADX cross down through 25 + middle band 회귀 → walking 종료, reversal 모드 재활성
3. 또는 trend continuation pullback (#6) 으로 진입

**실패 케이스 / 함정**:
- Walking 감지 직후 추세 반전 (false trend) → late detection으로 손실 가능
- 너무 strict한 임계값 (5/5)은 신호가 늦음, 너무 loose (3/5)는 false alarm 잦음
- 변동성 낮은 횡보장에서 매번 band 외부 → walking이 아닌데 walking으로 오판

**출처**:
- [StockCharts: Bollinger Bands Walking the Band](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/bollinger-bands)
- [OANDA: Gauge trends with Bollinger Bands](https://www.oanda.com/us-en/trade-tap-blog/trading-knowledge/gauge-trends-monitoring-for-breakouts-bollinger-bands/)
- [LuxAlgo: BBTrend Indicator](https://www.luxalgo.com/blog/bbtrend-indicator-combining-bollinger-bands-and-trend-analysis/)
- [TrendSpider: Bollinger Bands Trend Oscillator](https://help.trendspider.com/kb/indicators/bollinger-bands-trend-oscillator)

---

## 13. Williams %R Reversal

**개요**:
Williams %R = (HighestHigh - Close) / (HighestHigh - LowestLow) × -100. 범위 -100 (가장 oversold) ~ 0 (가장 overbought). RSI/Stochastic의 사촌이지만 0~-100 스케일 사용. -20 위 = OB, -80 아래 = OS. **신호는 zone "탈출"이지 zone "진입"이 아니다.**

**시그널 정의**:
- **Long Entry (oversold reversal)**:
  - `%R < -80` (oversold zone에 진입한 후)
  - AND `%R cross up through -80` (zone 탈출 — 핵심 트리거)
  - AND 진입봉이 bullish reversal candle
  - AND HTF (1H/4H) EMA200 우상향 또는 횡보
- **Short Entry**:
  - `%R > -20` AND cross down through -20
  - HTF 우하향 또는 횡보
- **Exit/SL**:
  - TP1: `%R = -50` → 50% 청산
  - TP2: 반대편 zone (-20 long의 경우, -80 short의 경우) 도달
  - SL: 진입봉 low/high 외 1×ATR

**파라미터**:
- Length: 14 (standard)
- Threshold: -20 / -80 (standard), -10 / -90 (extreme)
- Smoothing: 없음 (raw %R), 또는 SMA(3) 추가

**결합 필터**:
- 50/200 EMA로 trend filter
- Candlestick reversal pattern (engulfing, morning/evening star, hammer)
- ADX < 25
- Volume spike + reversal candle

**실패 케이스 / 함정**:
- "Touch -80 = buy" 단순 규칙은 강추세에서 catastrophic
- LTF (5m, 15m)에서 zone cross가 너무 잦음 → 1H 이상 권장
- Zone exit 후 즉시 재진입 (whipsaw) 빈번

**출처**:
- [BingX: How to Use Williams %R in Crypto](https://bingx.com/en/learn/article/how-to-use-williams-r-in-crypto-trading-spot-overbought-oversold-levels)
- [KuCoin Learn: Williams %R Indicator](https://www.kucoin.com/learn/trading/what-is-williams-percent-r-and-how-to-use-it-in-crypto-trading)
- [Quantified Strategies: Williams %R Trading Strategy](https://www.quantifiedstrategies.com/williams-r-trading-strategy/)
- [Pi42 Blog: Williams %R Indicator in Crypto](https://pi42.com/blog/williams-r-indicator-in-crypto/)

---

## 14. Fibonacci Retracement Entry

**개요**:
황금비(φ = 1.618) 및 그 도함수에 기반한 풀백 영역. Swing high → swing low를 잡고 38.2%, 50%, 61.8%, 78.6% 레벨을 그어 풀백 후 추세 재개 영역으로 사용. **"Golden Pocket" = 0.618-0.65 (또는 0.62-0.79) 영역**이 가장 인기 있는 reversal 진입 zone.

**시그널 정의**:
- **Long Entry (uptrend pullback)**:
  - 직전 명확한 swing low → swing high (impulse leg) 식별
  - Fibonacci retracement 그어 38.2 / 50 / 61.8 / 78.6% 표시
  - Golden Pocket (61.8-65%) 영역에서 가격이 정지 + bullish reversal candle
  - AND RSI(14) divergence or oversold bounce
  - AND HTF EMA200 우상향
- **Short Entry**: mirror, downtrend rebound을 0.618-0.79 영역에서 short
- **Exit/SL**:
  - SL: 0.786 (or 0.886) 레벨 아래 1×ATR
  - TP1: prior swing high (= 0% retracement)
  - TP2: Fib extension 1.272 / 1.618

**파라미터**:
- Standard levels: 23.6, 38.2, 50, 61.8, 78.6, 100
- Golden Pocket: 0.618-0.65 (tight), 0.62-0.79 (broad)
- Optional: 88.6% (final defense before invalidation)

**결합 필터**:
- Confluence: Fib level + EMA(50/200) + horizontal S/R + volume node
- Higher TF Fib (Daily/Weekly) is much more reliable than LTF
- Fib level + RSI bullish divergence = high-probability setup
- Fib level + Wyckoff Spring(#15) = institutional-grade setup

**실패 케이스 / 함정**:
- Fib drawing은 주관적 (어느 swing을 잡는가) → 자동화 시 ZigZag indicator로 swing 자동 검출
- 0.786 외부 이탈 → trend invalidation, 평균회귀 가설 깨짐
- 횡보장에서는 Fib level 의미 약함 → trending 후 풀백 구간에서만 적용
- 대형 뉴스로 갭이 발생하면 Fib 무시당함

**출처**:
- [StockCharts: Fibonacci Retracements](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-annotation-tools/fibonacci-retracements)
- [Mudrex Learn: Golden Pocket Trading Guide](https://mudrex.com/learn/fibonacci-levels-explained/)
- [Zeiierman: Calculate and Use Fibonacci Retracement Levels](https://www.zeiierman.com/blog/fibonacci-retracement-levels)
- [CME Group: Fibonacci Retracements and Extensions](https://www.cmegroup.com/education/courses/technical-analysis/fibonacci-retracements-and-extensions)

---

## 15. Wyckoff Spring / Upthrust

**개요**:
Richard Wyckoff의 accumulation/distribution 이론. **Spring**은 trading range 하단 지지선 아래로 가격을 내려 retail 손절(stop loss)을 사냥(stop hunt) 후 빠르게 range 안으로 회복하는 패턴 = 매집(accumulation)의 마지막 phase C 시그널 → strong long. **UTAD (Upthrust After Distribution)**는 그 반대 = range 상단 위로 fakeout 후 복귀 = 분배(distribution) 마지막 phase C → strong short.

**시그널 정의**:

### 15.1 Spring (Phase C of Accumulation)
- 사전 조건: 가격이 명확한 trading range (TR)에서 N주/N일 횡보, support 라인이 명확
- **Trigger**:
  - 가격이 TR low를 wick 또는 close로 이탈
  - 다음 봉에서 다시 TR 안으로 회복 (close > TR low)
  - **Volume spike** during the dip + volume drop on recovery (선택적: low volume spring = 더 강함)
  - 직후 SOS (Sign of Strength): 강한 상승봉 + volume 동반
- **Entry**:
  - Spring 후 SOS 봉에서 시장가 진입, 또는 LPS (Last Point of Support, 약한 풀백) pullback에서 limit
- **SL**: Spring low 아래 1-1.5×ATR
- **TP**: TR high (resistance) → 50% 청산, 잔여는 SOS 측정값(Wyckoff projection: TR width × multiplier)

### 15.2 UTAD (Phase C of Distribution)
- 사전: 가격이 TR에서 횡보 후 weakness 신호 누적 (BC, AR, ST, etc.)
- **Trigger**:
  - 가격이 TR high를 wick으로 돌파
  - 빠르게 TR 안으로 복귀 (close < TR high)
  - Volume spike on the spike + low follow-through
  - 직후 SOW (Sign of Weakness): 강한 하락봉
- **Entry**: SOW 봉에서 short, 또는 LPSY (Last Point of Supply) rally에서 limit
- **SL**: UTAD high 위 1-1.5×ATR
- **TP**: TR low → 50%, 잔여 trailing

**파라미터**:
- TR identification: ≥ 20 봉 횡보 + clear S/R lines
- Spring/UTAD wick: TR boundary 외부 0.5-3% (asset 변동성에 비례)
- Volume threshold: spike봉 volume > 직전 20봉 평균 × 2

**결합 필터**:
- Wyckoff phase 분석: PS, SC, AR, ST, Spring, Test, SOS (정확한 sequence)
- HTF 추세: spring은 macro 우상향 또는 transition 구간에서 가장 강함
- Volume profile: TR low가 high-volume node와 일치 시 신뢰도 ↑
- RSI bullish divergence on the spring = confluence

**실패 케이스 / 함정**:
- Spring이 있는 줄 알았으나 진짜 breakdown (TR 영구 이탈) — distinguishing factor: spring 이후 SOS가 명확한가?
- 너무 weak한 SOS volume → spring 실패, 재차 하락
- Range가 충분히 길지 않으면 spring 가짜 가능 (random noise)
- 알트코인은 fundamental shock에 spring → breakdown 변환이 흔함

**출처**:
- [Wyckoff Analytics: The Wyckoff Method](https://www.wyckoffanalytics.com/wyckoff-method/)
- [Phemex Academy: Wyckoff Method Accumulation & Distribution](https://phemex.com/academy/wyckoff-accumulation)
- [LiteFinance: Wyckoff Method Theory & Patterns](https://www.litefinance.org/blog/for-professionals/wyckoff-method/)
- [Alchemy Markets: Wyckoff Distribution Trading Guide](https://alchemymarkets.com/education/guides/wyckoff-distribution/)

---

## 16. Connors RSI(2) — 단기 평균회귀 (보너스)

**개요**:
Larry Connors의 "Short Term Trading Strategies That Work" 저서에서 제시. RSI 길이를 14 → 2로 압축해 극단적 민감도. 단 2-3일의 oversold/overbought spike만 노리는 단기 평균회귀. **Trend filter (200 SMA)** 와 결합하여 trend 방향으로만 진입하는 것이 핵심.

**시그널 정의**:
- **Long Entry**:
  - `Close > SMA(200)` (장기 추세 상승)
  - AND `RSI(2) < 10` (이상적: < 5, deeper oversold = 더 큰 expected return)
  - Entry: 종가 직전 또는 다음 시가
- **Short Entry**: mirror, `Close < SMA(200)` AND `RSI(2) > 90`
- **Exit**:
  - Long exit: `Close > SMA(5)` (5-day SMA 위)
  - Short exit: `Close < SMA(5)`
  - **No fixed stop loss** (Connors 권장 — but 실전에서는 위험 관리상 -5% hard stop 추가)

**파라미터**:
- RSI length: 2
- Trend filter: SMA(200) — 일봉 기준
- Exit MA: SMA(5)
- OS/OB threshold: 10 / 90 (or 5 / 95 for extreme)

**결합 필터**:
- Daily TF가 원본 (lower TF 적용 시 noise 폭증)
- Liquid asset only (BTC, ETH, top-10 alts)
- Position sizing: pyramid (RSI < 10이면 1 unit, < 5면 추가 1 unit)

**실패 케이스 / 함정**:
- 2008/2020/2022 같은 long-duration bear에서는 SMA200 위 조건 자체가 거의 안 잡힘 → trade 적음
- Crypto의 경우 SMA200을 4H 기준으로 하면 trade 빈도 ↑ but 신뢰도 ↓
- News-driven crash 직후 진입 시 더 큰 손실 가능 (no SL)
- Mean reversion이 일어나기 전 추가 하락 자주 발생 → averaging down 위험

**출처**:
- [StockCharts: RSI(2)](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2)
- [Quantified Strategies: RSI 2 Strategy](https://www.quantifiedstrategies.com/rsi-2-strategy/)
- [Optionstradingiq: Larry Connors' 2-Period RSI Strategy](https://optionstradingiq.com/2-period-rsi-strategy/)
- [eLearnMarkets: Larry Connor's 2 Period RSI](https://blog.elearnmarkets.com/how-to-trade-larry-connors-2-period-rsi/)

---

## 17. 공통 함정 및 리스크 관리

### 17.1 가장 빈번한 실패 패턴

1. **Catching the falling knife**: 강추세 하락 중 mean reversion 진입 → 추가 50%+ 하락 → 청산
   - 방어: HTF EMA200 + ADX 필터 + reclaim candle 확인
2. **Trend regime mistake**: trending market에서 ranging market 전략 사용
   - 방어: ADX(14) < 20 게이트, Bollinger walking 검출 (#12)
3. **News-driven gap**: CPI, FOMC, 거래소 해킹, ETF 결정 등이 평균회귀 무효화
   - 방어: 경제 캘린더 ±2시간 회피, slippage 큰 SL 사용
4. **Funding rate squeeze**: extreme funding (±0.1%/8h)에서는 long/short squeeze로 평균회귀가 가속 또는 무효
   - 방어: funding rate를 추가 필터로 사용
5. **Liquidity vacuum**: 저유동성 알트는 평균회귀가 자주 깨짐
   - 방어: top-50 marketcap만, daily volume > $50M 페어만
6. **Regime shift**: cointegration breakdown, structural change → 통계적 가정 무효
   - 방어: rolling ADF/Hurst 재검증, 매주 파라미터 재추정

### 17.2 Position Sizing (평균회귀 공통)

- **Base risk**: 1R = account의 0.5-1.0% (variant on signal strength)
- **Pyramid**: signal이 더 extreme일수록 더 큰 size (e.g. RSI<10이 더 oversold면 1.5R)
- **Anti-martingale**: 손실 후 size 축소 (절대 averaging down 금지 — 평균회귀 전략의 최대 함정)
- **Max concurrent positions**: 3-5개 (correlation matrix 확인)

### 17.3 Backtest 검증 체크리스트

- 최소 3개 regime 포함 (bull, bear, chop) — 2018, 2021, 2022, 2024 등
- Walk-forward analysis (overfitting 방지)
- Slippage modeling: 0.1-0.3% per side (crypto realistic)
- Maker/taker fee 반영
- Funding cost 반영 (perpetual short positions)
- Out-of-sample test 필수

### 17.4 Mean Reversion vs Trend Following — 어느 것이 우월한가?

- **결론**: 시장 regime에 따라 다름. 백테스트(2017-2024) 기준:
  - Trend-following: 큰 bull/bear cycle에서 우월 (+3.0R/cycle)
  - Mean reversion: 횡보·choppy 구간에서 우월 (+1.45R/cycle but high frequency)
- **Best practice**: 두 전략을 ADX-based switch로 동시 운용 (ensemble)
- BTC-neutral residual mean reversion은 post-2021 regime에서 Sharpe ~2.3 보고됨

### 17.5 Crypto-specific Tips

- BTC dominance 변화 추적 → BTC-pair (BTC/USDT) 와 alt-pair (ETH/BTC) 동작이 다름
- Funding rate를 매 진입 시 확인 (Binance/Bybit perp)
- Open interest 급증 + extreme funding = squeeze 임박 → 평균회귀 진입 보류
- DEX vs CEX 가격 괴리 = 차익거래 기회지만 평균회귀 가정 외부 요인
- 주말 변동성 (특히 일요일 새벽 UTC) — 평균회귀 신호 신뢰도 낮음

### 17.6 자동화 시스템 권장 아키텍처

1. **Signal layer**: 본 문서의 각 #1-#16 기법을 modular strategy class로 구현 (`BaseStrategy` interface)
2. **Filter layer**: ADX, EMA200, walking detection, news calendar, funding rate
3. **Confluence layer**: 동시에 ≥2개 시그널 trigger 시에만 진입 (단일 시그널 reliability 낮음)
4. **Risk layer**: position sizing, SL placement, time stop, max DD halt
5. **Regime detection**: Hurst, ADF, BB walking → mean-reversion 전략 활성/비활성 toggle

### 17.7 출처 (공통/리스크)

- [Cryptohopper: 3 Ways to Catch a Falling Knife in Crypto](https://www.cryptohopper.com/blog/6334-3-effective-ways-to-catch-a-falling-knife-in-crypto)
- [Phemex Academy: What Is Falling Knife in Crypto](https://phemex.com/academy/what-is-falling-knife)
- [Medium / Briplotnik: Systematic Crypto Trading Strategies](https://medium.com/@briplotnik/systematic-crypto-trading-strategies-momentum-mean-reversion-volatility-filtering-8d7da06d60ed)
- [LuxAlgo: Mean Reversion Strategies for Algorithmic Trading](https://www.luxalgo.com/blog/mean-reversion-strategies-for-algorithmic-trading/)
- [Quantified Strategies: Mean Reversion Trading Strategies](https://www.quantifiedstrategies.com/mean-reversion-trading-strategy/)
- [Robuxio: Algorithmic Crypto Trading V — Mean Reversion](https://www.robuxio.com/algorithmic-crypto-trading-v-mean-reversion/)

---

## 부록 A. 기법별 적용 시간프레임 권장표

| Technique | Scalp (1m-5m) | Intraday (15m-1H) | Swing (4H-Daily) | Position (Weekly) |
|-----------|---------------|-------------------|------------------|-------------------|
| RSI OB/OS Reversal | 비추천 | 추천 | 추천 | 가능 |
| RSI Divergence | 비추천 | 가능 | 강력추천 | 추천 |
| MACD Divergence | 비추천 | 비추천 | 강력추천 | 추천 |
| BB Reversion | 비추천 | 추천 | 추천 | 비추천 |
| %B + RSI | 가능 | 강력추천 | 추천 | 비추천 |
| EMA bounce | 비추천 | 추천 | 강력추천 | 추천 |
| VWAP Reversion | 강력추천 | 강력추천 | 비추천 | 비추천 |
| Stochastic | 가능 | 추천 | 추천 | 비추천 |
| CCI Extreme | 비추천 | 추천 | 추천 | 가능 |
| Z-score | 가능 | 추천 | 강력추천 | 추천 |
| Pairs trading | 비추천 | 추천 | 강력추천 | 추천 |
| BB Walking (필터) | 가능 | 추천 | 강력추천 | 추천 |
| Williams %R | 가능 | 추천 | 추천 | 비추천 |
| Fibonacci | 비추천 | 추천 | 강력추천 | 강력추천 |
| Wyckoff Spring | 비추천 | 가능 | 강력추천 | 강력추천 |
| Connors RSI(2) | 비추천 | 비추천 | 비추천 | 강력추천 (Daily) |

## 부록 B. 시그널 confluence matrix (실전 진입 권장)

진입 confidence를 높이려면 다음 조합 중 ≥2개 동시 만족:

- A. RSI(14) < 30 + bullish reversal candle
- B. Close < BB Lower + %B < 0 + reclaim
- C. EMA(50) bounce + bullish candle
- D. Fib 0.618-0.65 (Golden Pocket) touch
- E. Wyckoff Spring (TR low wick + reclaim + SOS volume)
- F. Z-score < -2 (rolling 50)
- G. Stochastic %K < 20 cross up

**필수 negative filter (모두 통과해야 진입)**:
- N1. ADX(14) < 25
- N2. NOT walking the band (#12)
- N3. HTF EMA200 not strongly opposing
- N4. No major news event ±2 hours
- N5. Funding rate within ±0.05% / 8h

## 부록 C. 자동 전략 생성기를 위한 의사코드 (예시)

```python
def mean_reversion_long_signal(bar, htf_bar, indicators):
    # Negative filters first (regime gate)
    if indicators.adx_14 >= 25:
        return None
    if is_walking_lower_band(bar.history, lookback=5, touches=3):
        return None
    if htf_bar.ema_200_slope < -slope_threshold:
        return None
    if news_calendar.has_event_within(bar.time, hours=2):
        return None
    if abs(bar.funding_rate) > 0.0005:
        return None

    # Confluence scoring (need >= 2 of these)
    score = 0
    if indicators.rsi_14 < 30 and bar.close > bar.previous.low:
        score += 1
    if indicators.bb_pctb < 0 and bar.close > indicators.bb_lower:
        score += 1
    if abs(bar.close - indicators.ema_50) / bar.close < 0.005 \
       and bar.is_bullish_engulfing:
        score += 1
    if indicators.z_score_50 < -2.0:
        score += 1
    if is_in_golden_pocket(bar.close, indicators.fib_levels):
        score += 1
    if indicators.stoch_k < 20 and indicators.stoch_k_cross_up:
        score += 1

    if score >= 2:
        sl = bar.low - 1.0 * indicators.atr_14
        tp1 = indicators.bb_middle  # SMA20
        tp2 = indicators.bb_upper or indicators.prior_swing_high
        return LongSignal(entry=bar.close, sl=sl, tp1=tp1, tp2=tp2,
                         time_stop_bars=12, confidence=score)
    return None
```

---

**문서 끝.**
