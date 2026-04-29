# 03 — Breakout & Range Trading Strategies (크립토 마켓)

> 본 문서는 자동화된 전략 생성기(quant strategy generator)가 시그널/룰을 코드로 변환하기 위한 레퍼런스이다.
> 모든 시그널은 가능한 한 정량적·결정적(deterministic) 형태로 기술한다.
> 본문은 한국어, 기술 용어는 영어를 병기한다.

---

## 0. 공통 전제 (Global Conventions)

- **타임프레임 표기**: `1m, 5m, 15m, 1h, 4h, 1d`
- **지수 표기**: `Donchian(N) = (highest_high(N), lowest_low(N))`, `ATR(N) = Average True Range over N bars`, `SMA(N), EMA(N)`
- **거래대금/거래량 평균**: `vol_avg(N) = SMA(volume, N)`
- **HTF (Higher Time Frame) 필터**: 보통 entry TF 의 4~6배 (예: 1h entry → 4h/1d HTF)
- **세션 정의 (24/7 크립토)**: UTC 00:00 daily open 기본, 또는 KST 09:00, 또는 NY 13:30 UTC.
- **확인봉 (confirmation candle)**: "close beyond level" — wick이 아닌 종가 기준
- **리스크 기준 단위**: 계좌의 0.5~1.0% per trade (R), stop 거리 = R / position_size
- **수수료/슬리피지 가정**: taker 0.05% + slippage 0.05% = round-trip ≈ 0.2% (백테스트 시 반드시 차감)

---

## 1. Support / Resistance Breakout (수평 레벨 돌파)

### 1.1 Horizontal Level Breakout (수평 지지/저항 돌파)

**개요**:
가장 기본적인 브레이크아웃. 최근 N봉 동안 여러 번 반응(reject)한 수평 가격대를 식별하고, 종가가 그 레벨을 명확히 돌파할 때 추세 추종 진입한다. 크립토에서는 4h/1d 차트의 주요 수평 레벨이 가장 신뢰도가 높다.

**시그널 정의**:
- **레벨 식별**:
  - `pivot_high(k=5)`: 좌우 5봉이 모두 더 낮은 high를 가진 봉의 high
  - 동일 가격대(±0.3% 허용 오차) 에 `pivot_high` 또는 `pivot_low` 가 ≥ 2회 반응 → 유효 레벨
  - 룩백: 4h 차트 기준 100~200봉 내
- **Long Entry**:
  - `close[0] > resistance_level * (1 + 0.001)` (0.1% 버퍼)
  - AND `volume[0] > vol_avg(20) * 1.5` (거래량 1.5배 이상)
  - AND `close[0] > open[0]` (양봉 종가)
- **Short Entry** (대칭):
  - `close[0] < support_level * (1 - 0.001)`
  - AND `volume[0] > vol_avg(20) * 1.5`
- **SL**: 돌파 봉의 반대편 wick (예: long → low of breakout candle * 0.997) 또는 레벨 - 1 ATR(14)
- **TP**:
  - TP1 = 진입 + 1 × (level distance from previous swing low) — measured move
  - TP2 = 진입 + 2R, trailing stop으로 전환 (chandelier exit, 3 × ATR)

**파라미터**:
- pivot lookback `k`: 3 (단기) ~ 10 (스윙)
- 가격 허용 오차 `tol`: 0.2~0.5% (크립토 변동성 반영, BTC < ETH < altcoin 순으로 ↑)
- volume multiplier: 1.5~2.0
- breakout buffer: 0.1~0.3%

**결합 필터**:
- HTF 추세: `close > EMA(200, 1d)` → long-only 모드 (fakeout 빈도 감소)
- ATR(14, 4h) > ATR(14, 4h) SMA(50) → 변동성 확장 국면
- KST 09:00 또는 UTC 13:30~21:00 (NY 세션) 에 발생한 돌파 우선
- BTC dominance 추세 (alt 트레이딩 시): BTC.D 하락 = alt long 우호

**실패 케이스 / 함정**:
- **Low-vol breakout**: vol < vol_avg(20) → 70%+ 페이크아웃 (Reddit r/algotrading 백테스트 컨센서스)
- **Range chop**: ADX(14) < 20 환경 → 양방향 false break 빈발
- **Wick-only break**: 종가가 아닌 wick으로만 뚫는 경우 → 무시
- **3rd-touch break이 아닌 1st-touch break**: 처음 닿은 레벨 돌파는 의미 약함

**출처**:
- https://www.altrady.com/crypto-trading/technical-analysis/breakout-trading-strategies
- https://capital.com/en-int/learn/trading-strategies/breakout-trading
- https://altfins.com/knowledge-base/support-and-resistance-lines/
- https://priceaction.com/price-action-university/strategies/support-resistance-levels/

---

### 1.2 Swing High / Swing Low Breakout

**개요**:
직전 스윙 고점/저점을 종가로 돌파하면 추세 연장으로 간주한다. 다중 타임프레임 구조(market structure)에서 HH(higher high)/LL(lower low)가 형성되는 시점을 포착한다.

**시그널 정의**:
- `swing_high = max(high[1:k+1])` where `k = 10` (1h 기준 약 10시간 전 고점)
- **Long Entry**:
  - `close[0] > swing_high`
  - AND HTF가 uptrend: `close(1d) > EMA(50, 1d)` AND `close(1d) > close(1d)[5]`
  - AND `body_size = abs(close - open) > ATR(14) * 0.5` (실체 큰 봉)
- **SL**: 직전 swing_low 또는 진입가 - 1.5 × ATR(14)
- **TP**: 1.5R, 3R 분할; 또는 다음 HTF 저항까지 trailing

**파라미터**: swing lookback k = 5~20 / ATR multiplier 1.0~2.0

**결합 필터**: market structure (BOS — Break of Structure), volume spike, RSI(14) > 50

