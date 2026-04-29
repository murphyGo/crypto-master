# 02. Classic Chart Patterns (Technical Analysis) — Crypto Reference

> 자동 전략 생성기를 위한 reference document.
> 패턴 인식 규칙, signal 정의, 실패 케이스를 명확히 기술. 모든 통계는 출처 표기.
> 크립토 적용 시 24/7 시장 / 낮은 유동성 / Bitcoin dominance 영향을 항상 고려.

---

## 0. 공통 전제 (Universal Conventions)

- **Timeframe**: 1H 이상 권장. 4H / 1D 가 fakeout이 가장 적음. 15m 이하는 noise 비율이 ≥ 40%.
- **Trendline 정의**: 최소 2개 swing point를 잇되, 패턴 confirmation 위해 **3개 이상 touch** 권장 (Bulkowski).
- **Breakout confirmation 기본 규칙**:
  - Close-based: 종가가 trendline 너머로 마감
  - Volume: breakout candle volume ≥ 직전 20-bar SMA volume × 1.5
  - Re-test: breakout 이후 최대 3-bar 내 trendline retest 시 entry 신뢰도 +
- **Crypto 특이 사항**:
  - BTC dominance > 50% 일 때 alt 패턴 신뢰도 10–15% 하락 (Coincub, altFINS).
  - 시총 top 50 외 종목은 fakeout rate 60–70%.
  - 주요 라운드 가격대 (BTC: 50k, 60k, 100k 등) 근처에서는 패턴 distortion 빈번.
- **포지션 사이징**: SL 거리 기준 risk-per-trade = account equity × 0.5–1.0%.

---

## 1. Triangles (삼각수렴)

### 1.1 Ascending Triangle (상승 삼각형)
**개요**: 수평 저항선과 상승 추세선이 수렴하는 bullish continuation 패턴. 매수세가 점진적으로 가격을 끌어올리되 저항대에서 매도세가 반복적으로 출현, 결국 매수가 이긴다는 심리. 상승 추세 중 출현 시 가장 reliable.

**형성 조건**:
- 상단: 수평선에 최소 **2 touches** (이상적으로 3 touches), 각 high 차이 ≤ 0.5%
- 하단: 상승 추세선에 최소 **2 higher lows** (이상적으로 3+)
- 폭/높이 비율: 패턴 길이는 최소 4 weeks (일봉 기준) 또는 동등한 캔들 수 (4H 24bars+)
- Volume profile: 수렴하면서 volume 감소, breakout 시 spike

**시그널 정의**:
- **Long Entry**: 수평 저항 close-break + 다음 bar 종가 > 저항선 → 진입.
  - 안전 entry: breakout 후 retest 이전 저항(이제 지지)에서 bullish reaction candle.
- **SL**: 직전 higher low 또는 패턴 high의 50% retracement 중 가까운 쪽.
- **TP**: 패턴 height (수평선 - 첫 번째 higher low) 를 breakout 지점에 가산.
- **Failure**: 종가가 상승 추세선 아래로 이탈 시 (busted ascending triangle, 평균 -13%).

**유효 비율**: Bull market upward breakout 성공률 ~70%, break-even failure 17%; 전체 39 패턴 중 **rank 16** (Bulkowski). 1,400+ 거래 기준.

**결합 필터**:
- HTF 추세 정렬: 1D 가 상승 추세일 때 4H ascending triangle 우위.
- Volume 확인: breakout candle volume × 1.5 이상.
- RSI: breakout 시 RSI > 50 (모멘텀 확인).

**실패 케이스 / 함정**:
- 수평선 fake break (1–2 bar wick만, 종가 미확인) → 진입 금지.
- 패턴이 너무 클 때 (full height > 가격의 30%) breakout 후 mean-reversion 확률 증가.
- Touch가 부족(좌우 합 3 이하)하면 신뢰도 급락.

