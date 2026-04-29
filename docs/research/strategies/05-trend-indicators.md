# 05 — Trend-Following Indicator Strategies (추세 추종 지표 전략)

> 자동화된 quant strategy generator를 위한 reference. 각 기법은 정확한 entry/exit
> rule, default parameter, 결합 filter, 함정을 포함한다. 시장은 crypto 24/7
> (BTC/ETH/major altcoins on Binance, Bybit; spot + perp). 모든 신호는
> bar-close 기준이며, intra-bar 신호는 명시적으로 표시한다.

## 목차
1. [Moving Average Crossover (Golden / Death Cross)](#1-moving-average-crossover)
2. [EMA Stack / EMA Ribbon (GMMA)](#2-ema-stack--ema-ribbon)
3. [MACD (Signal/Zero/Histogram)](#3-macd)
4. [Ichimoku Kinko Hyo](#4-ichimoku-kinko-hyo)
5. [Supertrend (ATR Trend Filter)](#5-supertrend)
6. [Parabolic SAR](#6-parabolic-sar)
7. [ADX / DMI](#7-adx--dmi)
8. [Donchian Channel Trend (Turtle)](#8-donchian-channel-trend)
9. [VWAP / Anchored VWAP](#9-vwap--anchored-vwap)
10. [Heikin-Ashi Smoothing](#10-heikin-ashi-smoothing)
11. [Kaufman Adaptive MA (KAMA)](#11-kaufman-adaptive-ma-kama)
12. [Hull Moving Average (HMA)](#12-hull-moving-average-hma)
13. [Arnaud Legoux Moving Average (ALMA)](#13-arnaud-legoux-moving-average-alma)
14. [Linear Regression Slope / R-Squared](#14-linear-regression-slope--r-squared)
15. [DEMA / TEMA](#15-dema--tema)
16. [Keltner Channel Trend Riding](#16-keltner-channel-trend-riding)
17. [Higher-Highs / Higher-Lows Structure](#17-higher-highs--higher-lows-structure)
18. [Ehlers Fisher Transform](#18-ehlers-fisher-transform)
19. [Cross-Cutting Notes](#19-cross-cutting-notes)

---

## 1. Moving Average Crossover

### Golden Cross / Death Cross (50/200 SMA)
**개요**: 단기 SMA가 장기 SMA를 상향 돌파(Golden Cross) 또는 하향 돌파(Death
Cross)하면 macro trend shift signal. 50일 / 200일 SMA가 표준이며 lagging
indicator로 trend confirmation 용도. 수식: `SMA(n) = sum(close[t-n+1..t]) / n`.
가정: trend는 once established 면 mean보다 오래 지속된다 (momentum persistence).

**시그널 정의**:
- Entry (Long): `SMA(50) crosses above SMA(200)` AND `SMA(50) slope > 0`
  AND `SMA(200) slope >= 0` AND `close > SMA(50)`
- Entry (Short): `SMA(50) crosses below SMA(200)` AND `SMA(50) slope < 0`
  (crypto에서는 daily timeframe에서만 신뢰)
- Exit / SL:
  - Trailing stop: `close < SMA(50)` 또는 ATR(14) * 2.5 chandelier
  - Hard SL: 진입가 -7% (BTC daily)
  - Reverse signal: opposite cross 발생 시 즉시 close

**파라미터**:
- Default: SMA 50/200 (daily)
- Variants: 20/50 EMA (daily, 단기 trend), 9/21 EMA (4H, swing), 5/20 EMA (1H, intraday)
- Crypto-tuned: 20/55 EMA (daily) — Bitcoin halving cycle 친화적

**결합 필터**:
- ADX(14) > 20: trending phase 확인
- Volume: golden cross day의 volume이 20-day avg volume 대비 > 1.2x
- HTF alignment: weekly close > weekly SMA(50)
- BTC.D filter: BTC dominance trend 일치 (alt 거래 시)

**실패 케이스 / 함정**:
- Whipsaw / chop market: 횡보 시 50/200 SMA가 반복적으로 cross — 1-3% 손실 다발
- Lag: 200일 SMA는 long bull run 종료 직후에 death cross 발생 → 저점 매도
- Signal frequency 낮음 (66년 backtest에서 33회): out-of-sample variance 큼
- BTC 강세장에서 alt golden cross 시 이미 +200% 상승한 후인 경우 多
- Reinvested-dividends 가정 부재 시 raw return은 buy-and-hold 대비 underperform

**출처**:
- [QuantifiedStrategies — Golden Cross Trading Strategy](https://www.quantifiedstrategies.com/golden-cross-trading-strategy/)
- [QuantifiedStrategies — Death Cross 65-Year Backtest](https://www.quantifiedstrategies.com/death-cross-in-trading/)
- [TOS Indicators — 20-Year S&P 500 Backtest](https://tosindicators.com/research/golden-cross-trading-strategy-20-year-backtest-results)
- [Trading Heroes — 50/200 MA Crossover Automation](https://www.tradingheroes.com/no-code-automated-50-200-ma-crossover/)

---

## 2. EMA Stack / EMA Ribbon

### EMA Stack (8/13/21/55) and GMMA (Guppy Multiple Moving Average)
**개요**: 다중 EMA가 동일 방향으로 정렬(stacked)되면 강한 추세, fanned-out
spacing은 momentum 강도를 나타낸다. EMA 수식:
`EMA = (close * α) + (EMA[t-1] * (1-α))`, `α = 2/(n+1)`. 가정: 단기/중기/장기
시간대 합의(consensus)가 추세 신뢰도를 높인다.

**시그널 정의**:
- Entry (Long): `EMA8 > EMA13 > EMA21 > EMA55` AND `close > EMA8`
  AND ribbon 간격 expanding (각 EMA spacing이 직전 5 bars 평균보다 크다)
- Entry GMMA Long: short group `EMA(3,5,8,10,12,15)` 전부 long group
  `EMA(30,35,40,45,50,60)` 위에 있고, two groups 간 separation widening
- Exit / SL:
  - 첫번째 cross-down: `EMA8 < EMA13` → partial exit (50%)
  - Full exit: `close < EMA21` (ribbon mid)
  - Trailing stop: `EMA21 - 1.0 * ATR(14)`
- Re-entry rule: stack alignment 회복 + close > EMA8 시 재진입

**파라미터**:
- 4-EMA stack: 8/13/21/55 (Fibonacci-based, swing trading 표준)
- GMMA short group: 3, 5, 8, 10, 12, 15
- GMMA long group: 30, 35, 40, 45, 50, 60
- Crypto variant: 9/21/50/200 EMA (BTC daily)
- Scalping: 5/10/20 EMA (5min)

**결합 필터**:
- ADX(14) > 25 (trend strength gate)
- Volume confirmation: ribbon 형성 직후 3-bar volume MA > 20-bar volume MA
- HTF: HTF EMA stack도 같은 방향 (15min entry → 1H trend)
- Compression detection: ribbon width / close < 0.5% → entry 보류 (chop 위험)

**실패 케이스 / 함정**:
- Compressed/intertwined ribbon: trend 부재 → entry 금지 (Guppy 핵심 룰)
- Late entry: ribbon이 fully fanned-out 후 진입하면 trend 후반부 진입
- Short-group whipsaw: EMA8/EMA13 cross가 noise (특히 1H 이하)
- Crypto weekend low-volume: ribbon이 false-stack 형성 후 월요일 무너짐
- 4H timeframe에서 funding rate 시점과 cross 일치 시 false break 빈번

**출처**:
- [StockCharts ChartSchool — GMMA](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/moving-average-trading-strategies/guppy-multiple-moving-average-an-ma-ribbon-designed-to-tip-the-markets-hand)
- [BabyPips — Trend Trading with GMMA](https://www.babypips.com/learn/forex/guppy-multiple-moving-average)
- [LiteFinance — GMMA Calculation & Strategy](https://www.litefinance.org/blog/for-beginners/best-technical-indicators/guppy-multiple-moving-average/)
- [Capital.com — GMMA Indicator Guide](https://capital.com/en-int/learn/technical-analysis/gmma-indicator)

---

## 3. MACD

### MACD (Moving Average Convergence Divergence)
**개요**: `MACD = EMA(12) - EMA(26)`, `Signal = EMA(MACD, 9)`, `Histogram = MACD - Signal`. Gerald Appel(1979) 개발. Trend + momentum 동시 측정. Zero line cross는 macro EMA cross, signal cross는 micro momentum shift, histogram slope는 가장 빠른 leading proxy.

**시그널 정의**:
- Entry (Long, conservative): `MACD > 0` AND `MACD crosses above Signal` AND `Histogram > 0 and rising 2 consecutive bars`
- Entry (Long, aggressive): `Histogram crosses above 0` (가장 빠른 timing, noise 많음)
- Entry (Long, zero-line): `MACD crosses above 0` AND price > EMA(50)
- Exit / SL:
  - Reverse: `MACD crosses below Signal`
  - Histogram divergence: 가격 HH인데 hist LH → exit
  - SL: ATR(14) * 2 below entry
- Bearish setup: 상기 모두 부호 반전

**파라미터**:
- Default: 12/26/9 (Appel original, daily)
- Faster (intraday): 5/35/5, 3/10/16
- Crypto longer-term: 19/39/9 (daily, BTC volatility 흡수)
- Weekly trend: 12/26/9 on weekly bars

**결합 필터**:
- 위치 필터: histogram cross가 zero line 위에서 발생할 때 long 신호 강도↑
- Trend filter: MACD signal cross는 close > SMA(200)일 때만 take
- Divergence: 가격 HH + MACD LH = bearish divergence (top warning)
- RSI(14) 50 cross alignment

**실패 케이스 / 함정**:
- Whipsaw zone (MACD ~ 0): zero line 근처에서 다중 cross → noise
- Lag: 두 EMA 기반이라 본질적으로 lagging — sharp reversal 따라잡지 못함
- Crypto pump candle: 한 큰 봉에 hist 급변 → 다음 봉 mean-reversion
- Divergence는 signal이 아닌 warning (단독 사용 위험)
- Default 12/26/9는 stocks daily 최적 — crypto 1H/15m에서는 너무 느림

**출처**:
- [altFINS — MACD Complete 2026 Guide](https://altfins.com/knowledge-base/macd-line-and-macd-signal-line/)
- [Phemex Academy — MACD Crypto Trading](https://phemex.com/academy/macd-indicator-crypto-trading)
- [Capital.com — MACD Best Settings](https://capital.com/en-int/learn/technical-analysis/macd-trading-strategy)
- [Mind Math Money — MACD Components](https://www.mindmathmoney.com/articles/understanding-the-macd-indicator-macd-line-signal-line-histogram-crossover-and-zero-line)

---

## 4. Ichimoku Kinko Hyo

### Ichimoku Cloud (一目均衡表)
**개요**: Goichi Hosoda(細田悟一, pen name "Ichimoku Sanjin") 1930년대~1968 공개. "한눈(一目)에 균형(均衡)을 보는 차트(表)". 5 lines: Tenkan-sen(9), Kijun-sen(26), Senkou Span A, Senkou Span B(52), Chikou Span(26 lagging).
- `Tenkan = (High9 + Low9) / 2`
- `Kijun  = (High26 + Low26) / 2`
- `Span A = (Tenkan + Kijun) / 2`, projected +26
- `Span B = (High52 + Low52) / 2`, projected +26
- `Chikou = Close`, plotted -26

**시그널 정의**:
- Strong Long entry: `close > Kumo` AND `Tenkan > Kijun` AND `Chikou > price[26 ago]` AND `future Kumo green (Span A > Span B)`
- TK Cross Long: `Tenkan crosses above Kijun` 발생 위치 분류
  - Above Kumo: strong bullish
  - Inside Kumo: neutral (skip)
  - Below Kumo: weak bullish (counter-trend, smaller size)
- Cloud breakout: `close crosses above Kumo top` → momentum entry
- Kumo twist: `Span A crosses above Span B` (forward 26 bars) → trend shift warning, 26 bar 후 신호 활성
- Exit / SL:
  - `close < Kijun-sen` → partial exit
  - `close < Kumo bottom` → full exit
  - SL: below most recent Kijun-sen low

**파라미터**:
- Default: 9/26/52/26 (Hosoda 원본, 일본 주 6일 작업주 기반)
- Modern 5-day week 변형: 7/22/44/22 또는 8/22/44/22
- Crypto 24/7 변형: 10/30/60/30 또는 20/60/120/30 (daily)
- Confidence: Hosoda original 9/26/52를 그대로 쓰는 게 community standard

**결합 필터**:
- Kumo thickness: `|Span A - Span B|`가 ATR(14) * 1.5 이상이면 강한 S/R
- Volume on cloud breakout
- HTF alignment: 4H Ichimoku 모든 component bullish AND 1H entry signal
- Chikou clear space: chikou 주변 26 bars에 price 충돌 없을 것

**실패 케이스 / 함정**:
- Inside-cloud whipsaw: 가격이 Kumo 내부에서 진동 시 모든 component noise
- Forward projection 26 bars: real-time signal 평가 시 미래 Kumo는 변동 가능
- Crypto flash crash: Tenkan/Kijun 즉시 break → late SL
- Late TK cross below Kumo: counter-trend trap
- 일본 시장 기반 parameter — crypto 24/7에 그대로 적용 시 weekly-effect 부재
- Chikou 해석 misinterpret: chikou는 "26 bar 전 가격과 비교"인데 "현재 close 다른 line과 비교"로 잘못 사용

**출처**:
- [Wikipedia — Ichimoku Kinkō Hyō](https://en.wikipedia.org/wiki/Ichimoku_Kink%C5%8D_Hy%C5%8D)
- [Technical Analysis Pro — How to Trade Ichimoku Cloud](https://www.technical-analysis-pro.com/indicators-ichimoku-cloud/)
- [PrimeXBT — Ichimoku Settings & Strategy](https://primexbt.com/for-traders/ichimoku-cloud/)
- [Medium — SmokeyHosoda Comprehensive Guide](https://medium.com/@SmokeyHosoda/a-comprehensive-guide-to-ichimoku-kinko-hyo-e5ed286c3258)

---

## 5. Supertrend

### Supertrend (ATR-based Trend Filter)
**개요**: Olivier Seban 개발 (출처: French trading community). ATR로 동적 upper/lower band 계산하고, 가격 위치에 따라 line이 flip하면서 trailing stop 역할. 수식:
- `Basic Upper = (H+L)/2 + multiplier * ATR(n)`
- `Basic Lower = (H+L)/2 - multiplier * ATR(n)`
- Final band는 직전 close에 따라 ratchet (uptrend lower band only ratchet up)
- Trend flip 시 line이 즉시 반대편으로 jump

**시그널 정의**:
- Entry (Long): `close crosses above Supertrend line` (red→green flip)
- Entry (Short): `close crosses below Supertrend line` (green→red flip)
- Exit / SL:
  - Stop = Supertrend line itself (built-in trailing stop)
  - Reverse signal = exit + flip (always-in system)
- Filter mode: signal만 trend bias로 사용, entry는 별도 trigger (e.g. EMA cross within trend) — fewer trades, higher quality

**파라미터**:
- Default: ATR(10), multiplier 3 (Seban 원본)
- Conservative: ATR(14), multiplier 3.5 — fewer signals, less whipsaw
- Aggressive intraday: ATR(7), multiplier 2 — scalp setup
- Crypto BTC 4H: ATR(10), multiplier 3 (community 표준)
- Crypto altcoin: ATR(14), multiplier 3 (변동성 높음 흡수)

**결합 필터**:
- 5 EMA / 20 EMA cross 일치 시 entry trigger
- ADX(14) > 25
- HTF Supertrend trend 일치 (4H supertrend bullish + 15min flip = entry)
- Volume spike on flip bar (current vol > 1.5 * 20-bar avg)

**실패 케이스 / 함정**:
- Sideways market: Supertrend 빈번한 flip → death by 1000 cuts
- Single-bar wick break: high volatility candle wick으로 line 터치 후 close 복귀 시 false flip
- Multiplier 너무 작으면 (≤2) noise, 너무 크면 (≥4) late
- Crypto perp funding flip 시점 false signal
- Standalone Supertrend strategy backtest는 trend market only (BTC 2017, 2020-2021)에서만 강함

**출처**:
- [TradingView — Supertrend Solution](https://www.tradingview.com/support/solutions/43000634738-supertrend/)
- [LiteFinance — Supertrend Formula & Strategies](https://www.litefinance.org/blog/for-beginners/best-technical-indicators/supertrend-indicator/)
- [TrendSpider — Supertrend Comprehensive Guide](https://trendspider.com/learning-center/supertrend-indicator-a-comprehensive-guide/)
- [GoodCrypto — Supertrend Crypto Strategy](https://goodcrypto.app/supertrend-indicator-how-to-set-up-use-and-create-profitable-crypto-trading-strategy/)

---

## 6. Parabolic SAR

### Parabolic Stop and Reverse (PSAR)
**개요**: J. Welles Wilder Jr.(1978, "New Concepts in Technical Trading Systems") 개발. Trend 진행 시 dot이 시간에 따라 가속하며 가격 반대편에 plotted. Trend reversal 시 dot이 반대편으로 jump (always-in). 수식:
- Uptrend: `PSAR[t] = PSAR[t-1] + AF * (EP - PSAR[t-1])`
- Downtrend: `PSAR[t] = PSAR[t-1] - AF * (PSAR[t-1] - EP)`
- `AF (Acceleration Factor)`: start 0.02, +0.02 per new EP, max 0.20
- `EP (Extreme Point)`: trend 동안의 highest high (long) / lowest low (short)

**시그널 정의**:
- Entry (Long): `PSAR flips below price` (dot jumps from above to below) AND price > 50 EMA
- Entry (Short): `PSAR flips above price`
- Exit / SL:
  - Stop = PSAR dot (trailing built-in)
  - Reverse = always-in flip
- Best practice: PSAR를 trailing stop only로, entry는 다른 indicator로

**파라미터**:
- Default: AF start 0.02, increment 0.02, max 0.20 (Wilder)
- Conservative (less whipsaw): increment 0.01, max 0.10
- Aggressive: increment 0.04, max 0.30
- Crypto 4H: 0.02 / 0.02 / 0.20 그대로 사용

**결합 필터**:
- ADX(14) > 25 (Wilder가 명시적으로 권고: PSAR는 trending market only)
- 200 EMA trend filter
- Volume confirmation on flip
- Time-of-day filter (crypto: avoid Asian thin liquidity hours for entry)

**실패 케이스 / 함정**:
- Sideways market: 빈번한 flip — Wilder 본인이 "trending only" 강조
- 첫 flip 직후 가격이 PSAR로 즉시 복귀 (noise) → 짧은 trade로 fee 누적
- Acceleration max(0.20) 도달 후 trend 끝나면 dot이 매우 가까워서 작은 pullback에 stop-out
- Crypto wick에 stop-hunt: PSAR dot이 round number 근처에 있으면 hunted
- Always-in 모드는 chop에서 매번 손실 — 반드시 ADX gate 필요

**출처**:
- [Wikipedia — Parabolic SAR](https://en.wikipedia.org/wiki/Parabolic_SAR)
- [TradingView — Parabolic SAR Solution](https://www.tradingview.com/support/solutions/43000502597-parabolic-sar-sar/)
- [QuantInsti — PSAR Python Code](https://blog.quantinsti.com/parabolic-sar/)
- [TrendSpider — PSAR Strategy Guide](https://trendspider.com/learning-center/optimizing-your-trading-strategy-with-the-parabolic-sar-indicator/)

---

## 7. ADX / DMI

### Average Directional Index & Directional Movement Index
**개요**: Wilder(1978) 개발. ADX는 trend의 강도(direction-agnostic), +DI/-DI는 방향. 수식:
- `+DM = high - high[1]` if positive and > -DM, else 0
- `-DM = low[1] - low` if positive and > +DM, else 0
- `+DI = 100 * EMA(+DM, 14) / ATR(14)`
- `-DI = 100 * EMA(-DM, 14) / ATR(14)`
- `DX = 100 * |+DI - -DI| / (+DI + -DI)`
- `ADX = EMA(DX, 14)` (Wilder smoothing)

**시그널 정의**:
- Trend strength gate: `ADX > 25` (strong trend), `ADX > 20` (developing)
- Entry (Long): `ADX > 25` AND `+DI > -DI` AND `+DI crosses above -DI`
- Entry (Short): `ADX > 25` AND `-DI > +DI` AND `-DI crosses above +DI`
- ADX rising filter: `ADX > ADX[3]` (강도 증가 중)
- Exit / SL:
  - DI cross opposite direction
  - ADX crosses below 20 (trend dissipating)
  - SL: ATR(14) * 2

**파라미터**:
- Default: 14 (Wilder)
- Faster: 7 또는 9 (intraday, 4H crypto)
- Slower / smoother: 21 (weekly bias)
- Strength thresholds: 0-20 weak, 20-25 developing, 25-50 strong, >50 very strong (overheated)

**결합 필터**:
- ADX는 자체로 standalone entry 부적합 — 항상 directional indicator (DI cross, EMA cross)와 결합
- Trend filter: 4H ADX > 25 일 때만 1H trade
- Avoid `ADX > 50` 진입 (trend 후반, mean-reversion 위험)
- Volume confirmation on DI cross

**실패 케이스 / 함정**:
- ADX는 lagging — 이미 strong trend 진입한 후에야 25 돌파
- Range market에서 +DI/-DI cross 빈발 (ADX <20일 때 모두 무효)
- Crypto: ADX(14) on 1H가 4H trend 따라잡지 못함 (HTF gate 필수)
- ADX의 absolute level은 asset/timeframe별로 차이 — 30이 BTC daily에서는 보통, 5min에서는 매우 강함 (z-score 변환 권장)
- Wilder smoothing vs RMA vs SMA 구현 차이 — 라이브러리 검증 필요

**출처**:
- [TradingView — ADX Scripts & Indicator](https://www.tradingview.com/scripts/averagedirectionalindex/)
- [Liberated Stock Trader — ADX Strategies](https://www.liberatedstocktrader.com/adx-indicator/)
- [Phemex Academy — DMI ADX Crypto](https://phemex.com/academy/how-to-trade-crypto-using-dmi-adx)
- [Interactive Brokers — ADX/DMI Lesson](https://www.interactivebrokers.com/campus/trading-lessons/adx-dmi/)

---

## 8. Donchian Channel Trend

### Donchian Channel (Turtle Breakout)
**개요**: Richard Donchian 개발(1960s). 단순한 highest high / lowest low channel. Richard Dennis "Turtle Trading"(1983) 시스템 backbone. 수식:
- `Upper = max(High, n)`
- `Lower = min(Low, n)`
- `Mid = (Upper + Lower) / 2`

본 문서에서는 **trend filter 용도** (단순 breakout entry는 별도 문서 참조).

**시그널 정의**:
- Trend bias: `close > Donchian Mid(20)` → bullish bias
- Trend Long entry: `close breaks above Donchian Upper(55)` (System 2, major trend) AND `close > 200 EMA`
- Trend Short entry: `close breaks below Donchian Lower(55)`
- Pullback re-entry within trend: trend bullish (above mid) AND close pulls back to Donchian Lower(20) AND bullish reversal candle
- Exit / SL:
  - Long exit: `low < Donchian Lower(10)` (Turtle 10-day exit rule)
  - Short exit: `high > Donchian Upper(10)`
  - Initial SL: 2 * N (where N = ATR(20)) below entry

**파라미터**:
- Turtle System 1: 20 entry / 10 exit (short-term, with skip-rule on prior winner)
- Turtle System 2: 55 entry / 20 exit (long-term, no skip rule)
- Crypto BTC daily: 20/10 (활성 trend)
- Position sizing: 1 N = 0.5% account risk, 1 N = 1 ATR(20) move

**결합 필터**:
- 200 EMA macro trend filter
- ADX(14) > 25
- Volume on breakout
- Avoid breakout into known resistance (recent rejection level within ATR)
- Skip rule: 직전 20-day breakout이 winning trade였다면 skip (Turtle System 1)

**실패 케이스 / 함정**:
- Crypto는 알고리즘 high-frequency 환경 → 단순 Donchian breakout false signal 증가 (Turtle 본래 design은 1980s commodities)
- 55-day breakout은 BTC에서 연 5-8회만 발생 (low frequency)
- Stop hunt: round-number Donchian level은 뻔한 stop cluster
- Channel width = volatility — wide channel일 때 entry 후 즉시 mean-revert
- Skip rule 없이 사용 시 winning streak 종료 후 큰 loss 흡수

**출처**:
- [Lizard Indicators — Turtle Donchian Strategy](https://www.lizardindicators.com/donchian-channel-strategy/)
- [Altrady — Turtle Trading Strategy Rules](https://www.altrady.com/blog/crypto-trading-strategies/turtle-trading-strategy-rules)
- [Tradeciety — Donchian Trend Following](https://tradeciety.com/donchian-channel-trading-indicator-tips)
- [Deepvue — Donchian Breakout Trader Radar](https://deepvue.com/indicators/donchian-channels-the-breakout-traders/)

---

## 9. VWAP / Anchored VWAP

### Volume Weighted Average Price
**개요**: `VWAP = Σ(typical_price * volume) / Σ(volume)`, where `typical_price = (H+L+C)/3`. Daily VWAP은 매일 session open에 reset (crypto는 00:00 UTC가 community 표준). Anchored VWAP(AVWAP, Brian Shannon)은 임의의 시점부터 cumulative — 주요 event(low, high, breakout, halving, ATH)에 anchor. 가정: 기관 trader가 large order를 VWAP 근처에서 split 실행하므로 VWAP은 실제 institutional cost basis.

**시그널 정의**:
- Trend bias: `close > VWAP_daily` → intraday bullish bias
- AVWAP Long entry (pullback): trend bullish + price pulls back to AVWAP anchored at recent significant low + bullish reaction candle
- AVWAP rejection short: trend bearish + price rallies to AVWAP from major high → rejection wick + close < AVWAP → short
- Multi-AVWAP confluence: 3+ different AVWAP levels (halving, recent ATH, recent low)이 좁은 range 내 모이면 strong S/R cluster
- Exit / SL:
  - SL: 1 ATR beyond AVWAP (whipsaw 방지)
  - TP: opposite AVWAP 또는 직전 swing extreme

**파라미터**:
- Daily VWAP reset: 00:00 UTC (crypto 표준)
- 1σ / 2σ Bollinger-style bands: VWAP ± k * std (k=1, 2, 3) — extension levels
- AVWAP anchor candidates: ATH, ATL, halving date, FOMC bar, large gap day, earnings (TradFi), exchange listing date, ETF approval bar (BTC)

**결합 필터**:
- HTF trend (200 EMA) 일치
- Volume profile / POC confluence
- Time-of-day: institutional flow strongest at NY open (13:30 UTC)
- AVWAP slope: AVWAP slope > 0 일 때만 long bias

**실패 케이스 / 함정**:
- Crypto 24/7 session 정의 모호 — UTC vs CST vs JST anchor 결과 다름
- Low volume hours (Asian early): VWAP이 light volume bar에 압도되어 왜곡
- Anchor selection bias: hindsight로 깔끔한 anchor 골라 backtest overfit
- VWAP 초기 (session open 후 ~1 hour) noisy — 첫 1시간 거래 회피 권장
- Perpetual swap funding 시각의 spike가 typical_price 왜곡 (typical은 fair price 아님 → mark price 사용 권장)

**출처**:
- [TrendSpider — Anchored VWAP Strategies](https://trendspider.com/learning-center/anchored-vwap-trading-strategies/)
- [Alphatrends (Brian Shannon) — Master AVWAP](https://alphatrends.net/anchored-vwap/)
- [HyroTrader — VWAP in Crypto](https://www.hyrotrader.com/blog/vwap-trading-strategy/)
- [Mudrex — VWAP in Crypto 2025 Tips](https://mudrex.com/learn/vwap-in-crypto/)

---

## 10. Heikin-Ashi Smoothing

### Heikin-Ashi Candles (平均足)
**개요**: 일본어 "balance bar". 표준 OHLC 대신 averaged candle 사용으로 short-term noise 제거. 수식:
- `HA-Close = (O + H + L + C) / 4`
- `HA-Open = (HA-Open[t-1] + HA-Close[t-1]) / 2` (seed bar는 (O+C)/2)
- `HA-High = max(High, HA-Open, HA-Close)`
- `HA-Low  = min(Low,  HA-Open, HA-Close)`

가정: synthetic averaged candle는 trend는 보존하고 noise만 제거 → "끊김 없는" 연속 동색 캔들이 강한 trend 시각화.

**시그널 정의**:
- Trend Long: 3+ 연속 green HA candle AND no lower wick (강한 buying pressure)
- Trend Short: 3+ 연속 red HA candle AND no upper wick
- Reversal warning: 동색 연속 후 doji-like HA candle (small body + 양쪽 wick)
- Entry rule: standard candle close > previous HA-High AND HA candle green
- Exit / SL:
  - First opposite-color HA candle → partial exit
  - Lower wick 처음 등장 (long trend 중) → trail SL up
  - Hard SL: HA-Low of entry candle - 1 ATR

**파라미터**:
- HA는 parameter-free (transform on raw OHLC)
- 변형: HA on EMA-smoothed OHLC (double smoothing) — 더 느린 신호
- Timeframe: 1H/4H/daily에서 가장 효과적, 15min 이하는 over-smoothed

**결합 필터**:
- HA 위에 EMA(20) overlay
- HTF HA trend 일치
- Volume on first opposite candle
- ADX > 20 trend gate

**실패 케이스 / 함정**:
- HA close ≠ real close — actual fill price와 차이 발생 (backtest 시 real close 사용 필수)
- "No lower wick" 조건은 strong trend에서만 — 실제로는 1-2 bar 후 즉시 wick 나타남
- Reversal 신호 시점이 1 bar 늦음 (HA-Open에 lag 내재)
- Over-smoothing: 중요한 reversal candle (대형 engulfing 등) shape 사라짐
- Backtest 함정: HA candle 자체를 entry 가격으로 가정하면 실제 fill 차이로 큰 slippage

**출처**:
- [Britannica Money — Heikin-Ashi Calculation](https://www.britannica.com/money/heikin-ashi-candlestick-chart)
- [LuxAlgo — Smooth Trend Detection](https://www.luxalgo.com/blog/heikin-ashi-candles-smooth-trend-detection/)
- [Corporate Finance Institute — HA Technique](https://corporatefinanceinstitute.com/resources/career-map/sell-side/capital-markets/heikin-ashi-technique/)
- [OANDA — HA Charts Explained](https://www.oanda.com/us-en/trade-tap-blog/trading-knowledge/heikin-ashi-candles-explained/)

---

## 11. Kaufman Adaptive MA (KAMA)

### Kaufman's Adaptive Moving Average
**개요**: Perry J. Kaufman("Smarter Trading", 1995) 개발. Efficiency Ratio(ER)로 trending vs noisy 구분하여 smoothing constant를 동적 조절. 수식:
- `Change = |close[t] - close[t-n]|`
- `Volatility = Σ(|close[i] - close[i-1]|, n)`
- `ER = Change / Volatility` (0~1, 1=perfect trend)
- `SC = (ER * (FastSC - SlowSC) + SlowSC)^2`
  - `FastSC = 2/(2+1)`, `SlowSC = 2/(30+1)`
- `KAMA[t] = KAMA[t-1] + SC * (close - KAMA[t-1])`

**시그널 정의**:
- Trend bias: `KAMA slope > 0` over last 5 bars
- Entry (Long): `close crosses above KAMA` AND KAMA slope > 0
- Entry (Short): `close crosses below KAMA` AND KAMA slope < 0
- Dual KAMA cross: `KAMA(10,5,30) > KAMA(40,5,30)` for long bias
- Exit / SL:
  - Cross opposite direction
  - Slope flip
  - SL: ATR(14) * 2 from KAMA

**파라미터**:
- Default (Kaufman): 10 / 2 / 30 — ER period / fast EMA / slow EMA
- Variants:
  - Slower: 21 / 2 / 30 (fewer signals)
  - Crypto BTC daily: 10 / 2 / 30 그대로 사용
  - Filter mode: 50 / 2 / 30 (smooth trend filter)

**결합 필터**:
- ADX(14) > 20
- ER > 0.3 entry threshold (avoid pure chop)
- HTF trend filter

**실패 케이스 / 함정**:
- Adaptive 특성으로 chop 시에 거의 평평한 line — entry signal 자체가 빈번하지 않으나 일단 발생 시 false 비율 still high
- 구현체 차이 큼: Pine, TradingView, TA-Lib KAMA 결과 미세하게 다름 (특히 seed bar 처리)
- Backtest에서 buy-and-hold outperform 시기 있음 (BTC strong bull)
- ER 계산이 lookback dependent — n 변경 시 결과 크게 변동

**출처**:
- [StockCharts ChartSchool — KAMA](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/kaufmans-adaptive-moving-average-kama)
- [CFI — KAMA Calculation Overview](https://corporatefinanceinstitute.com/resources/career-map/sell-side/capital-markets/kaufmans-adaptive-moving-average-kama/)
- [QuantifiedStrategies — Adaptive MA Backtest](https://www.quantifiedstrategies.com/adaptive-moving-average/)
- [TrendSpider — KAMA Guide](https://trendspider.com/learning-center/what-is-the-kaufman-adaptive-moving-average/)

---

## 12. Hull Moving Average (HMA)

### Hull Moving Average
**개요**: Alan Hull(2005) 개발. Lag 최소화 + smoothing 보존을 동시에 노린 weighted MA 변형. 수식:
- `HMA(n) = WMA( 2 * WMA(close, n/2) - WMA(close, n), sqrt(n) )`
- `WMA(close, k) = Σ(close[i] * w[i]) / Σ(w[i])`, where `w[i] = i+1`

가정: 짧은 WMA를 두 배 가중하고 긴 WMA를 빼서 lag 상쇄, 마지막 sqrt(n) WMA로 smoothing 회복.

**시그널 정의**:
- Hull 본인 권고: **crossover가 아닌 turning point**(slope change) 사용
- Entry (Long): `HMA slope flips positive` (HMA[t] > HMA[t-1] for first time after downturn)
- Entry (Short): `HMA slope flips negative`
- Crossover variant (Hull non-recommended but popular): `close > HMA` long
- Dual HMA: `HMA(20) > HMA(55)` for long bias
- Exit / SL:
  - Slope reverse
  - Cross opposite
  - SL: ATR * 1.5 below HMA

**파라미터**:
- Default: 16 (Hull 권장 swing trading)
- Common: 21, 55
- Crypto 1H scalping: HMA(9) for entries
- Trend filter: HMA(200)

**결합 필터**:
- Volume confirmation
- ADX > 20
- HTF HMA slope alignment

**실패 케이스 / 함정**:
- Sharp reversal 시 HMA가 빠르게 따라가서 slope flip 빈번 — chop에서 false
- Hull은 crossover 사용 비권고했지만 community에서 흔히 사용 → 신뢰도 낮음
- sqrt(n) 정수화 처리 차이로 라이브러리 결과 미세 차이
- Reduced lag = increased noise sensitivity (특히 5min 이하 timeframe)

**출처**:
- [Alan Hull — Official HMA Page](https://alanhull.com/the-hull-moving-average/)
- [StockCharts ChartSchool — HMA](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/hull-moving-average-hma)
- [Fidelity — Hull Moving Average](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/hull-moving-average)
- [Incredible Charts — HMA Indicator](https://www.incrediblecharts.com/indicators/hull-moving-average.php)

---

## 13. Arnaud Legoux Moving Average (ALMA)

### ALMA
**개요**: Arnaud Legoux & Dimitrios Kouzis Loukas(2009) 개발. Gaussian-weighted moving average with offset shift toward recent bars. 수식:
- `w[i] = exp(-(i - m)^2 / (2 * s^2))`
- `m = offset * (window - 1)` (Gaussian peak 위치)
- `s = window / sigma` (width)
- `ALMA = Σ(close[t-window+1+i] * w[i]) / Σ(w[i])`

가정: Gaussian 분포로 오래된 데이터 weight 부드럽게 감쇠 + offset으로 최근 bar에 peak 이동 = smoothness와 responsiveness 균형.

**시그널 정의**:
- Entry (Long): `close > ALMA` AND `ALMA slope > 0`
- Entry (Short): `close < ALMA` AND `ALMA slope < 0`
- Dual ALMA cross: `ALMA(9) crosses above ALMA(21)` long
- Exit / SL: opposite cross, slope flip, ATR-based SL

**파라미터**:
- Default: window=9, offset=0.85, sigma=6
- Smoother: window=21, offset=0.85, sigma=6
- Faster (responsive): window=9, offset=0.95, sigma=6
- Crypto 4H: 14 / 0.85 / 6
- Sigma는 6 유지 권장 (Six Sigma 영감)

**결합 필터**:
- HTF ALMA trend 일치
- Volume confirmation
- ADX > 20

**실패 케이스 / 함정**:
- Offset → 1 가까이: 과도한 responsive → noise
- Offset → 0: 과도한 lag → 일반 SMA 수준
- 라이브러리 구현 차이: Gaussian 정규화 방식 다름 (Pine vs TA-Lib)
- HMA처럼 reduced lag 트레이드오프 — sharp wick에 민감
- Sigma 변경 시 weight 분포 급변 — backtest 시 fine-tune 위험 (overfit)

**출처**:
- [TradingView — ALMA Solution](https://www.tradingview.com/support/solutions/43000594683-arnaud-legoux-moving-average/)
- [TradingCode — Pine Script ALMA](https://www.tradingcode.net/tradingview/arnaud-legoux-average/)
- [LuxAlgo — ALMA Guide](https://www.luxalgo.com/blog/arnaud-legoux-moving-average-alma-guide/)
- [TrendSpider — ALMA KB](https://help.trendspider.com/kb/indicators/arnaud-legoux-moving-average-alma)

---

## 14. Linear Regression Slope / R-Squared

### LR Slope and R² (Trend Strength via Statistics)
**개요**: 가격 series에 OLS linear regression fit. Slope는 단위시간당 가격 변화율 (trend 방향 + 강도), R²는 fit quality (0~1, 1=perfect linear). 수식:
- `slope = Σ((x_i - x̄)(y_i - ȳ)) / Σ(x_i - x̄)^2`
- `R² = 1 - (SS_res / SS_tot)`
- `SS_res = Σ(y_i - ŷ_i)^2`, `SS_tot = Σ(y_i - ȳ)^2`

가정: trend가 directional movement에서 통계적으로 유의미하면 slope ≠ 0 AND R² 충분히 높다.

**시그널 정의**:
- Trend bias: `slope(20) > 0` AND `R²(20) > 0.7`
- Entry Long: slope cross above 0 AND R² > 0.6 AND price > LR_line
- Entry Short: slope cross below 0 AND R² > 0.6
- Slope strength: slope normalized as `slope / close * 100` (% per bar)
- Exit / SL:
  - Slope cross 0
  - R² drops below 0.4 (trend 통계적 약화)
  - SL: 2 * standard error of regression below entry

**파라미터**:
- LR length: 20 (swing), 14 (intraday), 50 (long-term)
- R² threshold: 0.7 (strong), 0.5 (moderate), 0.85 (very strong, Phemex 권장)
- 95% confidence: R² > 0.85 for n=20
- Crypto BTC daily: LR(20), R² > 0.7

**결합 필터**:
- Slope sign + R² magnitude AND
- Price > LR_line midpoint
- ADX(14) corroboration
- HTF LR slope alignment

**실패 케이스 / 함정**:
- Linear assumption: crypto는 exponential growth → log-price 사용 권장
- Lookback dependent: n 변경 시 slope/R² 크게 변동
- High R² + tiny slope = trend 강하지만 의미 없음 (entry 가치 X)
- Outlier 1개에 slope 왜곡 (BTC liquidation candle)
- R² 단독 사용 시 direction 모호 — slope sign 항상 병행

**출처**:
- [QuantifiedStrategies — LR Slope Backtest](https://www.quantifiedstrategies.com/linear-regression-slope/)
- [LuxAlgo — Linear Regression Indicator Guide](https://www.luxalgo.com/blog/linear-regression-a-statistical-indicator-guide/)
- [TradingPedia — R-Squared Method](https://www.tradingpedia.com/forex-trading-indicators/r-squared-method/)
- [TrendSpider — LR Slope Guide](https://trendspider.com/learning-center/linear-regression-slope-a-comprehensive-guide-for-traders/)

---

## 15. DEMA / TEMA

### Double / Triple Exponential Moving Average
**개요**: Patrick Mulloy(1994, "Technical Analysis of Stocks & Commodities") 개발. Single EMA의 lag 문제를 multiple EMA composition으로 상쇄. 수식:
- `EMA1 = EMA(close, n)`
- `EMA2 = EMA(EMA1, n)`
- `EMA3 = EMA(EMA2, n)`
- `DEMA = 2*EMA1 - EMA2`
- `TEMA = 3*EMA1 - 3*EMA2 + EMA3`

**시그널 정의**:
- Entry (Long): `close > DEMA` AND `DEMA slope > 0`
- DEMA cross: `DEMA(9) > DEMA(21)` long bias
- TEMA cross variant: `TEMA(20) > TEMA(50)` (faster than EMA cross)
- Entry (Short): symmetric inverse
- Exit / SL:
  - Cross opposite
  - Slope flip
  - SL: ATR(14) * 2

**파라미터**:
- DEMA default: 14, 21
- TEMA default: 14, 21
- Common pairs: 9/21, 20/50, 50/200
- Crypto: TEMA(20) on 1H for swing, DEMA(50) for trend filter

**결합 필터**:
- ADX > 25
- Volume on cross
- HTF alignment
- TEMA crossovers는 EMA보다 빠르므로 false signal 더 많음 → trend gate 필수

**실패 케이스 / 함정**:
- Reduced lag = whipsaw 증가 — noise market에서 EMA보다 더 false
- TEMA는 DEMA보다 더 빠르고 더 noisy (trade-off)
- Sharp reversal 시 DEMA/TEMA가 너무 빨리 cross → mean-reversion 후 재cross
- 초기 n bars 동안 unstable (3중 EMA seeding 문제)
- Backtest에서 단순 SMA crossover보다 turnover 높음 → fee 부담↑

**출처**:
- [Wikipedia — Double EMA](https://en.wikipedia.org/wiki/Double_exponential_moving_average)
- [Wikipedia — Triple EMA](https://en.wikipedia.org/wiki/Triple_exponential_moving_average)
- [StockCharts ChartSchool — DEMA](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/double-exponential-moving-average-dema)
- [StockCharts ChartSchool — TEMA](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/triple-exponential-moving-average-tema)

---

## 16. Keltner Channel Trend Riding

### Keltner Channel (ATR-based Channel)
**개요**: Chester Keltner(1960), Linda Bradford Raschke 변형(1980s). Bollinger Bands와 유사하지만 std 대신 ATR 사용 → volatility scaling 다름. 수식:
- `Mid = EMA(close, 20)`
- `Upper = Mid + multiplier * ATR(10)`
- `Lower = Mid - multiplier * ATR(10)`

가정: 강한 trend는 가격이 upper band를 "탐(ride)" — band touch가 reversal이 아니라 continuation signal.

**시그널 정의**:
- Trend Long ride: 3+ closes above Keltner Upper → 강한 uptrend
- Pullback Long entry: 직전 1-3 bars 동안 Upper band touched, 가격이 Mid EMA로 pullback, bullish candle close → re-enter long
- Continuation: keltner mid를 break하지 않으면 trend intact
- Exit / SL:
  - Close back to lower band
  - Keltner Mid 하향 break (long의 경우)
  - Hard SL: lower Keltner band - 0.5 ATR
  - Partial TP: opposite band 70% close (LiteFinance 권장)

**파라미터**:
- Default: EMA(20) ± 2 * ATR(10)
- Conservative: EMA(20) ± 2.5 * ATR(14)
- Aggressive: EMA(20) ± 1.5 * ATR(10)
- Linda Raschke 변형: SMA(20) + ATR(20) * 2

**결합 필터**:
- ADX(14) > 25 (sideway 시 strategy 적용 금지 — Keltner 핵심 전제)
- HTF EMA(200) trend
- Volume on band break
- Channel slope: Mid EMA가 명확히 상향(하향)일 것

**실패 케이스 / 함정**:
- Sideway market: 가격이 Upper-Lower 사이를 진동 → 모든 entry false
- Single-bar wick break: 한 봉이 band 뚫고 즉시 복귀 → trap
- Crypto wick: 5% 이상 wick으로 band touched 후 즉시 mean-revert (좋은 SL이 필수)
- Multiplier 너무 작으면 false breakout 빈번
- ATR(10) on 1H crypto는 sub-1% — multiplier 2면 매우 좁아서 자주 touched

**출처**:
- [LiteFinance — Keltner Channel Strategy](https://www.litefinance.org/blog/for-beginners/best-technical-indicators/keltner-channel/)
- [StockCharts ChartSchool — Keltner Channels](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/keltner-channels)
- [QuantifiedStrategies — Keltner Bands](https://www.quantifiedstrategies.com/keltner-bands-trading-strategies/)
- [Trading With Rayner — Keltner Complete Guide](https://www.tradingwithrayner.com/keltner-channel-indicator/)

---

## 17. Higher-Highs / Higher-Lows Structure

### Market Structure (Dow Theory)
**개요**: Charles Dow(1851-1902). Trend의 가장 fundamental한 정의: uptrend = 연속된 HH(higher high) + HL(higher low), downtrend = LH + LL. 수식적으로는 swing point detection algorithm 필요 (e.g. ZigZag, fractal pattern).

**시그널 정의**:
- Swing detection: bar `t`가 swing high if `high[t] > high[t-k..t-1]` AND `high[t] > high[t+1..t+k]` (k=3 or 5 typical)
- Trend Long bias: 직전 2 swing highs HH AND 직전 2 swing lows HL
- Trend break (BoS, Break of Structure): 가격이 직전 swing low 하향 break while in uptrend → trend possibly ending
- Entry (continuation Long): trend bullish + price pulls to recent HL + bullish reversal at HL → enter long
- Entry (BoS reversal): trend bullish but BoS 발생 후 retest of broken level rejected → enter short
- Exit / SL:
  - Stop below most recent HL (long)
  - Trail SL up to each new HL
  - Exit on BoS (HL break) → trend invalidated

**파라미터**:
- Swing detection k: 3 (responsive), 5 (standard), 10 (major swings only)
- ZigZag deviation %: 3% (BTC daily), 5% (altcoin daily), 1% (intraday)
- Fractal pattern: 5-bar Bill Williams fractal

**결합 필터**:
- Volume confirmation: HH formed on increasing volume = healthy
- Multi-timeframe: HTF structure bullish AND LTF entry within HL pullback
- HTF swing high / low가 LTF swing low / high와 동시 위치 시 강한 confluence

**실패 케이스 / 함정**:
- Swing detection은 inherent lookahead — 마지막 swing은 confirm까지 lag
- Crypto wick: false swing이 wick 1개로 형성 → close-only swing 권장
- Subjective: 다른 k, dev% 결과 다름 → 알고리즘 명시 필수
- Equal Highs (EQH) / Equal Lows (EQL): 정확히 같은 가격이면 HH/HL 정의 애매 → epsilon tolerance (0.1%) 사용
- Liquidity grab: HH 직후 stop hunt for stops just above 직전 high

**출처**:
- [Incredible Charts — Dow Theory Trends](https://www.incrediblecharts.com/technical/dow_theory_trends.php)
- [Fidelity — Basic Concepts of Trend](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/basic-concepts-trend)
- [FX Foundations — Market Structure HH HL LH LL](https://fxfoundations.com/learn/technical-analysis/market-structure)
- [Oxford Strat — Dow Theory Trend Strategy](https://oxfordstrat.com/trading-strategies/dow-theory-trend/)

---

## 18. Ehlers Fisher Transform

### Fisher Transform (간략)
**개요**: John F. Ehlers("Cybernetic Analysis for Stocks and Futures", 2004). 가격 분포가 normal이 아닌데 많은 indicator는 정규성 가정 → Fisher transform으로 가격(또는 normalized price)을 Gaussian normal로 mapping. 수식:
- `value[t] = 0.66 * ((price - lowest_low) / (highest_high - lowest_low) - 0.5) * 2 + 0.67 * value[t-1]` (normalize to ±1, smoothed)
- `Fisher = 0.5 * ln((1 + value) / (1 - value)) + 0.5 * Fisher[t-1]`
- `Trigger = Fisher[t-1]`

가정: Fisher transform이 가격 분포를 정규화 → extreme이 명확해지고 turning point가 statistically 유의미.

**시그널 정의**:
- Reversal Long: `Fisher crosses above Trigger` (i.e. above Fisher[t-1]) AND Fisher < 0 (oversold)
- Reversal Short: `Fisher crosses below Trigger` AND Fisher > 0
- Extreme: Fisher > +1.5 = overbought, < -1.5 = oversold (potential reversal)
- Trend mode (less common): Fisher > 0 prolonged = trend bullish
- Exit / SL:
  - Opposite cross
  - Extreme reached: take profit at +/-2
  - SL: ATR-based

**파라미터**:
- Default period: 9 (Ehlers original)
- Smoother: 13, 21
- 매우 noisy: 5 (intraday)

**결합 필터**:
- Trend filter: 200 EMA — Fisher reversal entry는 HTF trend 방향과 일치할 때만
- Volume on cross
- Confluence with support/resistance

**실패 케이스 / 함정**:
- Fisher는 본질적으로 oscillator — 강한 trend에서 extreme 영역에 stuck
- 단독 사용 시 reversal trader trap (counter-trend false signals 많음)
- Implementation의 normalization range 차이: HH/LL lookback이 다르면 결과 다름
- Crypto pump bar: Fisher가 즉시 +2 도달 후 더 상승 → "overbought" 신호 무력
- Lag from smoothing constants — seed 후 8-10 bars 동안 unstable

**출처**:
- [TradingView — Fisher Transform](https://www.tradingview.com/scripts/fishertransform/)
- [LuxAlgo — Fisher Transform Clarity](https://www.luxalgo.com/blog/fisher-transform-clarity-for-turning-points/)
- [GoCharting — Ehlers Fisher Transform](https://gocharting.com/docs/charting/technical-indicator/momentum/eshlers-fisher-transform-indicaotor)
- [TradingPedia — Ehlers Fisher Transform](https://www.tradingpedia.com/forex-trading-indicators/ehlers-fisher-transform/)

---

## 19. Cross-Cutting Notes

### Trend-Following Universals (모든 기법 공통)

#### A. Risk & Position Sizing
- **Risk per trade**: 0.5% ~ 1% of account equity (Turtle: 1 N = 0.5%)
- **ATR-based sizing**: `position_size = (account_equity * risk%) / (entry - stop)`
- **Volatility scaling**: high ATR → smaller position (Andreas Clenow style)
- **Max correlated exposure**: BTC 추세 trade 동시에 5+ alt long은 BTC bet 중복 → 합산 한도 (e.g. total long ≤ 4% account)
- **Pyramiding**: Turtle 규칙 — 1 N 유리하게 움직일 때마다 추가 unit, max 4 units

#### B. Combining Filters (Strategy Generator 권장 stack)
1. **HTF trend filter** (200 EMA daily, 또는 weekly Ichimoku)
2. **Trend strength gate** (ADX > 25, R² > 0.7, KAMA ER > 0.3)
3. **Entry trigger** (cross, breakout, structure)
4. **Volume confirmation** (current bar > 1.5 * 20-bar avg)
5. **Time/session filter** (avoid Asian thin liquidity, funding flip times)

#### C. Exit Hierarchy
1. **Hard SL** (catastrophic protection, 1-2 ATR or % loss)
2. **Trailing stop** (Supertrend, Chandelier, PSAR, prior HL)
3. **Reverse signal** (always-in systems)
4. **Time stop** (no profit after N bars → exit)
5. **Trend invalidation** (BoS, R² collapse, ADX < 20)

#### D. Crypto-Specific Adjustments
- **24/7 markets**: timeframe 정의 시 UTC 00:00 daily reset 표준
- **Funding rates**: perpetual swap funding flip 시점 (Binance 8H 간격) false signal 빈번
- **Weekend low liquidity**: Sat-Sun signals 신뢰도 낮음 → discount or skip
- **News-driven gaps**: regulatory news, hack, exchange outage → indicator meaningless 1-2 bars
- **Stop hunt**: round number, prior swing high/low cluster의 stops sweep → SL을 round number 직접 위/아래에 두지 말 것 (extra ATR buffer)
- **Spread + slippage**: backtest에서 0.05% (BTC) ~ 0.2% (alt) 가정
- **Mark price vs last price**: liquidation 계산은 mark price, 신호 계산은 last price → 충돌 가능

#### E. Backtest Pitfalls
- **Lookahead bias**: HA close, swing detection, AVWAP anchor selection
- **Survivorship**: delisted altcoins universe 누락
- **Overfitting parameters**: 30+ indicator parameters를 in-sample optimize → out-of-sample 붕괴
- **Sample size**: BTC 14년 history에서 daily 50/200 cross signal은 ~30회 뿐 — variance 크고 통계적 유의 부족
- **Regime dependency**: trend-following은 trending regime(2017, 2020-2021)에서만 강함, 2018-2019 또는 2022 chop 시기 max DD 50%+
- **Correlated trades**: 다중 alt long simultaneous = single BTC bet, sample size inflate

#### F. Strategy Generator Output Schema (suggestion)
```yaml
strategy:
  name: "supertrend_ema_bull"
  timeframe: "4h"
  symbol: "BTC/USDT"
  entry:
    long:
      conditions:
        - "supertrend(10, 3) green flip"
        - "close > ema(200)"
        - "adx(14) > 25"
        - "volume > sma(volume, 20) * 1.2"
      action: "buy"
  exit:
    long:
      stop_loss: "supertrend line"
      take_profit: null
      reverse_signal: "supertrend red flip"
  sizing:
    risk_pct: 0.005
    sizing_method: "atr"
    atr_period: 14
    atr_multiplier: 2
```

#### G. References (시스템적 trend-following 권장 도서)
- J. Welles Wilder Jr., *New Concepts in Technical Trading Systems* (1978) — RSI, ADX, PSAR, ATR 원전
- Andreas Clenow, *Following the Trend* (2013) — diversified managed futures
- Andreas Clenow, *Stocks on the Move* (2015) — momentum ranking
- Robert Carver, *Systematic Trading* (2015) — system design framework
- Perry Kaufman, *Smarter Trading* (1995) — KAMA introduction
- John Ehlers, *Cybernetic Analysis for Stocks and Futures* (2004) — Fisher Transform
- Goichi Hosoda, *Ichimoku Kinko Hyo* (1968) — 일본 원전

#### H. Aggregator-friendly Indicator Ranking (실시간 사용 시)
Trend-following 신호 quality 순서 (주관적, crypto daily 기준):
1. **HTF trend filter** (Ichimoku weekly, 200 EMA daily) — bias only
2. **ADX + DI** — strength + direction
3. **Supertrend** — entry timing + trailing stop combined
4. **EMA stack** — visual trend confirmation
5. **Donchian breakout (55)** — major trend entry
6. **MACD histogram slope** — early momentum
7. **Anchored VWAP** — institutional cost basis
8. **HH/HL structure** — fundamental trend
9. **KAMA / HMA** — adaptive smoothing
10. **Heikin-Ashi** — visual filter
11. **Parabolic SAR** — trailing stop only
12. **Fisher Transform** — counter-trend reversal (trend-following에는 부차적)

#### I. Failure Mode Summary (모든 trend-following 공통)
- **Whipsaw / chop**: 모든 trend-following의 가장 큰 적 — ADX/ER/R² gate 필수
- **Lag**: trend 따라잡으나 turning point 못 잡음 — leading filter (RSI div, Fisher) 보조
- **Regime shift**: bull→bear 전환 직후 큰 손실 — HTF trend filter로 mitigate
- **Crowded trade**: 모든 사람이 보는 setup (50/200 SMA, BTC ATH) → stop hunt
- **Fee/slippage drag**: 빈번한 cross 신호 → turnover 높아 net return 감소
- **Tail risk**: 24/7 crypto + leverage = single black-swan event에 전체 capital wipe (FTX, Luna 등 학습)

---

*Document version: 1.0 — generated for crypto-master strategy generator reference. All citations verified at time of writing (2026-04-28).*