**실패 케이스**:
- 분기점에서 swing high 직후 즉시 reverse → "Stop run" / liquidity grab (특히 알트코인)
- HTF 추세와 반대 방향 break → high failure rate

**출처**:
- https://www.altrady.com/blog/swing-trading/support-and-resistance-how-to-use-them-in-swing-trading
- https://changelly.com/blog/support-and-resistance-in-crypto/

---

## 2. Trendline Breakout (추세선 돌파)

**개요**:
2개 이상의 swing high(하락 추세선) 또는 swing low(상승 추세선)를 잇는 직선을 종가가 돌파하면 추세 전환의 초기 시그널. 단, 추세선은 주관적이라 기계화하려면 swing point + linear regression 또는 `pivot-based slope` 로 정의해야 한다.

**시그널 정의**:
- **Trendline 추출 (자동화)**:
  - 최근 N=50봉에서 `pivot_high(k=3)` 두 개 (가장 최근 두 개) 선택 → 두 점을 잇는 직선의 기울기 m, 절편 b
  - 유효성: 추세선과 사이 봉 wick이 ≥ 1회 추가 reject (3-touch rule)
- **Long Entry (descending trendline 돌파)**:
  - `close[0] > (m * t[0] + b) * 1.002`  (0.2% 버퍼)
  - AND `volume[0] > vol_avg(20) * 1.3`
  - AND retest 옵션: 돌파 후 1~5봉 내 추세선 재방문 후 재반등 시 진입 (false break 필터)
- **SL**: 추세선 - 1 × ATR(14), 또는 retest low
- **TP**: 추세선 시작점 high (measured target), 또는 다음 horizontal resistance

**파라미터**:
- pivot k: 3~5
- 최소 3-touch 또는 2-touch (덜 보수적)
- buffer: 0.2~0.5%
- retest window: 1~10봉

**결합 필터**:
- HTF EMA cross: 1d EMA(20) > EMA(50)
- RSI(14) divergence (bullish: 가격 LL, RSI HL → 추세선 break 신뢰도↑)
- "5% rule" — 종가가 추세선을 5% 이상 이탈하면 강한 break (BingX 기준)

**실패 케이스 / 함정**:
- 추세선 기울기가 너무 가파른 경우 (>60도) → 자주 깨짐, 무의미
- 단 2-touch 추세선 → 통계적 유의성 부족
- News-driven spike → 추세선 break 이지만 곧바로 mean revert

**출처**:
- https://capital.com/en-int/learn/trading-strategies/trendline-trading
- https://bingx.com/en/learn/article/understanding-trend-lines-for-cryptocurrency-trading-a-visual-guide-to-smarter-moves
- https://www.bitget.com/wiki/what-are-trend-lines
- https://www.altrady.com/crypto-trading/technical-analysis/breakout-trading-strategies

---

## 3. False Breakout / Fakeout (페이크아웃, 트랩)

**개요**:
가격이 핵심 레벨을 일시 이탈했다가 다시 회복하는 패턴. Bull trap (저항 돌파 후 반락) / Bear trap (지지 이탈 후 반등). Stop hunt 의도의 institutional liquidity grab일 때가 많다. 페이크아웃 자체를 trade 하면 추세 방향과 반대지만 매우 높은 RR 가능.

**시그널 정의**:
- **Fakeout 식별 (Bear trap 예 — long entry)**:
  - 봉 1: `low[1] < support_level` AND `close[1] > support_level` (하방 wick 후 회복)
  - OR 봉 2: `low[1] < support` 후 다음봉 `close[0] > support_level AND close[0] > close[1]`
  - AND 거래량: 이탈 봉 volume > vol_avg(20) * 1.5 (trap 거래량 동반)
- **Long Entry**:
  - 회복 확인 봉 종가 + 0.1% 또는 break 봉의 high
- **SL**: 페이크아웃 wick의 low - 0.3 ATR (반드시 새로운 저점)
- **TP**:
  - TP1 = 직전 swing high (range 상단)
  - TP2 = range 폭 × 1.5 (measured-move target)
- **Bull trap (short entry)** 은 대칭

**파라미터**:
- wick depth 최소: support 대비 ≥ 0.3% 침투
- recovery window: 1~3봉
- volume confirm multiplier: 1.5~2.0

**결합 필터**:
- HTF 추세 방향: bear trap → uptrend HTF 일 때 신뢰도↑ ("trend resumption")
- RSI divergence: 가격 LL + RSI HL → bear trap 가능성 강함
- Order book / liquidation map (CoinGlass): cluster of stops just below support

**실패 케이스 / 함정**:
- "True breakout"인데 한 봉 retest 후 그대로 추세 진행 → fakeout으로 오인 시 손실
- Recovery 봉 자체가 약하면 (small body, upper wick) 진짜 반전 아님
- Range 외부 acceptance: "2-day close beyond range" → 진짜 break (Investopedia)

**출처**:
- https://www.morpher.com/blog/false-breakout-trading-strategies
- https://phemex.com/academy/bull-trap-vs-bear-trap
- https://priceaction.com/price-action-university/strategies/false-break-out/
- https://bookmap.com/blog/breakout-or-fakeout-the-3-point-checklist-for-confirmation
- https://www.luxalgo.com/blog/5-false-breakout-strategies-for-traders/

---

## 4. Range / Box Trading (박스권 매매, "Buy support, sell resistance")

**개요**:
주요 크립토는 시간의 60~70%를 횡보(range-bound)로 보낸다. 박스 상하단 사이 mean reversion으로 진입, 양 극단에서 반전 신호 시 fade. 추세장에서는 절대 사용 금지 (catastrophic loss).

**시그널 정의**:
- **Range 식별**:
  - `range_high = max(high, 50)`, `range_low = min(low, 50)`
  - Range 유효성: `(range_high - range_low) / range_low < 0.10` (BTC 기준 10% 이내), 그리고 `pivot_high` ≥ 2, `pivot_low` ≥ 2 가 좁은 영역에서 발생
  - ADX(14) < 20 (방향성 약함)