**출처**:
- [Bulkowski on Ascending Triangles](https://thepatternsite.com/at.html)
- [Bulkowski on Busted Ascending Triangles](https://thepatternsite.com/BustAscTriangles.html)
- [Investopedia: Ascending Triangle](https://www.investopedia.com/terms/a/ascendingtriangle.asp)
- [BabyPips: Triangles](https://www.babypips.com/learn/forex/triangles)

---

### 1.2 Descending Triangle (하락 삼각형)
**개요**: 수평 지지선과 하락 추세선의 수렴. Bearish continuation. 매수세가 점진적으로 약해지고 결국 지지선 붕괴.

**형성 조건**:
- 하단: 수평선에 최소 2 touches, low 차이 ≤ 0.5%
- 상단: 하락 추세선에 lower highs 2+
- Volume: 수렴하며 감소, breakdown 시 surge
- 최소 길이: 일봉 4주 / 4H 24+ bars

**시그널 정의**:
- **Short Entry**: 수평 지지선 close-break + retest 후 lower high 형성 시 short.
- **SL**: 직전 lower high 또는 패턴 low의 50% retracement 위쪽.
- **TP**: 패턴 height를 break 지점에서 차감.
- **Failure**: 종가가 하락 추세선 위로 이탈 (busted, 평균 +36% rise — 강력한 reversal signal).

**유효 비율**: 하방 breakout 성공률 ~64%, 2023 study에서 reversal 예측 68% (continuation context).

**결합 필터**:
- HTF 하락 추세 정렬 필수.
- MACD bearish cross + RSI < 50.
- Funding rate (perp): 양수 + 패턴 = short squeeze 위험, 음수 + 패턴 = 더 신뢰.

**실패 케이스**:
- Bull 시장 내 출현 시 fakeout 빈번 (busted rate ↑).
- 지지선 wick 이탈 후 reclaim → busted, long으로 전환 가능.

**출처**:
- [Bulkowski on Descending Triangles](https://thepatternsite.com/dt.html)
- [Liquidity Provider: Triangle Patterns](https://liquidity-provider.com/articles/triangle-patterns-in-trading-ascending-descending-symmetrical-guide/)
- [StockCharts ChartSchool: Descending Triangle](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/descending-triangle-continuation)

---

### 1.3 Symmetrical Triangle (대칭 삼각수렴)
**개요**: lower high 와 higher low 가 한 점에 수렴. 방향 중립 — 추세 지속 또는 반전 가능. Bulkowski 통계상 continuation 54%, reversal 46%.

**형성 조건**:
- 상단: 하락 추세선에 lower highs 2+
- 하단: 상승 추세선에 higher lows 2+
- 두 trendline의 기울기 절댓값 유사 (대칭).
- Apex(수렴점) 에 도달하기 전 패턴 길이의 50–75% 지점에서 breakout 일어나야 신뢰.
- Volume 감소.

**시그널 정의**:
- **Entry**: 어느 한쪽 trendline close-break.
  - Long: 상단 break + retest.
  - Short: 하단 break + retest.
- **SL**: 반대편 trendline 너머.
- **TP**: 패턴 가장 두꺼운 부분(left edge)의 height를 breakout point에 투영.
- **Pre-breakout**: 진입 금지 (apex 매우 가까운 곳 = noise).

**유효 비율**: Upside breakout 발생률 56% (225/401 cases), measured move 도달 약 60% (Bulkowski). 전체 perf rank ~30 — 신뢰도 낮음.

**결합 필터**:
- 방향성 신호로 HTF 추세를 활용.
- Volume spike 필수 (없으면 false break 가능성 ≥ 50%).
- Apex 까지 75% 진행 후 breakout 은 신뢰도 급락.

**실패 케이스**:
- Apex 너무 가까운 곳에서 breakout → 즉시 reversal 빈번.
- 양쪽 trendline 모두 빠르게 break (whipsaw) → 무거래.

**출처**:
- [Bulkowski on Symmetrical Triangles](https://thepatternsite.com/st.html)
- [Investopedia: Symmetrical Triangle](https://www.investopedia.com/terms/s/symmetricaltriangle.asp)
- [TradingView Education: Triangles](https://www.tradingview.com/education/triangles/)

---

## 2. Wedges (쐐기)

### 2.1 Rising Wedge (상승 쐐기)
**개요**: 상승 추세선 두 개가 모두 위쪽으로 기울되 하단 추세선의 기울기가 더 가파른 수렴 패턴. Bearish reversal (uptrend 정점) 또는 bearish continuation (downtrend 중간 반등) 시그널. Bulkowski 통계상 가장 신뢰도 낮은 패턴 중 하나.

**형성 조건**:
- 두 trendline 모두 상승 기울기, 양쪽 모두 최소 **2 touches** (좋은 신뢰도는 좌우 각 2+, 총 4 touches).
- 하단(상승 추세선) 기울기 > 상단 기울기.
- Volume: 패턴 진행 중 감소 (특히 high 갱신 시 약화).
- 최소 길이: 일봉 3주 이상.

**시그널 정의**:
- **Short Entry**: 하단 추세선 close-break + retest 시 short.
- **SL**: 직전 wedge 내부 high 위쪽.
- **TP**: 패턴 시작점(개시 가격)까지 — 보수적; 또는 wedge 가장 두꺼운 부분 height를 break point 에서 차감.
- **Failure**: 종가가 wedge 상단 추세선 위로 이탈 → busted (uptrend 재개).

**유효 비율**:
- 하방 breakout: 성공률 49% (failure rate 51%) — Bulkowski 36개 bearish 패턴 중 **rank 36 (worst)**.
- 평균 9% 하락 (downside breakout, bull market).
- 상방 breakout: 통계적으로 81% 성공률 (덜 흔함, 그러나 발생 시 신뢰도 ↑).

**결합 필터**:
- HTF divergence (RSI bearish divergence) 동반 시 신뢰도 급증.
- Bitcoin dominance 상승 + alt rising wedge = strong short setup.
- Funding rate 과도 양수 (≥ 0.05% / 8h) = squeeze 가능성.

**실패 케이스**:
- 단순 minor pullback 을 wedge로 오인 (touch 부족).
- 강한 bull trend 중에는 squeeze로 wedge 위로 explosively breakout.
- Low-volume 환경에서 wedge breakout 자체가 noise.

**출처**:
- [Bulkowski on Rising Wedges](https://thepatternsite.com/risewedge.html)
- [Liberated Stock Trader: Rising Wedge](https://www.liberatedstocktrader.com/rising-wedge-pattern/)
- [Investopedia: Rising Wedge](https://www.investopedia.com/terms/r/risingwedge.asp)

---

### 2.2 Falling Wedge (하락 쐐기)
**개요**: 두 trendline 모두 하향 기울기이며 상단 trendline의 기울기가 더 가파름. Bullish reversal/continuation. Rising wedge보다 통계적으로 훨씬 신뢰도 높음.

**형성 조건**:
- 두 추세선 모두 하향, 상단 기울기 > 하단 기울기.
- 좌우 각 2+ touches (총 4+).
- Volume: 패턴 진행 중 감소, breakout 시 surge.
- 최소 길이: 일봉 3주 이상.

**시그널 정의**:
- **Long Entry**: 상단 추세선 close-break + retest 시 long.
- **SL**: wedge 내부 직전 low 아래.
- **TP**: wedge 시작점 또는 가장 두꺼운 부분의 height를 break 지점 가산.

**유효 비율**: 성공률 ~74% (failure rate 26%), bull market에서 우수.

**결합 필터**:
- RSI bullish divergence (가격 lower low, RSI higher low) — 매우 강력.
- Volume contraction + breakout volume spike.
- HTF 지지대(이전 swing low, 200 EMA)와 일치 시 우위.

**실패 케이스**:
- Strong downtrend 중에는 단순 bear flag로 오인 가능.
- Volume이 breakout 시 미확인 → fakeout.

**출처**:
- [Bulkowski on Falling Wedges](https://thepatternsite.com/fallwedge.html)
- [Investopedia: Falling Wedge](https://www.investopedia.com/terms/f/fallingwedge.asp)
- [BabyPips: Wedges](https://www.babypips.com/learn/forex/wedges)

---

## 3. Channels (채널)

### 3.1 Ascending Channel (상승 채널)
**개요**: 평행한 상단/하단 추세선 사이에서 가격이 상승. Bullish continuation. 채널 내 mean-reversion 또는 breakout 양방 트레이딩 가능.

**형성 조건**:
- 상단 trendline: lower 추세선과 평행, 각각 2+ touches.
- 채널 폭(height): 일관성 (편차 ≤ 10%).
- 추세선 기울기 동일 (parallel).

**시그널 정의 — Mean-reversion**:
- **Long**: 하단 추세선 터치 + bullish reversal candle (hammer, engulfing) → 진입.
- **Short**: 상단 추세선 터치 + bearish rejection.
- **SL**: 채널 너비의 1/3 ~ 1/2 만큼 trendline 너머.
- **TP**: 반대편 trendline.

**시그널 정의 — Breakout**:
- 상단 close-break + volume spike → momentum long. TP = 채널 height × 1.0~1.5 가산.
- 하단 close-break = 추세 reversal 가능성, short 또는 청산.

**유효 비율**: Channel breakout (방향 무관) 성공률 65–70% (volume 동반 시), reversal 무 confirmation 시 fakeout ~40%.

**결합 필터**:
- Touch count ≥ 4 (양쪽 합) 권장.
- HTF 추세와 동일 방향일 때 mean-reversion long 우위.
- Stochastic / RSI extreme (overbought/oversold) 와 결합.

**실패 케이스**:
- 가짜 채널 (cherry-picked trendline, touch 1회) — 통계적으로 무의미.
- 강한 trending breakout 후 mean-reversion 시도 = 큰 손실 위험.

**출처**:
- [BabyPips: Trend Channels](https://www.babypips.com/learn/forex/trend-channels)
- [TradingView: Parallel Channel](https://www.tradingview.com/scripts/parallelchannel/)
- [Investopedia: Ascending Channel](https://www.investopedia.com/terms/a/ascendingchannel.asp)
- [FXOpen: Ascending Channel](https://fxopen.com/blog/en/how-to-trade-an-ascending-channel-pattern/)

---

### 3.2 Descending Channel (하락 채널)
**개요**: 평행 추세선이 하향 기울기. Bearish continuation. 동일 룰을 mirrored 로 적용.

**형성 조건**: ascending과 동일하되 방향 반대.

**시그널 정의**:
- **Short (mean-reversion)**: 상단 trendline rejection.
- **Long (mean-reversion)**: 하단 trendline reaction (역추세, 작은 size).
- **Breakout long**: 상단 close-break + volume.

**유효 비율**: Bearish channel breakout 상방 성공률 ~62% (downtrend reversal context).

**결합 필터/실패**: ascending channel 과 mirror.

**출처**: 위 ascending channel 출처 동일.

---

### 3.3 Horizontal Channel (수평 채널 / Range)
**개요**: 평행 수평선 사이의 횡보. 추세 부재, 명확한 supply/demand zone.

**형성 조건**:
- 상단/하단 모두 수평 (기울기 0).
- 각 boundary에 ≥ 2 touches (rejection 캔들 동반).
- Range 폭이 일관성 있음.

**시그널 정의**:
- **Range trade**: 하단에서 long, 상단에서 short. SL = boundary 너머 ATR × 1, TP = 반대 boundary.
- **Breakout**: close + 1.5x volume → 방향 추종. TP = range 폭을 break point에 투영.

**유효 비율**: Bulkowski Rectangle Top/Bottom 통계 (4. Rectangle 섹션 참고).

**결합 필터**: ADX < 20 (추세 약함) 일 때 range trade 신뢰; ADX > 25 = breakout 모드.

**실패 케이스**: Squeeze 후 가짜 breakout 빈번 (특히 amateur volume).

**출처**: 위 Channel 출처와 Rectangle 섹션 출처 참조.

---

## 4. Head and Shoulders (헤드 앤 숄더)

### 4.1 Head and Shoulders Top (정배열 H&S)
**개요**: 좌측 어깨, 머리, 우측 어깨 + 두 어깨를 잇는 neckline. Uptrend 정점에서 출현하는 가장 신뢰도 높은 reversal 패턴 중 하나.

**형성 조건**:
- 사전 uptrend 필수.
- 어깨 높이 차 ≤ 머리 높이의 20%.
- Neckline 기울기 약간 (일직선/약간 하향이 이상적).
- Volume profile:
  - 좌측 어깨: 정상 / 높은 volume.
  - 머리: volume 약간 감소.
  - 우측 어깨: volume 가장 낮음 (모멘텀 약화).

**시그널 정의**:
- **Short Entry (1st)**: neckline close-break (종가 기준 하락 마감).
- **Short Entry (2nd, conservative)**: break 후 neckline retest, bearish rejection.
- **SL**: 우측 어깨 high 위쪽 (또는 two-candle rule: 2 bar 뒤 high — Daily Price Action 권장).
- **TP**: head top → neckline 거리를 breakdown 지점에서 차감 (measured move).
- **Failure**: 종가가 neckline 위로 reclaim → 패턴 무효.

**유효 비율**:
- Neckline break 후 성공률 ~81% (chartscout / Bulkowski variant).
- Average decline 16% (bull market).
- Throwback rate 68% — retest entry가 통계적으로 풍부.
- Full measured move 도달률 ~51% — partial TP 권장.

**결합 필터**:
- Bearish RSI divergence (head 에서 RSI 가 left shoulder 보다 낮음).
- HTF 저항대와 head top 일치.
- Daily / 4H 권장 (15m 이하는 noise).

**실패 케이스**:
- Neckline wick break only → 진입 보류.
- Volume이 우측 어깨에서 오히려 증가 → 모멘텀 미약화, fakeout 위험.
- Strong macro bull 환경 (BTC halving 직후 등) 에서는 reclaim 빈번.

**출처**:
- [Bulkowski on Head-and-Shoulders Tops](https://thepatternsite.com/hst.html)
- [BabyPips: Head and Shoulders](https://www.babypips.com/learn/forex/head-and-shoulders)
- [DailyPriceAction: H&S Guide](https://dailypriceaction.com/blog/head-and-shoulders-pattern/)
- [Altrady: H&S in Crypto](https://www.altrady.com/crypto-trading/technical-analysis/head-and-shoulders-chart-patterns)

---

### 4.2 Inverse Head and Shoulders (역배열 H&S, IH&S)
**개요**: H&S 의 mirror. Downtrend 바닥에서 나오는 강력한 bullish reversal. 좌측 어깨 / 머리 (lowest low) / 우측 어깨.

**형성 조건**: H&S top mirror.
- 사전 downtrend 필수.
- Volume이 우측 어깨에서 증가 (반전 모멘텀).
- Neckline 약간 상향 기울기 허용.

**시그널 정의**:
- **Long Entry**: neckline close-break, retest 시 conservative entry.
- **SL**: 우측 어깨 low 아래.
- **TP**: head bottom → neckline 거리 신축 가산.

**유효 비율**: 성공률 ~83%, average rise ~38% (Bulkowski IH&S).

**결합 필터**:
- Bullish RSI divergence (head 에서 RSI > left shoulder).
- 200 EMA reclaim과 동시 발생 시 매우 강력.

**실패 케이스**: 매크로 bear cycle 중 IH&S 는 종종 fakeout (예: bear market rally).

**출처**:
- [Bulkowski on Head-and-Shoulders Bottoms](https://thepatternsite.com/hsb.html)
- [altFINS: Inverse H&S Crypto](https://altfins.com/knowledge-base/how-to-trade-inverse-head-and-shoulders-pattern-crypto-chart-pattern/)

---

## 5. Double Top / Double Bottom

### 5.1 Double Top (이중 천장, M-pattern)
**개요**: 두 개의 비슷한 high가 형성되며 그 사이 swing low(neckline 역할). Uptrend 끝의 reversal 신호.

**형성 조건**:
- 사전 uptrend.
- 두 high 차이 ≤ 3% (이상적 ≤ 1%).
- 두 peak 사이 시간 간격: 최소 2주 (일봉) — 너무 가까우면 단순 noise.
- 두 peak 사이 swing low (= neckline) 가 최소 10% pullback.
- Volume: 두 번째 peak에서 첫 번째 보다 낮음.

**시그널 정의**:
- **Short Entry**: neckline (mid swing low) close-break + retest.
- **SL**: 두 번째 peak 위쪽.
- **TP**: peak — neckline 거리를 breakdown 지점에서 차감.
- **Failure**: 종가가 두 번째 peak 위로 break → busted, 강한 long signal.

**유효 비율**:
- Bulkowski: 성공률 ~65% (혹은 unconfirmed 시 short 손실률 63%).
- Confirmation 없이 진입 시 win rate 매우 낮음 → **반드시 neckline break 대기**.

**결합 필터**: Bearish divergence (RSI/MACD), HTF 저항 일치.

**실패 케이스**:
- 두 peak 사이 swing low가 ≤ 5% (noise) → 패턴 무효.
- Crypto pump 후 단순 cooldown 을 double top 으로 오인.

**출처**:
- [Bulkowski on Double Tops](https://thepatternsite.com/doubletop.html)
- [Bulkowski on Busted Double Tops](https://thepatternsite.com/BustDoubleTops.html)
- [Investopedia: Double Top](https://www.investopedia.com/terms/d/doubletop.asp)

---

### 5.2 Double Bottom (이중 바닥, W-pattern)
**개요**: Mirror of double top. Downtrend 바닥의 reversal. 통계적으로 double top 보다 신뢰도 우위.

**형성 조건**: double top mirror.
- 두 low 차이 ≤ 3%.
- 두 low 사이 swing high (neckline) 최소 10%.
- Volume: 두 번째 low가 첫 번째 보다 낮은 volume → 매도 압력 약화.

**시그널 정의**:
- **Long Entry**: neckline close-break.
- **SL**: 두 번째 low 아래.
- **TP**: neckline — bottom 거리 가산.

**유효 비율**:
- Bulkowski: 성공률 ~78%, bull market 에서 88%; failure rate ~16%; average rise 37%.
- Eve&Eve variant 가장 안정.

**결합 필터**: Bullish RSI divergence, 주요 지지대 (Fib 0.618 of prior leg) 일치.

**실패 케이스**:
- Bear market 내 발생 시 종종 lower low로 이어짐 (busted bottom).
- 두 low 사이 시간 간격 너무 짧음 (< 1주).

**출처**:
- [Bulkowski on Double Bottoms](https://thepatternsite.com/db.html)
- [Bulkowski on Double Bottom Types](https://www.thepatternsite.com/DoubleBottomTypes.html)
- [Liberated Stock Trader: Double Bottom](https://www.liberatedstocktrader.com/double-bottom-pattern/)

---

### 5.3 Triple Top / Triple Bottom
**개요**: 3개의 유사 peak/low. Double 패턴의 강화 버전이지만 발생 빈도 낮음. 같은 boundary 에서 3번 거부 → 매우 견고한 supply/demand zone 의 증거.

**형성 조건**:
- 3개 peak/low 차이 ≤ 3% (이상적 ≤ 1%).
- 각 peak 사이 swing pullback 최소 10%.
- 패턴 길이: 일봉 4주 이상.
- Volume: 매 peak/low 마다 점차 감소.

**시그널 정의**:
- **Triple Top Short**: 가장 최근 swing low (neckline) close-break.
- **Triple Bottom Long**: 가장 최근 swing high close-break.
- **SL/TP**: double top/bottom 과 동일 규칙.

**유효 비율**:
- Triple top: 보고된 신뢰도 87–88% (몇몇 자료); backtest 기반 win rate 41% — **출처별 편차 큼, conservative 사용 권장**.
- Triple bottom: 신뢰도 ~74–87%, throwback rate 65% (Bulkowski).

**결합 필터**: Daily/Weekly 에서만 신뢰. Bearish/bullish divergence 강력 confirmation.

**실패 케이스**: 3rd touch 가 1st/2nd 보다 너무 멀어지면 단순 sideways consolidation 일 가능성.

**출처**:
- [Bulkowski on Triple Tops](https://thepatternsite.com/tt.html)
- [Bulkowski on Triple Bottoms](https://thepatternsite.com/tb.html)
- [ThinkMarkets: Triple Top](https://www.thinkmarkets.com/en/trading-academy/technical-analysis/triple-top-pattern/)
- [LiteFinance: Triple Bottom](https://www.litefinance.org/blog/for-professionals/100-most-efficient-forex-chart-patterns/triple-bottom-pattern/)

---

## 6. Cup and Handle / Inverse Cup and Handle

### 6.1 Cup and Handle (컵 앤 핸들, Bullish)
**개요**: U자형 cup + 우측 짧은 pullback (handle) → upside breakout. 장기 accumulation 후 매수세 재집결의 시그널. William O'Neil 의 CANSLIM 핵심 패턴.

**형성 조건**:
- Cup 깊이: 직전 상승의 38.2% – 61.8% retracement 가 이상적 (Bulkowski).
- Cup 모양: 둥글고 대칭적; V자형은 신뢰도 낮음.
- Cup 길이: 최소 7 weeks (일봉) — crypto 에선 4H 기준 100+ bars.
- Handle: cup 우측 high 의 10–15% 미만 pullback, 1–4주 길이.
- Handle 내부 trendline 약간 하향 기울기.
- Volume: cup 형성 중 감소, handle 에서 추가 감소, breakout 시 spike.

**시그널 정의**:
- **Long Entry**: handle resistance (= cup right rim) close-break + volume.
- **SL**: handle 내부 low 아래.
- **TP**: cup depth 를 breakout point 에 가산.
- **Aggressive variant**: handle 내부 retest 후 bullish candle 에서 진입.

**유효 비율**:
- Bulkowski: 성공률 65–70%, average rise 24%; bull market 에서는 일부 자료 95% / +54%.
- Measured move 도달 ~50%.

**결합 필터**:
- 사전 uptrend (최소 30% 상승) 후 형성될 때 우위.
- Volume contraction in handle 필수.
- HTF 저항 돌파 동시 발생 시 매우 강력.

**실패 케이스**:
- Handle pullback이 cup의 50% 이상 → invalid (단순 double top 가능성).
- V-cup (sharp recovery) 은 fakeout 비율 ↑.
- Crypto pump-and-dump 에서 cup 모양 흉내 (volume profile 미충족) 다수.

**출처**:
- [Bulkowski on Cup with Handle](https://thepatternsite.com/cup.html)
- [Investopedia: Cup and Handle](https://www.investopedia.com/terms/c/cupandhandle.asp)
- [LuxAlgo: Cup and Handle Success Rates](https://www.luxalgo.com/blog/cup-and-handle-pattern-success-rates-explained/)

---

### 6.2 Inverse Cup and Handle (Bearish)
**개요**: Mirror — 거꾸로 된 U + 작은 상승 handle → downside breakout. Distribution top 의 시그널.

**형성 조건**: cup-and-handle mirror. Volume 은 inverted cup 형성 중 감소, handle 에서 증가 가능, breakdown 시 spike.

**시그널 정의**:
- **Short Entry**: handle support close-break.
- **SL**: handle high 위.
- **TP**: inverted cup depth 차감.

**유효 비율**: Cup-and-handle 보다 통계 부족; 일반적으로 신뢰도 약간 낮음 (~60%).

**결합 필터**: 사전 downtrend, bearish divergence.

**실패 케이스**: Crypto bear → bull 전환 구간에서 빈번한 fakeout.

**출처**:
- [Bulkowski on Inverted Cup and Handle](https://thepatternsite.com/cuph.html)
- [Investopedia: Inverse Cup Handle](https://www.investopedia.com/terms/i/inverted-cup-and-handle.asp)

---

## 7. Flags and Pennants

### 7.1 Bull Flag (강세 플래그)
**개요**: 강한 상승 (flagpole) 후 짧은 평행 채널 형태의 약세 pullback. Bullish continuation. 전체 차트 패턴 중 가장 흔하고 가장 빠른 trade.

**형성 조건**:
- Flagpole: 최소 20% (일봉) 또는 동등한 강도의 short timeframe move (tight, 5–15 candles).
- Flag 본체: 평행한 두 trendline, 약한 하향 기울기 또는 수평.
- Flag 길이: flagpole 의 1/3 이하 (시간/가격 모두).
- Flag 내부 retracement: flagpole의 38.2–50% 미만 (50% 초과 시 단순 pullback).
- Volume: flagpole 에서 spike, flag 에서 감소, breakout 에서 surge.

**시그널 정의**:
- **Long Entry**: flag upper trendline close-break + volume × 1.5.
- **SL**: flag lower trendline 아래 또는 flag low 아래.
- **TP**: flagpole length 를 breakout 지점에 가산 (1:1 measured move).

**유효 비율**: ~70% in bull market; flag continuation 패턴 중 상위.

**결합 필터**:
- HTF 추세 정렬.
- Volume contraction in flag 필수.
- Funding rate (perp) 정상 (squeeze 위험 낮음) 일 때 우위.

**실패 케이스**:
- Flag 내부 retracement > 50% → flagpole 무효.
- Flag 길이가 flagpole 길이를 초과 → pattern decay.

**출처**:
- [StockCharts: Flag Pennant](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/flag-pennant)
- [Warrior Trading: Bull Flag](https://www.warriortrading.com/bull-flag-trading/)
- [TrendSpider: Flag Patterns](https://trendspider.com/learning-center/chart-patterns-flags/)

---

### 7.2 Bear Flag (약세 플래그)
**개요**: 강한 하락 (bear flagpole) 후 약한 상승 pullback. Bearish continuation.

**형성 조건**: bull flag mirror. Flag 내부 약한 상승 기울기.

**시그널 정의**:
- **Short Entry**: flag lower trendline close-break.
- **SL**: flag high 위.
- **TP**: flagpole length 차감.

**유효 비율**: ~67%, bear market 에서 우수.

**결합 필터**: Funding rate 양수 + bear flag = squeeze risk; 음수 / neutral 시 신뢰도 ↑.

**실패 케이스**: Crypto 빠른 reversal, especially after capitulation candle.

**출처**: 위 flag 출처 동일 + [Changelly: Bear Flag](https://changelly.com/blog/bear-flag-pattern/)

---

### 7.3 Pennant (페넌트)
**개요**: Flagpole 후 작은 symmetrical triangle (수렴). Flag 와 유사하나 평행 대신 수렴.

**형성 조건**:
- Flagpole 동일.
- Pennant: 두 trendline 수렴, 매우 짧음 (1–3주 이하).
- Volume contraction.

**시그널 정의**:
- **Bullish Long**: pennant 상단 trendline close-break.
- **Bearish Short**: pennant 하단 trendline close-break.
- **TP**: flagpole length 측정 적용.

**유효 비율**: Bullish pennant ~65%, bearish ~62%. Symmetrical triangle 통계와 유사하나 사전 강한 추세 덕에 우위.

**결합 필터**: Pennant duration 짧을수록 (≤ 2주) 신뢰도 ↑.

**실패 케이스**: pennant 너무 길면 (> flagpole 길이의 50%) symmetrical triangle 로 변질.

**출처**:
- [Centerpoint: Bullish Pennant](https://centerpointsecurities.com/bullish-pennant-patterns/)
- [Britannica Money: Flag Pennant](https://www.britannica.com/money/flag-pennant-technical-analysis)

---

## 8. Rectangles / Boxes

**개요**: 수평 지지/저항 사이의 횡보 (= horizontal channel). Continuation 또는 reversal 모두 가능. Darvas Box 와 동일 개념.

**형성 조건**:
- 상단/하단 수평선 (기울기 ≤ 0.1%).
- 각 boundary 최소 2 touches (이상적으로 3+).
- 패턴 길이: 일봉 3주 이상.
- Volume: 횡보 동안 감소.

**시그널 정의**:
- **Long Breakout**: 상단 close-break + volume → long. SL = box low. TP = box height 가산.
- **Short Breakdown**: 하단 close-break.
- **Range Trade (no breakout)**: 하단 매수, 상단 매도. Tight SL (ATR × 1).

**유효 비율 (Bulkowski)**:
- Rectangle Top (uptrend 중 형성): 상방 breakout 성공률 85% bull market, +51% rise.
- Rectangle Bottom (downtrend 중): 하방 breakout 성공률 76%, -16% decline.
- 전체 70–90% range, 패턴 중 상위.

**결합 필터**:
- ADX < 20 동안 range trade, ADX 상승 시 breakout 모드 전환.
- Volume on breakout candle ≥ 1.5x avg.
- Bollinger Band squeeze 와 결합 시 강력.

**실패 케이스**:
- Wick break only (종가 미확인) → fakeout 빈도 ↑ in crypto.
- Multiple consecutive false breakouts → range 가 wider 가 되거나 triangle 로 변형.

**출처**:
- [Bulkowski on Rectangle Tops](https://thepatternsite.com/recttops.html)
- [Bulkowski on Rectangle Bottoms](https://thepatternsite.com/rectbots.html)
- [Investopedia: Rectangle](https://www.investopedia.com/terms/r/rectangle.asp)
- [Liberated Stock Trader: Rectangle](https://www.liberatedstocktrader.com/rectangle-chart-pattern/)

---

## 9. Rounding Top / Bottom (Saucer)

### 9.1 Rounding Bottom (Saucer Bottom)
**개요**: 점진적이고 부드러운 U자형 바닥. 매도세가 천천히 소진되고 매수세가 점진적으로 누적되는 accumulation 패턴.

**형성 조건**:
- 길이: 평균 8.5개월 (Bulkowski) — crypto 에선 일봉 / 주봉만 신뢰. 4H 이하는 noise.
- Lower lows → flat → higher lows 의 부드러운 progression.
- Sharp wick 없음 (clean U).
- Volume: 하락 구간 감소, 바닥에서 최저, 회복 구간에서 증가 (volume bowl).

**시그널 정의**:
- **Long Entry**: saucer rim (= 좌측 시작가) 수평선 close-break + volume.
- **SL**: 바닥 부근 swing low 아래.
- **TP**: depth 를 breakout 지점에 가산.

**유효 비율**: 정확도 63–65%, average return 10–15%, R/R ratio 1.2–1.6 (Bulkowski).

**결합 필터**: Weekly 200 EMA 위에서 형성 시 매우 강력. Bullish RSI 추세 (점진적 상승).

**실패 케이스**:
- Sharp V-bottom 을 saucer로 오인 — pattern 정의 미충족.
- Crypto bear cycle 중에는 saucer 가 더 큰 downtrend 의 일부일 수 있음.

**출처**:
- [Bulkowski on Rounding Bottoms](https://thepatternsite.com/roundb.html)
- [StockCharts ChartSchool: Rounding Bottom](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/rounding-bottom)
- [ChartGuys: Rounding Bottom](https://www.chartguys.com/chart-patterns/rounding-bottom-saucer)

---

### 9.2 Rounding Top
**개요**: 거꾸로 된 saucer. Distribution. 통계 빈도 낮음, 신뢰도 mid-tier.

**형성 조건**: rounding bottom mirror. Volume bowl 거꾸로.

**시그널 정의**:
- **Short Entry**: rim (좌측 시작가) close-break.
- **SL**: 패턴 high 위.
- **TP**: depth 차감.

**유효 비율**: ~60%, average decline 약 12%.

**실패 케이스**: 시간 길어 trader patience 요구; 장기 horizon 에 적합.

**출처**:
- [Bulkowski on Rounding Tops](https://thepatternsite.com/roundtop.html)

---

## 10. Diamond Pattern (다이아몬드)

**개요**: Broadening 페이즈 (HH + LL) 이후 contracting 페이즈 (LH + HL) — 즉 megaphone + symmetrical triangle 의 합체. Reversal 시그널이 강한 편 (특히 diamond top).

**형성 조건**:
- 명확한 4개 주요 swing point (broadening 단계 2, contracting 단계 2).
- 사전 추세 (top 은 uptrend, bottom 은 downtrend) 필수.
- Trendline 4개 (좌측 상/하, 우측 상/하).
- 출현 빈도 낮음 — 발견 시 확인 needed.

**시그널 정의**:
- **Diamond Top Short**: 우측 하단 trendline close-break.
- **Diamond Bottom Long**: 우측 상단 trendline close-break.
- **SL**: 패턴 내부 마지막 swing 너머.
- **TP**: 패턴 가장 두꺼운 부분의 height 를 breakout 지점에 가/감산.

**유효 비율**:
- Diamond Bottom: upside breakout 73–74%, average rise 35–39%.
- Diamond Top: downside breakout 54%, average decline 17%.

**결합 필터**: Volume 은 contracting 단계에서 감소, breakout 에서 surge 필수.

**실패 케이스**:
- 진짜 diamond 는 매우 드물다. 대부분의 "diamond" 는 broadening 또는 triangle 로 분류 가능.
- 패턴이 명확하지 않으면 사용 금지.

**출처**:
- [Bulkowski on Diamond Tops](https://thepatternsite.com/diamondt.html)
- [Bulkowski on Diamond Bottoms](https://www.thepatternsite.com/diamondb.html)
- [FXOpen: Diamond Pattern](https://fxopen.com/blog/en/how-to-trade-the-diamond-chart-pattern/)
- [LiteFinance: Diamond Pattern](https://www.litefinance.org/blog/for-professionals/100-most-efficient-forex-chart-patterns/diamond-pattern-trading/)

---

## 11. Broadening (Megaphone) Pattern

**개요**: 두 trendline 이 점점 발산 (HH + LL). 변동성 확대 = 시장 불안정. 통계적으로 약한 패턴 — Bulkowski mid-list/poor.

**형성 조건**:
- 상단 trendline 상승 기울기, 하단 trendline 하락 기울기.
- 각 trendline 최소 2 touches (총 4 swing points 이상).
- 사전 추세에 따라 broadening top (uptrend 후) 또는 broadening bottom (downtrend 후) 으로 분류.

**시그널 정의** (Bulkowski 권장):
- **Pre-breakout partial rise/decline trade**: 가격이 trendline 까지 도달하지 못하고 반대로 reversal 시 진입. (까다로움 — beginner 비추천.)
- **Breakout trade**: 한쪽 trendline close-break + retest.
- **Busted trade (best)**: breakout 후 빠르게 reversal 시 반대 방향 진입.

**유효 비율**:
- Broadening Top: break-even failure rate above average, average move below average — **rank 25/39**.
- Broadening Bottom: 비슷한 mid-list 성능.

**Bulkowski 권장 필터**:
- 빠르게 형성된 broadening top 회피.
- 비정상적으로 큰 패턴 회피.
- Overhead resistance 가 가까울 때 회피.
- **Busted breakout** 가 가장 수익성 높음.

**실패 케이스**:
- 변동성 큰 crypto 에서 broadening 처럼 보이지만 단순 random walk 인 경우 다수.
- Touch가 부족하면 (3 이하) 패턴 무효.

**출처**:
- [Bulkowski on Broadening Tops](https://thepatternsite.com/bt.html)
- [Bulkowski on Broadening Bottoms](https://thepatternsite.com/broadb.html)
- [TopStep: Megaphone Patterns](https://www.topstep.com/blog/trading-megaphone-patterns/)

---

## 12. Harmonic Patterns (간략)

> Harmonic patterns 은 Fibonacci 비율로 정의되는 5점 (X-A-B-C-D) 구조. PRZ (Potential Reversal Zone) = D 점에서 reversal 진입.

### 12.1 ABCD
**개요**: 가장 단순한 harmonic. 두 impulse(A→B, C→D) + 하나의 retracement(B→C).

**형성 조건**:
- BC = AB의 0.618 또는 0.786 retracement.
- CD = AB 길이와 동일 (대칭) 또는 1.272/1.618 extension.
- AB 와 CD 의 시간 길이 유사.

**시그널 정의**:
- **D 점 진입** (reversal 방향).
- **SL**: D 점 너머 ATR × 1.
- **TP1**: AD의 0.382 retracement, **TP2**: 0.618.

**출처**:
- [BabyPips: ABCD and Three-Drive](https://www.babypips.com/learn/forex/the-abcd-and-the-three-drive)
- [TradingView: ABCD](https://www.tradingview.com/chart/BTCUSD/Q7SmkxM8-Harmonic-patterns-Gartley-Bat-Butterfly-Crab-and-Shark/)

---

### 12.2 Three Drives
**개요**: 3개의 impulse + 2개의 corrective leg. Elliott Wave 5파와 유사.

**형성 조건**:
- Drive 1, 2, 3.
- Correction A = Drive 1의 0.618 retracement.
- Drive 2 = Correction A의 1.272 extension.
- Correction B = Drive 2의 0.618 retracement.
- Drive 3 = Correction B의 1.272 extension.
- 시간 / 가격 대칭성 중요.

**시그널 정의**:
- **Drive 3 완성 시점 (1.272 ext) 에서 reversal 진입**.
- **SL**: Drive 3 너머 ATR × 1.5.
- **TP**: Drive 1 시작점까지 (보수적).

**유효 비율**: 통계적 데이터 적음; 패턴 자체가 드물게 출현. 일반적으로 50–60% 신뢰도 추정.

**출처**:
- [BabyPips: ABCD and Three-Drive](https://www.babypips.com/learn/forex/the-abcd-and-the-three-drive)
- [TradingView Education: Three Drives](https://www.tradingview.com/education/threedrivespattern/)
- [LiteFinance: Three Drives](https://www.litefinance.org/blog/for-beginners/harmonic-patterns/three-drives-pattern/)

---

### 12.3 Gartley
**개요**: 5점 (X-A-B-C-D), Bullish/Bearish 양방향. Fibonacci 비율 엄격.

**형성 조건**:
- AB = XA의 0.618 retracement.
- BC = AB의 0.382~0.886 retracement.
- CD = BC의 1.13~1.618 extension.
- D 점 = XA의 0.786 retracement (PRZ).

**시그널 정의**:
- **Long (bullish Gartley)**: D 점에서 long, SL = X 아래.
- **TP**: AD의 0.618, 그리고 1.272.

**유효 비율**: ~70% (well-formed pattern, daily TF).

**출처**:
- [IG: Harmonic Patterns](https://www.ig.com/en/trading-strategies/top-7-harmonic-patterns-every-trader-should-know-210608)
- [Admiral Markets: Harmonic Trading](https://admiralmarkets.com/education/articles/forex-strategy/harmonic-trading-patterns)

---

### 12.4 Bat
**개요**: Gartley의 변형, D 점이 더 깊은 retracement.

**형성 조건**:
- AB = XA의 0.382~0.500 retracement (Gartley 보다 얕음).
- BC = AB의 0.382~0.886 retracement.
- CD = BC의 1.618~2.618 extension.
- D 점 = XA의 0.886 retracement (PRZ — 더 깊음).

**시그널 정의**: Gartley 와 동일 구조, SL 조밀 (high R/R).

**유효 비율**: ~65–70%, 정확한 PRZ 덕분에 R/R 가 좋음.

**출처**: 위 Gartley 출처 동일.

---

### 12.5 Butterfly
**개요**: D 점이 XA를 초과 (extension). Aggressive reversal entry.

**형성 조건**:
- AB = XA의 0.786 retracement.
- BC = AB의 0.382~0.886 retracement.
- CD = BC의 1.618~2.618 extension.
- D 점 = XA의 1.272~1.618 **extension** (X 너머).

**시그널 정의**:
- **D 에서 reversal entry** (overshoot 끝). SL 매우 tight (D 너머 small ATR).
- **TP**: A 점 또는 0.618 of AD.

**유효 비율**: Daily TF 에서 ~65%, 잘못 그리면 사기성 패턴 多.

**출처**:
- [EBC: AB=CD to Butterfly](https://www.ebc.com/forex/trading-harmonic-patterns-from-ab-cd-to-butterfly)
- [NAGA: Harmonic Patterns](https://naga.com/en/academy/harmonic-patterns-gartley-butterfly-bat-crab)

---

## 13. Crypto-Specific Considerations & Universal Caveats

### 13.1 Failure Modes Common Across Patterns
1. **Wick-only break (no close)**: crypto 에서 매우 빈번. 무조건 close-based confirmation.
2. **Low-volume breakout**: volume × 1.5 이하면 fakeout 가능성 ≥ 50%.
3. **Liquidation cascade fakeouts**: perp 시장에서 stop hunting → trendline 잠시 break 후 reversal. 대형 움직임 (BTC ATR × 2 이상) 직전 funding rate 점검.
4. **Asian / weekend low-liquidity**: pattern noise 증가, 신뢰도 -10–20%.
5. **News-driven invalidation**: macro / regulatory event 시 모든 TA 무효 가능.

### 13.2 Confirmation Stack (전략 생성기 적용 가이드)
패턴 진입 신호 강화:
- **Volume**: breakout candle volume ≥ SMA(volume, 20) × 1.5.
- **Higher TF align**: 패턴 TF의 2~4배 큰 TF 추세와 일치.
- **Momentum**: RSI cross 50 (방향 따라), MACD histogram 같은 방향 확장.
- **Structure**: HH/HL (long) or LH/LL (short) 동반.
- **Funding rate**: extremely positive (≥ 0.05%/8h) = long 신중 / squeeze 위험.

### 13.3 Pattern Selection Priority (신뢰도 기준)
**Tier 1 (highest reliability)**:
- Inverse Head & Shoulders (~83%)
- Double Bottom (Eve&Eve, ~78%)
- Rectangle Top breakout (~85% bull)
- Cup and Handle (65–70%)
- Falling Wedge (~74%)

**Tier 2 (mid)**:
- Ascending Triangle (~70%)
- Bull Flag (~70%)
- Diamond Bottom (~73%)
- Head & Shoulders Top (~81% confirmed)
- Triple Bottom (~74%)

**Tier 3 (use with strict filters)**:
- Symmetrical Triangle (~54% directional)
- Pennant
- Rounding Top/Bottom
- Diamond Top (~54%)
- Broadening (mid-list)

**Tier 4 (avoid unless strong filter stack)**:
- Rising Wedge downside (~49%, worst Bulkowski rank)
- Untrended versions of any pattern
- Patterns with < 4 trendline touches

---

## 14. Reference / 출처 정리

### Primary (authoritative, 통계 인용)
- [Bulkowski's Pattern Index (thepatternsite.com)](https://thepatternsite.com/chartpatterns.html) — Encyclopedia of Chart Patterns 통계 기반
- [Bulkowski Top 10 Reversals/Continuations](https://thepatternsite.com/top10.html)
- [Encyclopedia of Chart Patterns (Wiley)](https://www.amazon.com/Encyclopedia-Chart-Patterns-Thomas-Bulkowski/dp/0471668265)

### Educational
- [StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns)
- [BabyPips School](https://www.babypips.com/learn/forex)
- [Investopedia Technical Analysis](https://www.investopedia.com/technical-analysis-4689657)
- [TradingView Education](https://www.tradingview.com/education/)

### Crypto-specific
- [altFINS Knowledge Base](https://altfins.com/knowledge-base/chart-patterns/)
- [Coincub: Crypto Chart Patterns Guide](https://coincub.com/blog/crypto-chart-patterns-guide/)
- [Altrady Technical Analysis](https://www.altrady.com/crypto-trading/technical-analysis/)

### Practical / Backtesting
- [Liberated Stock Trader](https://www.liberatedstocktrader.com/) — Bulkowski-based 검증 자료
- [QuantifiedStrategies](https://www.quantifiedstrategies.com/) — backtest 결과
- [LuxAlgo Blog](https://www.luxalgo.com/blog/) — pattern success-rate analyses

### YouTube (참고)
- Rayner Teo (TradingwithRayner): 패턴 적용 실전 사례
- The Trading Channel: H&S, flag 위주
- TradingView official YouTube: 무료 공식 강좌

---

**문서 끝.** 자동 전략 생성기는 §13.3 Tier 별 신뢰도와 §0 Universal Conventions 의 confirmation stack 을 우선 적용할 것을 권장한다.