- **Long Entry (지지 매수)**:
  - `close[0] <= range_low * 1.005` (지지 +0.5%)
  - AND `RSI(14) < 35`
  - AND bullish reversal candle (hammer / bullish engulfing) on entry TF
- **Short Entry (저항 매도)**:
  - `close[0] >= range_high * 0.995`
  - AND `RSI(14) > 65`
  - AND bearish reversal candle
- **SL**: range 외부 0.5~1 × ATR(14) (예: long → range_low - ATR)
- **TP**:
  - TP1 = midpoint = (range_high + range_low) / 2
  - TP2 = 반대편 경계 - 0.3% 버퍼

**파라미터**:
- range lookback: 30~100봉
- ADX threshold: < 20 (range), > 25 (trend, 비활성)
- RSI 임계: 30/70 (보수) 또는 40/60 (공격)
- 자본 분할: 20~30% per leg, 평균 단가 (DCA) 가능

**결합 필터**:
- Bollinger Band Width 낮음 (BB squeeze 직전 상태와 구분)
- Volume profile: range 중앙에 POC 위치 → mean reversion 강함
- 시간 필터: Asian session (UTC 23:00~07:00) 은 range 빈발, NY session은 range break 빈발 → time-of-day adjustment

**실패 케이스 / 함정**:
- Range break out 시 즉시 stop out → range trade는 항상 stop을 좁게 가져가야 함
- News / funding rate flip → range 무력화
- Pin / news-spike → 단 한 봉으로 SL hit

**출처**:
- https://blockchain77.com/mastering-crypto-range-trading-the-complete-guide-for-2025/
- https://blog.mexc.com/what-is-the-range-trading-strategy-and-how-it-works/
- https://phemex.com/academy/range-trading-strategy-crypto
- https://3commas.io/mean-reversion-trading-bot

---

## 5. Donchian Channel Breakout (Turtle Trading 변형)

### 5.1 Original Turtle System 1 (단기, 20일)

**개요**:
Richard Dennis & William Eckhardt의 1983 Turtle 실험에서 사용된 단기 시스템. 20일 신고가 돌파 시 long, 20일 신저가 이탈 시 short. ATR 기반 포지션 사이징으로 마켓 간 리스크 정규화.

**시그널 정의**:
- `upper(N) = max(high, N)`, `lower(N) = min(low, N)`, where N = 20
- **Long Entry**:
  - `high[0] > upper(20)[1]` (이전 봉 기준 20일 high 돌파, intra-bar 가능)
  - 단 직전 20일 breakout이 winning trade 였다면 skip (whipsaw 방지) — 원본 룰
- **Short Entry**:
  - `low[0] < lower(20)[1]`
- **N (Volatility unit)**: `N = ATR(20)` (Wilder smoothing)
- **Position size**: `units = (0.01 * equity) / N`
- **Pyramiding**: 0.5N 추가 이동시 1 unit 추가, 최대 4 units
- **SL**: 진입가 - 2N (long) / 진입가 + 2N (short)
- **Exit**:
  - System 1 long exit: `low[0] < min(low, 10)[1]` (10일 최저)
  - System 1 short exit: `high[0] > max(high, 10)[1]`

**파라미터**: N = 20 (entry), 10 (exit), ATR period 20, 2N stop

**결합 필터** (크립토용 수정):
- BTC 기준 backtest 결과: System 1 (20-day) 성과 부진, **System 2 (55-day)** 가 더 나음 (Tradesanta, HTX Research)
- Long-only 모드 권장 (short-side는 crypto에서 음의 기댓값)
- HTF EMA(200, 1d) 위에서만 long entry 활성

### 5.2 Turtle System 2 (장기, 55일)

- N = 55 entry / 20 exit
- 모든 break 진입 (skip 룰 없음)
- SL = 2N, profit target 없음 (trend follow)

**크립토 백테스트 결과 (요약)**:
- 2017~2022 BTC: System 2 > buy-and-hold; 2022~2025 trend 약화로 underperform 사례 다수
- Altcoin 적용 시 변동성 노이즈 매우 큼 → N (ATR period) 더 길게 (60~100) 권장

**실패 케이스 / 함정**:
- Choppy market (2018, 2023 전반): 연속 fake-break → 누적 -30% drawdown 가능
- 24/7 시장 → daily bar 정의가 거래소마다 상이 (UTC 00:00 vs exchange-local)
- Slippage: large unit size → stop fill price 악화

**출처**:
- https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf  (원본 Turtle Rules PDF)
- https://www.quantifiedstrategies.com/turtle-trading-strategy/
- https://www.altrady.com/blog/crypto-trading-strategies/turtle-trading-strategy-rules
- https://medium.com/huobi-research/huobi-quant-academy-3-220714ccde9f
- https://medium.com/@jsgastoniriartecabrera/comprehensive-back-testing-and-performance-analysis-of-the-turtle-trading-decision-system-in-76317fb66f52
- https://tradesanta.com/blog/turtle-trading-in-the-crypto-market-a-viable-strategy

---

## 6. Opening Range Breakout (ORB) — 크립토 적응

**개요**:
전통 주식의 "오프닝 30분 high/low 돌파" 전략을 24/7 크립토에 이식. 크립토에는 "단일 open"이 없으므로, **UTC 00:00 daily candle open** 또는 **NY 세션 (UTC 13:30) open**, **KST 09:00**, **CME BTC futures open (UTC 22:00 일~금)** 등을 anchor로 사용한다.

**시그널 정의 (15-min ORB on 1h crypto)**:
- **Anchor open time**: 예) UTC 00:00
- **Opening Range**:
  - `OR_high = max(high, anchor, anchor + 30min)` (첫 30분의 high)
  - `OR_low = min(low, anchor, anchor + 30min)`
- **Long Entry**:
  - 봉 close (5m or 15m) 가 `OR_high` 위에서 마감
  - AND `volume[0] > vol_avg(20) * 1.3`
  - AND OR range > ATR(14, 1h) * 0.5 (너무 좁은 OR은 노이즈)
- **Short Entry**: `close < OR_low` 대칭
- **SL**: 반대편 OR 경계 또는 진입가 - 1 × OR range
- **TP**:
  - TP1 = 진입 + 1 × OR range
  - TP2 = 진입 + 2 × OR range
  - TP3 = 직전 daily high/low

**파라미터**:
- OR window: 5min / 15min / 30min / 60min (선택)
- anchor: UTC 00:00 / 13:30 / KST 09:00
- breakout buffer: 0.1%
- max trades per session: 1 (re-entry 금지)

**결합 필터**:
- VWAP filter: long 시 close > VWAP (anchored to session open)
- ATR expansion: ATR(14) > ATR(14) SMA(20)
- News/funding spike 회피: 30분 이내 funding settle / major news 발표 제외

**실패 케이스 / 함정**:
- 크립토 24/7 → "open"이 약한 anchor (volume spike 미약할 수 있음)
- Asian session OR은 NY session에서 자주 부정됨 → time-zone bias 존재
- Whipsaw: OR_high → OR_low → OR_high 같은 양방향 돌파 (40~60% 성공률)

**출처**:
- https://www.altrady.com/blog/crypto-trading-strategies/orb-trading-strategy
- https://forextester.com/blog/opening-range-breakout-trading-strategies/
- https://tradethatswing.com/opening-range-breakout-strategy-up-400-this-year/
- https://tradersmastermind.com/trading-strategy-opening-range-breakout/
- https://www.tradingview.com/script/wLSGHPUe-ORB-Breakout-Strategy-with-VWAP-and-Volume-Filters/

---

## 7. Bollinger Band Squeeze Breakout (TTM Squeeze 포함)

### 7.1 Bollinger Band Squeeze (단순)

**개요**:
변동성 수축(BB width 감소) 후 변동성 확장은 강한 방향성 움직임을 동반한다는 가정. "Quiet → loud" cycle.

**시그널 정의**:
- `BB_upper = SMA(close, 20) + 2 * stdev(close, 20)`
- `BB_lower = SMA(close, 20) - 2 * stdev(close, 20)`
- `BB_width = (BB_upper - BB_lower) / SMA(close, 20)`
- **Squeeze 상태**: `BB_width <= min(BB_width, 120)` (최근 120봉 중 최저 BB width — bottom 6-month percentile)
- **Long Entry (squeeze fire)**:
  - Squeeze 상태에서 `close[0] > BB_upper[1]`
  - AND `volume[0] > vol_avg(20) * 1.5`
- **Short Entry**: `close < BB_lower` 대칭
- **SL**: BB middle (= SMA20) 또는 squeeze 봉의 반대편 wick
- **TP**: 1R / 2R / trailing on BB middle cross

### 7.2 TTM Squeeze (John Carter, BB + Keltner combination)

**개요**:
Bollinger Band 가 Keltner Channel 안으로 완전히 들어가면 "squeeze on" → 둘이 다시 벌어지면 "squeeze fired". Momentum histogram (LinReg of close - midprice over 20 bars) 으로 방향 결정.

**시그널 정의**:
- `BB_upper(20, 2)`, `BB_lower(20, 2)`
- `KC_upper = SMA(close, 20) + 1.5 * ATR(20)`, `KC_lower = SMA(close, 20) - 1.5 * ATR(20)`
- **Squeeze ON**: `BB_upper < KC_upper AND BB_lower > KC_lower` (BB가 KC 내부)
- **Squeeze FIRED (release)**: 위 조건이 깨지는 첫 봉 (`squeeze_on[1] AND NOT squeeze_on[0]`)
- **Momentum**: `mom = LinearRegression(close - (highest(20)+lowest(20))/2 - SMA(close,20)/2, 20)`
  - mom > 0 AND rising → bullish breakout
  - mom < 0 AND falling → bearish breakout
- **Long Entry**:
  - Squeeze fired AND mom > 0 AND mom[0] > mom[1]
  - AND `close[0] > BB_upper[1]` (확정 돌파)
- **Exit**:
  - momentum이 정점 후 감소(mom[0] < mom[1]) → 부분 청산
  - 또는 BB middle 터치
- **SL**: KC_lower (long) / KC_upper (short)

**파라미터**:
- BB: 20, 2 stdev
- KC: 20, 1.5 ATR
- Momentum lookback: 12 또는 20
- Min squeeze duration: ≥ 6 bars (너무 짧은 squeeze는 신호 무효)

**결합 필터**:
- HTF 추세: 1d EMA50 방향과 일치하는 fired만 진입
- Volume expansion: fired 봉 volume > vol_avg(20) * 1.5
- ADX(14) > 20 in 5~10 bars after fire (추세 확정)

**실패 케이스 / 함정**:
- "Two-sided squeeze fire": 양방향으로 한번씩 fire → first fire 가짜
- 짧은 squeeze 후 fire → 실제 변동성 확장 아님
- Choppy crypto altcoin: squeeze 자체가 의미 약할 수 있음 (variance가 항상 큼)

**출처**:
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/ttm-squeeze
- https://trendspider.com/learning-center/introduction-to-ttm-squeeze/
- https://trendspider.com/learning-center/bb-kc-squeeze-a-powerful-indicator-for-trading-range-breakouts/
- https://deepvue.com/indicators/ttm-squeeze-indicator-for-breakout-trades/
- https://www.tradingsetupsreview.com/bollinger-squeeze/
- https://medium.com/mudrex/bollinger-band-and-keltner-channel-trading-strategy-4772f47f06d7

---

## 8. Keltner Channel Breakout (단독)

**개요**:
Keltner Channel은 EMA를 중심으로 ATR 배수의 envelope. Bollinger 대비 변동성이 ATR 기반이라 더 부드럽고, trend trade에 적합.

**시그널 정의**:
- `KC_mid = EMA(close, 20)`
- `KC_upper = KC_mid + 2 * ATR(10)`
- `KC_lower = KC_mid - 2 * ATR(10)`
- **Long Entry**:
  - `close[0] > KC_upper[1]`
  - AND `close[0] > EMA(50)` (HTF trend)
  - AND volume confirmation 1.3×
- **Short Entry**: 대칭
- **SL**: KC_mid (= EMA20) 또는 진입가 - 1.5 × ATR(10)
- **TP**: trailing on EMA20 cross, 또는 2~3R fixed

**파라미터**:
- EMA period: 20 (entry TF), 50 (filter)
- ATR period: 10 또는 14
- ATR multiplier: 1.5 (tight) ~ 2.5 (wide)

**결합 필터**:
- Volume profile POC 위에서 long 만
- ADX(14) > 25 (trending market)

**실패 케이스 / 함정**:
- Range market에서 KC band 양쪽 turn over → mean reversion이 우세
- Crypto flash crash → ATR이 점차 확장돼 false signal 생성

**출처**:
- https://volatilitybox.com/research/keltner-channels-vs-bollinger-bands/
- https://medium.com/mudrex/bollinger-band-and-keltner-channel-trading-strategy-4772f47f06d7
- https://www.netpicks.com/squeeze-out-the-chop/

---

## 9. Volatility Breakout (Larry Williams style)

**개요**:
Larry Williams 의 고전 전략. 전일 range × K 만큼 당일 시가에서 가격이 움직이면 추세 신호로 간주, 진입. 한국 코인 트레이더 사이에서 "변동성 돌파 전략" (changdolpa) 으로 매우 유명. 단순하고 일봉 기반이라 자동화 쉬움.

**시그널 정의**:
- `R = high[1] - low[1]` (전일 range)
- `K = 0.5 ~ 0.7` (일반 0.5; LW 원본 0.6)
- `target_long = open[0] + R * K`
- `target_short = open[0] - R * K`
- **Long Entry**:
  - intra-day price breaches `target_long` → market or stop-buy at `target_long`
- **Short Entry**: 대칭 (price breaches `target_short`)
- **Exit**: 다음 일봉 시가에 청산 (close-to-open 사이클) — 원본 룰
- **SL**:
  - 옵션 A (LW): 진입가와 전일 low 의 중간 = `(target_long + low[1]) / 2`
  - 옵션 B (단순): 진입가 - 0.5 × R
- **TP**: 일봉 close 또는 진입 후 ATR(14) × 2

**파라미터**:
- K: 0.3 (공격) ~ 0.9 (보수); BTC backtest 0.5~0.6 권장
- 청산 시점: daily close / next open (변형)
- 거래 가능 시간: 일봉 기준 → 시작 시간 정의 필요 (UTC 00:00 권장)

**결합 필터**:
- HTF MA filter: `close > MA(20, 1d)` 일 때만 long
- Volume filter: 어제 volume > volume MA(20)
- 한국 커뮤니티 변형: "노이즈 비율" K 자동 조정 — 최근 20일 (high-close)/(high-low) 평균
- 분산 적용 (anti-overfit): 여러 코인에 자본 1/N 분할 (BTC, ETH, SOL, …)

**실패 케이스 / 함정**:
- Gap-down open day → target_long hit 후 즉시 reverse (bull trap)
- 변동성 0인 일 (R 매우 작음) → target이 과도하게 낮아 false trigger
- Daily candle anchor 차이 (UTC vs KST) → 결과 크게 변함

**한국 커뮤니티 노트**:
- 김치 김프 변동성: 한국 거래소(업비트)는 USDT 거래소 대비 K 더 크게 (0.6~0.7) 권장
- "코인 사관학교", "아빠는 비트코이너" 채널에서 다중 코인 분산 + K=0.5 + MA filter 변형 백테스트 공유

**출처**:
- https://www.quantifiedstrategies.com/larry-williams-volatility-strategy/
- https://www.mql5.com/en/articles/20745
- https://www.best-trading-platforms.com/trading-platform-futures-forex-cfd-stocks-nanotrader/larry-williams-volatility-break-out-strategy
- https://tradersmastermind.com/volatility-breakout-trading-strategy/
- https://www.whselfinvest.com/en-fr/trading-platform/free-trading-strategies/tradingsystem/56-volatility-break-out-larry-williams-free

---

## 10. Round Number / Psychological Level Breakout

**개요**:
$10k, $50k, $100k 같은 큰 round number 는 옵션 행사가 / 스탑 클러스터 / 인간 인지적 anchor 가 모이는 자석. 돌파 시 stop-cascade, 거부 시 sharp reversal.

**시그널 정의**:
- **Round level 정의**:
  - BTC: 매 $10,000 (예: 50000, 60000, 100000) — major
  - BTC: 매 $5,000 — minor
  - ETH: 매 $500 (1000, 1500, …) — major
  - SOL/altcoin: 매 round percentage point on USDT
- **Approach detection**: `abs(close - round_level) / close < 0.02` (2% 이내 접근)
- **Long Entry (round resistance break)**:
  - `close(4h)[0] > round_level * 1.005` (0.5% 버퍼; round 위 거짓돌파 흔함)
  - AND `volume(4h)[0] > vol_avg(20) * 2.0` (2배 이상 — 더 엄격)
  - AND 24시간 내 retest 시 holds (≥ 1 candle close above) → 진짜 break
- **Short (rejection from round)**:
  - 가격이 round 도달 후 wick 형성 + bearish engulfing → fade short
- **SL**: long → round_level - 1 × ATR(14, 4h); short → round_level + 1 × ATR
- **TP**:
  - 다음 round level 까지 (예: 100k break → 110k target)
  - Options open interest cluster 까지 (Deribit data)

**파라미터**:
- 버퍼: 0.3~0.7% (round 일수록 ↑)
- volume multiplier: 1.5~2.5
- retest 확인 필수 (옵션이지만 권장)

**결합 필터**:
- Open interest (futures): round break 시 OI 증가 → 진짜 break
- Funding rate: 과열(annualized > 30%) → bull trap 위험
- Options gamma exposure (Deribit): 큰 call wall 위 돌파 → 가속 매수 가능

**실패 케이스 / 함정**:
- 첫 시도 돌파는 70%+ 페이크 (Brooks Trading Course 통계)
- Macro news 와 우연 동시 발생 → news fade 후 다시 round 아래로
- round 직전 large limit sell wall (whale) → 종가 break 못함

**출처**:
- https://markets.financialcontent.com/wral/article/breakingcrypto-2025-11-4-bitcoins-six-figure-showdown-the-battle-for-the-100k-psychological-level
- https://www.brookstradingcourse.com/analysis/bitcoin-bear-breakout-of-100000-big-round-number/
- https://www.cryptohopper.com/blog/the-impact-of-psychological-levels-on-crypto-trading-11398
- https://www.babypips.com/learn/forex/psychological-level
- https://forextester.com/blog/psychological-levels-in-trading/

---

## 11. All-Time High (ATH) / All-Time Low Breakout

**개요**:
가격이 사상 최고치를 돌파하면 매도 저항이 사실상 사라진다 ("blue sky breakout"). BTC의 경우 cycle top까지 지속되는 강한 추세가 형성된 역사적 패턴 (2017, 2020-21, 2024-25). 단 ATH 직후 30~80% 조정도 흔하다.

**시그널 정의**:
- `ATH = max(high, all-time)` (전체 데이터)
- **Long Entry (ATH breakout)**:
  - `close(1d) > ATH * 1.02` (2% 버퍼 — ATH 페이크 잦음)
  - AND `volume(1d) > vol_avg(50) * 1.5`
  - AND 1주일 내 retest holds (close above ATH on retest day)
- **Pyramid**: 첫 entry 후 1 ATR 추가 상승마다 0.5 unit 추가, 최대 3 add-on
- **SL**:
  - 초기: ATH * 0.95 (5% 손절)
  - Trailing: chandelier exit = highest_high(22) - 3 × ATR(22)
- **TP**:
  - 고정 TP 사용 안함 (trend follow)
  - exit = trailing stop hit 또는 weekly close < EMA(20, 1w)

**파라미터**:
- 돌파 버퍼: 1~3% (BTC 1~2%, alt 2~5%)
- Trailing chandelier: 22 봉, 3 ATR (Chuck LeBeau 원본)
- Volume confirm: 1.5~2.0×

**ATL (All-Time Low) breakdown** — 대칭이지만 크립토에서는 ATL 도달 자체가 거의 없으므로 주로 alt-coin (장기 하락) 에 적용. Long-only crypto 시스템에서는 사용 안함이 일반적.

**결합 필터**:
- Bitcoin halving cycle phase (post-halving 6~12개월 = ATH break 확률↑)
- BTC dominance: 상승 → BTC ATH 강세, 하락 → alt cycle ATH break
- Macro: DXY 하락, US10Y 하락 → risk-on, ATH break 우호

**실패 케이스 / 함정**:
- "Double top fakeout": 직전 ATH 살짝 돌파 후 큰 폭 하락 (2021년 11월 BTC $69k)
- News-driven spike (예: ETF approval, Trump tweet) → 단기 ATH 돌파 후 mean revert
- Cycle top 시그널 무시: NUPL > 0.75, 펀딩 > +50% 연환산 → ATH break 진입 자제

**출처**:
- https://www.okx.com/en-us/learn/concept-all-time-high-ath
- https://academy.binance.com/en/glossary/all-time-high
- https://www.mexc.com/learn/article/what-is-bitcoin-all-time-high-btc-record-prices-explained/1
- https://cryptopotato.com/bitcoin-price-analysis-path-to-new-ath-opens-up-if-btc-reclaims-this-key-level/

---

## 12. Inside Bar / NR4 / NR7 Breakout (Linda Raschke)

### 12.1 Inside Bar Breakout

**개요**:
Inside Bar = 현재 봉의 high < 직전 봉 high AND 현재 봉 low > 직전 봉 low. 변동성 수축 = mother bar 양쪽 break를 trigger 로. Linda Raschke / Lawrence Connors 의 "Street Smarts" 핵심 셋업.

**시그널 정의**:
- `inside_bar`: `high[0] < high[1] AND low[0] > low[1]`
- **Long Entry**:
  - 다음 봉 (혹은 inside bar 이후 5봉 내) high > `high[1]` (mother bar high) → buy stop
  - AND HTF trend up (`close > EMA50`)
- **Short Entry**: low < `low[1]` 대칭
- **SL**: mother bar 반대편 (long → low[1] - 0.2%)
- **TP**: 1R, 2R 분할; 또는 다음 swing high

### 12.2 NR4 (Narrow Range 4)

- `range(0) = high[0] - low[0]`
- **NR4**: `range(0) < min(range(i) for i in 1..3)` → 직전 4봉 중 가장 좁은 봉
- 다음 봉 high/low 돌파 시 진입

### 12.3 NR7 (Narrow Range 7)

- **NR7**: `range(0) < min(range(i) for i in 1..6)` → 직전 7봉 중 가장 좁음
- 더 강한 압축 신호 → break 후 큰 변동성 확률↑
- Linda Raschke 룰: NR7 다음날에는 추세 방향만 진입 (countertrend 금지)

### 12.4 NR4/IB 조합 (가장 강한 셋업)

- **NR4 AND inside bar**: 두 조건 동시 충족 → 가장 강력한 압축
- 다음 봉 break 시 진입, win rate 60~70% (전통 시장; 크립토는 다소 낮음)

**파라미터**:
- TF: 1d 가 원본; crypto는 4h, 1d 모두 사용 가능
- Stop entry buffer: 0.1~0.2%
- Hold period: 1~5봉 (단기 explosion 셋업)

**결합 필터**:
- ADX 상승 중 (variance expanding)
- Volume 평소보다 낮음 = 압축 확인
- BB width percentile < 20%

**실패 케이스 / 함정**:
- Inside bar break 후 즉시 반대 break ("inside bar fake")
- 2개 연속 NR7 → 좁아지는 wedge로 비추세 확장 가능성
- Crypto 24/7 → 봉 정의에 민감 (일봉 anchor 매우 중요)

**출처**:
- https://forextraininggroup.com/simple-tactics-for-trading-narrow-range-bars-nr4-nr7-nr4id/
- https://www.netpicks.com/nr7-inside-bar/
- https://oxfordstrat.com/trading-strategies/price-breakout-nr7/
- https://blog.elearnmarkets.com/nr4-and-nr7-trading-strategy-setup/
- https://priceaction.com/price-action-university/strategies/fakey/

---

## 13. Volume Profile POC / VAH / VAL Breakout

**개요**:
Volume Profile = 가격대별 누적 거래량 히스토그램. POC (Point of Control) = 최대 거래량 가격, VAH/VAL = 70% volume이 분포한 영역의 상하단. 가격이 high-volume node 사이를 빠르게 통과 (LVN — Low Volume Node 돌파) 하면 trending move 발생.

**시그널 정의 (Daily Volume Profile)**:
- 세션 단위: 일봉 / 주봉 / 30-day rolling
- **POC**: 가장 높은 volume bin 의 중간 가격
- **VAH/VAL**: POC에서 상하로 확장하며 누적 70% volume 영역 경계
- **LVN (Low Volume Node)**: VAH/VAL 외부에서 volume bin이 평균의 < 30%

**Strategy A — VAH Breakout (recoil entry)**:
- `close > previous_VAH AND close > current_VWAP`
- AND volume > vol_avg(20) * 1.5
- → long, target = VAH + (VAH - VAL) (range 폭 만큼 확장)
- SL = VAH - 0.5 × ATR

**Strategy B — VAL Mean Reversion**:
- `close < VAL` 후 `close > VAL` 회복 (reclaim)
- → long, target = POC, SL = recent low

**Strategy C — POC Acceptance/Rejection**:
- 가격이 POC에서 ≥ 3봉 동안 머물면 "accepted" → POC가 새 지지/저항
- 1~2봉 만에 떠나면 "rejected" → fade 진입

**Strategy D — LVN 돌파**:
- LVN 가격대에서 `volume(breakout bar) > avg_volume * 1.5`
- → 다음 HVN(High Volume Node) 까지 빠르게 이동 (fast move zone)

**파라미터**:
- Profile period: 1일, 1주, 30일 (selectable)
- Value area %: 70% (표준)
- Bin size: tickSize × 10 (BTC 약 $10/bin), 또는 0.1% price increment
- LVN threshold: bin volume < 30% of POC bin volume

**결합 필터**:
- HTF trend 방향
- VWAP cross 동시 발생
- Order flow / footprint chart (있다면): aggressive buy at VAH

**실패 케이스 / 함정**:
- 너무 짧은 profile period (단일 봉) → POC 의미 약함
- VPVR vs Session Volume Profile 혼용 시 데이터 불일치
- Crypto 24/7 → "session" 정의에 따라 POC 위치 크게 바뀜
- LVN 통과 직후 mean revert → "fast move zone" 가설 항상 유효 아님

**출처**:
- https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/
- https://www.futureshive.com/blog/volume-profile-trading-strategy-2025
- https://www.quantvps.com/blog/value-area-trading-strategy-guide
- https://blog.opofinance.com/en/volume-profile-strategy/
- https://chartswatcher.com/pages/blog/master-the-volume-profile-indicator-for-better-trading

---

## 14. 종합 결합 매트릭스 (Strategy Combination Matrix)

| Primary Signal | HTF Filter | Volume | Volatility | Time-of-Day |
|---|---|---|---|---|
| Donchian(20) break | EMA200(1d) | vol > 1.5x avg | ATR > ATR-SMA(50) | NY (UTC 13:30~21:00) |
| ORB (UTC 00:00, 30m) | VWAP | vol > 1.3x avg | OR > 0.5xATR | session-start only |
| LW Volatility (K=0.5) | MA(20,1d) | yest. vol > vol-MA(20) | — | next daily close exit |
| TTM Squeeze fired | EMA50 dir | fire bar 1.5x | ADX rising | any |
| ATH break | weekly trend up | 1.5x 50-bar avg | ATR(14,1d) expanding | weekly close only |
| S/R horizontal break | EMA200(1d) | 1.5x 20-bar avg | — | NY/EU session |
| NR7 / NR4-IB | EMA50 dir | low vol on inside | BB width < 20%ile | next-bar break |
| Range fade | ADX < 20 | mid-range vol normal | BB width < 30%ile | Asian session 우선 |
| Volume Profile VAH | VWAP | 1.5x avg | — | RTH equivalent |
| Round number break | OI rising | 2.0x avg | funding < +30%/yr | 24h retest 필수 |

---

## 15. 일반적 함정 (Common Pitfalls Summary)

1. **Low-volume breakouts**: 모든 브레이크아웃 전략의 #1 false signal source. 1.5× 이상 거래량 동반 필수.
2. **Wick-only breaks**: 종가 기준 break를 사용하지 않으면 60%+ 페이크.
3. **Range market 트렌드 셋업 사용**: ADX < 20 / BB width 좁음 환경에서 Donchian/Turtle/breakout 전략은 손실 누적. Regime filter 필수.
4. **Trend market range 셋업 사용**: ADX > 30 환경에서 mean reversion = catastrophic loss.
5. **24/7 anchor 일관성 부재**: ORB, LW, Daily Profile 모두 단일 anchor 일관 사용 필요. UTC 00:00 권장.
6. **Slippage 과소 반영**: 대형 alt에서 1% 이상 slippage 발생; 백테스트에 반드시 round-trip 0.2~0.5% 차감.
7. **Lookahead bias**: pivot, swing, profile 계산 시 미래 봉 참조 금지 — strict `[1:]` indexing.
8. **Overfit to BTC**: BTC 결과를 alt에 그대로 적용하면 실패. 코인별 ATR 기반 파라미터 스케일링 필요.
9. **Funding/news event 무시**: 펀딩 settle (8h cycle), CPI, FOMC 발표 ±15분 전후 진입 회피.
10. **Crypto-specific stop-hunt**: 정확한 round number 또는 직전 swing low/high 에 stop을 두면 자주 hit. 0.3~0.5% 버퍼 추가.

---

## 16. 자동화 시 권장 전략 우선순위 (For Strategy Generator)

높은 자동화 적합성 (deterministic, low ambiguity):
1. **Donchian System 2 (55/20)** — Long-only on BTC/ETH, ATR sizing
2. **Larry Williams Volatility Breakout** (K=0.5, daily)
3. **TTM Squeeze fired** (4h or 1d)
4. **NR7 / NR4-IB** (1d)
5. **ATH breakout** (1d, weekly close confirm)

중간 자동화 적합성 (parameter sensitive):
6. **ORB** (anchor 선택 영향)
7. **Bollinger Squeeze** (단독)
8. **Keltner Channel breakout**

낮은 자동화 적합성 (subjective level identification 필요):
9. **Trendline breakout** (pivot-based 기계화 가능하나 noisy)
10. **Horizontal S/R breakout** (clustering 알고리즘 필요)
11. **Volume Profile POC/VAH/VAL** (profile period selection 영향 큼)
12. **Round number breakout** (level 정의는 쉽지만 confluence 판단 어려움)
13. **False breakout / fakeout fade** (정의 자체가 사후적 — 가장 어려움)
14. **Range mean reversion** (regime detection 부정확 시 치명적)

---

## 17. 백테스트 필수 점검 항목 (Backtest Checklist)

- [ ] Out-of-sample 테스트: in-sample 60% / OOS 40% 분할
- [ ] Walk-forward optimization: 6개월 학습 / 1개월 forward, rolling
- [ ] Slippage / 수수료: 최소 round-trip 0.2%, alt는 0.4~0.5%
- [ ] Lookahead bias 점검: pivot/profile 모든 계산은 `[1:]` 시점 기준
- [ ] Survivorship bias: delisted alt 포함 (특히 2017~2018 ICO 코인)
- [ ] Regime test: 강추세장(2020-21), 약세장(2022), 횡보장(2023) 분할 성과
- [ ] Drawdown limit: max DD < 30% / Calmar > 1.0 / Sharpe > 1.0 (daily) 권장
- [ ] Trade count: 최소 100 trade 이상 (통계적 유의성)
- [ ] Position sizing: ATR-based, 고정 fractional 1% per trade
- [ ] Multi-asset robustness: BTC 외에 ETH, SOL 등 ≥ 3개 자산에서 양의 PnL

---

## 18. 참고 채널 / 커뮤니티 (Reference Communities)

- **유튜브 (영문)**:
  - "Trader Tom" — price action, breakout setups
  - "Jason Pizzino" — crypto cycle / ATH 분석
- **유튜브 (한국어)**:
  - "코인 사관학교" — 변동성 돌파 (Larry Williams 변형) 백테스트
  - "아빠는 비트코이너" — 자동매매 + 변동성 돌파 실거래
- **Reddit**: r/algotrading (백테스트 결과 토론), r/CryptoCurrency (가격/레벨), r/Bitcoin
- **TradingView**: Pine Script 커뮤니티 — TTM Squeeze, Donchian, ORB 인기 indicator 코드
- **학술/리서치**:
  - Curtis Faith, "Way of the Turtle" (2007)
  - Larry Williams, "Long-Term Secrets to Short-Term Trading"
  - Linda Raschke & Larry Connors, "Street Smarts" (1995)
  - HTX Research, Huobi Quant Academy — 크립토 적용 백테스트

---

## 19. 핵심 수식 요약 (Cheatsheet)

```
# Donchian
upper(N) = highest_high(N)
lower(N) = lowest_low(N)
ATR(N)   = SMA(TR, N)   where TR = max(H-L, |H-Cprev|, |L-Cprev|)

# Bollinger
BB_mid   = SMA(close, 20)
BB_upper = BB_mid + 2 * stdev(close, 20)
BB_lower = BB_mid - 2 * stdev(close, 20)
BB_width = (BB_upper - BB_lower) / BB_mid

# Keltner
KC_mid   = EMA(close, 20)
KC_upper = KC_mid + 1.5 * ATR(20)
KC_lower = KC_mid - 1.5 * ATR(20)

# TTM Squeeze
squeeze_on = (BB_upper < KC_upper) AND (BB_lower > KC_lower)

# Larry Williams Vol Breakout
R          = high[1] - low[1]
target_long  = open[0] + R * K   # K = 0.5
target_short = open[0] - R * K

# Opening Range
OR_high = max(high, anchor : anchor + OR_window)
OR_low  = min(low,  anchor : anchor + OR_window)

# Volume Profile
POC = argmax_price(volume_at_price, period)
VA  = price range containing 70% of total volume
VAH = max(VA), VAL = min(VA)

# NR7
NR7 = range(0) < min(range(1..6))

# Inside Bar
IB  = (high[0] < high[1]) AND (low[0] > low[1])
```

---

## 20. 변경 이력 (Document Changelog)

- v1.0 (2026-04-28): 초안 작성. 13개 핵심 기법 + 결합 매트릭스 + 자동화 우선순위 + 백테스트 체크리스트 포함.

---

_End of document._
