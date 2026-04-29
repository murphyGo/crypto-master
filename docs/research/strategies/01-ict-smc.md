# 01. ICT / SMC (Inner Circle Trader / Smart Money Concepts) — 크립토 적용

> 본 문서는 자동 전략 생성기가 ICT/SMC 컨셉을 알고리즘 규칙으로 변환할 수 있도록, 시그널 정의·필터·실패 케이스를 정량적으로 명세한다.
> 모든 시간은 별도 표기 없으면 **NY Time (ET, EDT/EST)** 기준이며 크립토 24/7 환경에 맞춰 UTC도 병기한다.
> 기본 캔들 timeframe 표기: HTF=Daily/4H, MTF=1H/15m, LTF=5m/1m.

---

## 0. 공통 용어 및 약어

- **OB**: Order Block (오더 블록, 마지막 반대 방향 캔들)
- **FVG**: Fair Value Gap (3-캔들 imbalance)
- **IFVG**: Inversion FVG (관통된 후 반대 역할 수행)
- **BOS**: Break of Structure (추세 연속)
- **CHOCH**: Change of Character (추세 전환, 일부 자료에서는 MSS와 혼용)
- **MSS**: Market Structure Shift (CHOCH의 더 강한 형태, displacement 포함)
- **BSL/SSL**: Buy-Side Liquidity / Sell-Side Liquidity
- **EQH/EQL**: Equal Highs / Equal Lows
- **OTE**: Optimal Trade Entry (Fib 0.62~0.79)
- **PD Array**: Premium/Discount Array — OB, FVG, Breaker, Mitigation 등 가격이 반응하는 구조 모음
- **PO3**: Power of Three (Accumulation-Manipulation-Distribution)
- **SMT**: Smart Money Technique divergence (상관 자산 간 발산)
- **CISD**: Change in State of Delivery (배송 상태 변화 — 새로운 방향의 첫 close)
- **HTF Bias**: 상위 timeframe(Daily/4H)의 우위 방향

---

## 1. Order Block (OB) — 오더 블록

### 1.1 Bullish Order Block (강세 OB)
**개요**: Bullish OB는 강한 상승 임펄스 직전의 마지막 음봉(bearish candle)으로, 기관이 매수 포지션을 누적한 흔적으로 간주된다. 가격이 이 영역으로 되돌아오면 잔여 매수 주문이 처리되며 지지로 작동한다는 시장-미시구조 가설에 기반한다.
**시그널 정의**:
  - 식별: 최근 swing low 직전의 마지막 음봉(C1) 식별. 다음 캔들(C2)은 양봉이며 C1의 high를 종가 기준으로 돌파해야 함. C2 이후 N=3개 이상의 캔들이 누적 변위 ≥ 1.5×ATR(14) 이상 상승.
  - OB 영역: C1의 [low, high]. 정밀하게는 C1 body의 [open, low] (ICT 정통식) 또는 [low, 50% midpoint] (보수식).
  - Entry: 가격이 OB 영역으로 retrace 후 OB 내부 50% midpoint 터치 + LTF(1m/5m)에서 bullish CHOCH 또는 displacement 확인 시 long. 보수형은 OB 상단 close 위에서 진입.
  - SL: OB low 아래 0.2×ATR 또는 swing low - 0.1%.
  - TP: 직전 swing high (BSL) → 다음 BSL → HTF FVG. 최소 1:2 RR.
**결합 필터**:
  - HTF Bias: Daily/4H가 bullish (HH-HL 구조 또는 discount 영역 내).
  - OB가 HTF discount(equilibrium 0.5 아래)에 위치할 것.
  - OB와 함께 동일 영역에 FVG가 있으면 신뢰도 +.
  - Killzone 내 형성된 OB 우선 (London/NY AM).
**실패 케이스 / 함정**:
  - **Deep mitigation**: 가격이 OB low 아래로 wick만 찍고 다시 회복 (정통 OB 무효 → Breaker 후보로 전환).
  - 고변동성 뉴스(FOMC, CPI, ETF 결정) 직후엔 OB respect 확률 급락.
  - 약세 추세 내 bullish OB는 retracement 정도로만 작동, target은 1R로 축소 권장.
  - 너무 오래된 OB(> 50 캔들)는 mitigation 끝났을 가능성. fresh OB(<= 20 캔들) 권장.
**출처**:
  - https://innercircletrader.net/tutorials/ict-bullish-order-block/
  - https://atas.net/blog/what-are-ict-order-blocks-and-breaker-blocks-in-trading/
  - https://www.luxalgo.com/blog/ict-trader-concepts-order-blocks-unpacked/
  - https://bingx.com/en/learn/article/what-is-order-block-in-crypto-trading-how-to-trade

### 1.2 Bearish Order Block (약세 OB)
**개요**: Bearish OB는 강한 하락 임펄스 직전의 마지막 양봉으로, 기관 매도 누적 흔적이다. 가격 재방문 시 저항으로 작동한다.
**시그널 정의**:
  - 식별: 최근 swing high 직전의 마지막 양봉(C1). C2는 음봉이며 C1 low를 종가로 break. 누적 변위 ≥ 1.5×ATR(14).
  - OB 영역: C1의 [low, high] 또는 [open, high].
  - Entry: 가격이 OB로 회귀 후 50% midpoint 터치 + LTF bearish CHOCH/displacement 시 short.
  - SL: OB high + 0.2×ATR.
  - TP: 직전 swing low (SSL) → 다음 SSL → HTF FVG.
**결합 필터**:
  - HTF Bias bearish + OB가 premium(equilibrium 0.5 위)에 위치.
  - 인접 FVG/Breaker 동조.
  - London/NY AM killzone 우선.
**실패 케이스 / 함정**:
  - 강한 momentum 추세에서 bearish OB는 반복 깨짐 → BOS 후 Breaker로 추적.
  - 주말 thin liquidity에서 false rejection 빈번.
**출처**:
  - https://innercircletrader.net/tutorials/ict-bearish-order-block/
  - https://tradingfinder.com/education/forex/ict-bearish-order-block/

### 1.3 Breaker Block (브레이커 블록)
**개요**: Breaker는 "실패한 OB"가 반대 역할로 전환된 영역이다. 가격이 OB를 깨뜨리고 반대 방향으로 BOS를 만들면, 원래 OB는 새로운 추세에서 지지/저항으로 재활용된다. **반드시 liquidity sweep을 동반**해야 정통 Breaker로 분류된다.
**시그널 정의**:
  - Bullish Breaker 식별: (1) 직전 swing low(SSL)를 sweep하는 wick, (2) 그 다음 캔들이 직전 swing high를 종가 break (MSS), (3) 깨진 bearish OB가 bullish Breaker가 됨.
  - Entry: 가격이 Breaker zone으로 retrace + LTF에서 bullish displacement/FVG 형성 → zone 상단에서 long.
  - SL: Breaker low (sweep wick) 아래 0.2×ATR.
  - TP: MSS 이후 형성된 첫 BSL → 외부 liquidity.
**결합 필터**:
  - 반드시 liquidity sweep 선행 (이게 없으면 Mitigation Block).
  - HTF bias 일치.
  - FVG가 Breaker zone 내부 또는 인접 시 confluence.
**실패 케이스 / 함정**:
  - Sweep 없는 단순 OB 깨짐은 Breaker 아님 → "weak Breaker" 분류, 패스 권장.
  - 첫 retest에서만 신뢰도 높음. 2회차 이후는 자주 실패.
  - Daily/Weekly close 직전 형성된 Breaker는 다음 세션에서 invalidation 빈번.
**출처**:
  - https://innercircletrader.net/tutorials/ict-breaker-block-trading/
  - https://fxnx.com/en/blog/ict-breaker-blocks-master-art-trading-failed-order-blocks
  - https://www.xs.com/en/blog/breaker-block/

### 1.4 Mitigation Block (미티게이션 블록)
**개요**: Mitigation Block은 sweep 없이 단순 구조 break로 전환된 zone. Breaker보다 momentum이 약하며, "기관이 미체결 주문을 추가 mitigate한다"는 가설.
**시그널 정의**:
  - 식별: 가격이 직전 swing low를 sweep하지 **않고** 그대로 swing high를 break (bullish 케이스).
  - Entry: zone 재방문 + LTF CHOCH 시 진입.
  - SL/TP: Breaker와 동일 구조, 단 RR target 1:1.5로 축소 권장.
**결합 필터**: HTF bias 강하게 일치할 때만 사용.
**실패 케이스 / 함정**: 신뢰도 본질적으로 Breaker보다 낮음. 단독 사용 비권장, FVG/OTE confluence 필수.
**출처**:
  - https://tradingfinder.com/education/forex/ict-mitigation-block/
  - https://innercircletrader.net/tutorials/ict-mitigation-block-explained/
  - https://www.mql5.com/en/articles/19619

---

## 2. Fair Value Gap (FVG) / Imbalance

### 2.1 Bullish FVG
**개요**: 3개 연속 캔들에서 Candle-1의 high와 Candle-3의 low 사이에 미체결 영역이 형성되는 imbalance. 시장이 너무 빠르게 한 방향으로 이동해 거래되지 않은 가격 구간이며, 통계적으로 70~80% 케이스에서 가격이 재방문한다.
**시그널 정의**:
  - 식별: 3-bar pattern (C1, C2, C3)에서 C1.high < C3.low (bullish FVG). C2는 일반적으로 큰 양봉(displacement candle).
  - FVG zone: [C1.high, C3.low].
  - Entry: 가격이 FVG zone으로 회귀 시 zone 상단(C3.low) 또는 50% midpoint 터치 시 long. 보수형은 midpoint 위에서 1m/5m bullish close 확인 후 진입.
  - SL: FVG 하단(C1.high) 아래 0.2×ATR, 또는 직전 swing low.
  - TP: 다음 BSL pool, HTF FVG 상단, 1:2 RR 최소.
**결합 필터**:
  - C2 캔들 바디가 ATR(14)의 1.5배 이상 (displacement 검증).
  - HTF discount 영역에 위치.
  - OB와 겹치면 high-prob.
  - Killzone 내 형성 우선.
**실패 케이스 / 함정**:
  - **FVG fully filled and close beyond** → 무효, IFVG로 전환 가능성.
  - 횡보장(레인지)에서 형성된 FVG는 자주 전체 fill됨.
  - HTF FVG는 며칠~몇 주 후에 채워지므로 단기 진입 신호로 부적합.
**출처**:
  - https://www.luxalgo.com/blog/fair-value-gap-market-imbalance-trading-hack/
  - https://tradingstrategyguides.com/day-6-fair-value-gaps-explained-ict-smc-fvg-trading-guide/
  - https://trendspider.com/learning-center/fair-value-gap-trading-strategy/
  - https://www.equiti.com/sc-en/news/trading-ideas/fair-value-gap-fvg-the-complete-guide-for-ict-traders/

### 2.2 Bearish FVG
**시그널 정의**:
  - 식별: C1.low > C3.high. C2는 큰 음봉.
  - FVG zone: [C3.high, C1.low].
  - Entry: 가격이 zone으로 회귀 시 zone 하단 또는 midpoint에서 short.
  - SL: zone 상단(C1.low) 위 0.2×ATR.
  - TP: 다음 SSL, HTF FVG 하단.
**결합 필터/실패 케이스**: Bullish FVG와 대칭.
**출처**: 위 동일 + https://innercircletrader.net/tutorials/ict-fair-value-gap-fvg/

### 2.3 Inversion FVG (IFVG)
**개요**: 기존 FVG가 가격에 의해 완전히 관통(close beyond)되면, 그 zone은 반대 역할로 작동한다. Bearish FVG가 깨지면 bullish IFVG, bullish FVG가 깨지면 bearish IFVG.
**시그널 정의**:
  - Bullish IFVG: bearish FVG가 candle close 기준으로 상향 돌파 → 동일 zone에서 가격 재방문 시 지지로 작동.
  - Entry: IFVG zone retest + LTF에서 bullish CISD(첫 양봉 close above midpoint) → long.
  - SL: IFVG 반대편 wick 아래 0.2×ATR.
  - TP: 1:2 RR 최소, 다음 liquidity pool.
**결합 필터**:
  - Liquidity grab 직후 IFVG 형성이 가장 신뢰도 높음.
  - OB / Breaker / SMT divergence 동반 시 confluence 강함.
  - NY 9:30 open 직후 또는 silver bullet 구간(10–11am NY)에 형성된 IFVG 우선.
**실패 케이스 / 함정**:
  - Invalidated FVG와 IFVG 혼동: 단순 fill ≠ IFVG. close beyond 필수.
  - 저변동 구간에서 IFVG는 noise 가능성 높음.
  - 첫 번째 터치에서만 작동, 2회차 이후는 약함.
**출처**:
  - https://www.ebc.com/forex/inverse-fair-value-gaps-in-smc-how-to-trade-efficiently
  - https://www.tradingview.com/chart/BTCUSDT.P/L39WTf6H-Inversion-Fair-Value-Gaps-IFVGs-A-Deep-Dive-Trading-Guide/
  - https://www.fluxcharts.com/articles/inversion-fair-value-gaps-ifvg-explained
  - https://www.tradezella.com/strategies/ifvg-trading-model

---

## 3. Liquidity 개념

### 3.1 Buy-Side Liquidity (BSL)
**개요**: BSL은 명확한 swing high, equal highs, trendline high 위에 누적된 매수 stop(숏 stop-loss + breakout buy order) 주문 구역이다. 기관은 자신의 매도 포지션을 채우기 위해 이 영역을 의도적으로 sweep한다.
**시그널 정의**:
  - BSL 식별: 직전 swing high, EQH (2개 이상의 거의 동일한 high, ≤ 0.1% 차이), 트렌드라인 위.
  - 이용: BSL sweep 후 즉시 LTF에서 bearish CHOCH/MSS 발생 시 short. SL은 BSL high + 0.2×ATR.
**결합 필터**: HTF가 premium 영역, killzone 내 sweep 우선.
**실패 케이스**: Sweep 후 가격이 sustained close above BSL → 진정한 breakout, 진입 보류.
**출처**: https://tradingfinder.com/education/forex/ict-bsl-ssl/

### 3.2 Sell-Side Liquidity (SSL)
**개요**: SSL은 swing low, equal lows, trendline low 아래의 매도 stop(롱 stop-loss + breakout sell) 영역.
**시그널 정의**:
  - SSL 식별: swing low, EQL.
  - 이용: SSL sweep + bullish CHOCH/MSS → long. SL은 SSL low - 0.2×ATR.
**결합 필터**: HTF discount, killzone.
**실패 케이스**: Sustained close below SSL → 진정한 breakdown.
**출처**: https://tradingfinder.com/education/forex/ict-bsl-ssl/

### 3.3 Liquidity Sweep / Stop Hunt
**개요**: 가격이 BSL 또는 SSL을 wick으로 잠시 관통한 뒤 빠르게 회귀하는 패턴. 기관이 retail stop을 trigger시켜 자신들의 fill을 확보하는 구조.
**시그널 정의**:
  - Sweep 식별: 캔들 high가 BSL 위로 돌파 but **close는 BSL 아래**. wick 길이 ≥ 캔들 body의 1.5배. 이상적으로 1~3 캔들 내에 회귀.
  - Entry: sweep 직후 LTF(1m/5m)에서 반대 방향 CHOCH + FVG 형성 → 진입.
  - SL: sweep wick 끝 + 0.1×ATR.
  - TP: 반대편 liquidity pool, 1:2 RR.
**결합 필터**:
  - HTF bias와 sweep 방향 일치 (역추세 sweep 무시 권장).
  - Killzone 내 sweep만 유효.
  - Volume spike (이전 20캔들 평균 1.5배 이상).
  - SMT divergence on correlated asset (BTC sweep 시 ETH는 not sweep — 4.x 참조).
**실패 케이스 / 함정**:
  - **Sustained sweep**: wick 아닌 body close beyond → 진정한 breakout. 진입 시 stop-out.
  - 주말/holiday thin volume에서 random sweep 발생 빈번.
  - 동일 BSL에서 2회 이상 반복 sweep → 그 영역 신뢰도 소진.
**출처**:
  - https://arongroups.co/technical-analyze/liquidity-in-ict/
  - https://www.equiti.com/sc-en/news/trading-ideas/liquidity-sweeps-explained-how-to-identify-and-trade-them/
  - https://www.fluxcharts.com/articles/Trading-Concepts/Price-Action/liquidity-sweeps
  - https://innercircletrader.net/tutorials/ict-liquidity-sweep-vs-liquidity-run/

### 3.4 Equal Highs / Lows (EQH / EQL)
**개요**: 거의 같은 가격에서 형성된 2개 이상의 high/low. retail 트레이더가 명확히 인식하기 때문에 stop이 클러스터로 누적된다 → 기관의 우선 sweep 타깃.
**시그널 정의**:
  - EQH/EQL 식별: |high1 - high2| / price ≤ 0.1% (BTC 기준 약 ±50~100 USD on 50k 가격).
  - 이용: EQH/EQL을 BSL/SSL으로 표시하고 sweep 시그널 활용 (3.3 동일).
**실패 케이스**: 3개 이상의 EQH/EQL은 자주 진정한 breakout으로 이어짐 → sweep 트레이드 비권장.
**출처**: https://tradingfinder.com/education/forex/ict-bsl-ssl/

---

## 4. Market Structure

### 4.1 Break of Structure (BOS) — 추세 연속
**개요**: 진행 중인 추세 방향으로 직전 swing point를 종가 기준 돌파. 추세 지속 신호.
**시그널 정의**:
  - Bullish BOS: 가격이 직전 swing high를 캔들 종가로 돌파 (HH 형성). 직전 추세도 bullish (HH-HL).
  - Bearish BOS: 직전 swing low를 종가 돌파 (LL 형성). 직전 추세 bearish.
  - Entry: BOS 후 retracement, 가장 가까운 OB/FVG/OTE zone에서 추세 방향 진입.
  - SL: 직전 swing point(BOS 형성 전 HL 또는 LH) 너머.
  - TP: 다음 liquidity, 1:2 RR.
**결합 필터**: BOS 캔들 바디 길이 ≥ 1×ATR (displacement). HTF align.
**실패 케이스**:
  - Wick-only BOS (close 미달) → 무효.
  - 첫 BOS 이후 retracement 없이 바로 진입 시 chase risk.
**출처**:
  - https://innercircletrader.net/tutorials/break-of-structure-vs-change-of-character/
  - https://www.fluxcharts.com/articles/Trading-Concepts/Price-Action/Break-of-Structures
  - https://www.mindmathmoney.com/articles/break-of-structure-bos-and-change-of-character-choch-trading-strategy

### 4.2 Change of Character (CHOCH) — 추세 전환
**개요**: 기존 추세 반대 방향으로의 첫 swing point 돌파. 추세 전환 가능성 신호. 종종 reversal trade의 anchor가 된다.
**시그널 정의**:
  - Bullish CHOCH: bearish 추세(LH-LL) 중 직전 LH를 종가 돌파.
  - Bearish CHOCH: bullish 추세(HH-HL) 중 직전 HL을 종가 돌파.
  - Entry: CHOCH 후 첫 OB/FVG retest에서 새로운 방향 진입.
  - SL: CHOCH 형성 전 extreme(LL 또는 HH) 너머.
**결합 필터**: 액티브 liquidity sweep 동반 시 신뢰도 +. HTF FVG/OB 영역에서 CHOCH 발생 시 prime.
**실패 케이스**:
  - CHOCH 후 즉시 다시 반대 방향 BOS → "fakeout CHOCH". 첫 retest 보수적 접근 필수.
  - Range market에서는 CHOCH 빈번하지만 후속 trend 약함.
**출처**: 위 동일.

### 4.3 Market Structure Shift (MSS)
**개요**: CHOCH의 더 엄격한 형태. **liquidity sweep + 강한 displacement (FVG 형성)** 까지 동반된 break.
**시그널 정의**:
  - 조건: (1) 직전 BSL/SSL sweep, (2) 반대 방향 swing point의 종가 break, (3) break 캔들이 FVG 형성.
  - Entry: MSS 후 FVG로 retrace 시 진입.
  - SL: sweep wick 너머.
  - TP: 1:2~1:3 RR.
**결합 필터**: silver bullet, judas swing 등 시간 기반 setup과 결합 시 매우 강력.
**실패 케이스**: Displacement 부재 시 일반 CHOCH로 격하, RR 보수화.
**출처**:
  - https://www.luxalgo.com/blog/market-structure-shifts-mss-in-ict-trading/
  - https://innercircletrader.net/tutorials/ict-market-structure-shift/
  - https://tradingfinder.com/education/forex/ict-mss/

### 4.4 Internal vs External Structure
**개요**: External structure는 큰 swing(HTF) — Daily/4H의 주요 high/low. Internal structure는 그 안에서 형성되는 LTF swing(15m/1m). 둘이 일치할 때 high-confidence.
**시그널 정의**:
  - External BOS lookback: 50~100 candles.
  - Internal BOS lookback: 5~49 candles.
  - 사용 패턴: External BOS bullish + internal CHOCH bearish at premium → external 방향(long) trade as internal sweep terminates.
**결합 필터**: External 추세 우위 + internal에서 entry trigger.
**실패 케이스**: Internal과 external 불일치 시 trade skip 또는 매우 작은 size.
**출처**:
  - https://www.luxalgo.com/blog/market-structure-shifts-mss-in-ict-trading/
  - https://innercircletrader.net/tutorials/break-of-structure-vs-change-of-character/

---

## 5. Premium / Discount / Equilibrium

### 5.1 Premium / Discount Zone
**개요**: 임의의 swing 구간(가장 최근 HTF impulse low ↔ high)의 fibonacci 0~1 retracement에서 0.5는 equilibrium, 0.5 위는 premium(매도 우선), 0.5 아래는 discount(매수 우선).
**시그널 정의**:
  - 측정: 최근 HTF swing low(0.0)와 swing high(1.0) 사이 fib retracement 그리기.
  - Long bias: 가격이 discount(0~0.5)에 있을 때만.
  - Short bias: 가격이 premium(0.5~1.0)에 있을 때만.
  - Equilibrium 중심 진입은 회피 (낮은 RR).
**결합 필터**: HTF bias 일치, OB/FVG가 zone 내부에 위치.
**실패 케이스**: Trending market에서는 premium에서 매도해도 새 high 갱신 가능. 항상 추세 방향 우선.
**출처**:
  - https://tradingfinder.com/education/forex/ict-fibonacci-levels/
  - https://innercircletrader.net/tutorials/ict-fibonacci-levels/

### 5.2 Optimal Trade Entry (OTE)
**개요**: HTF impulse의 fibonacci 0.62~0.79 retracement zone. 0.705가 정밀 sweet spot. 기관 압력이 가장 집중되는 retracement 영역으로 간주.
**시그널 정의**:
  - 측정: HTF impulse 시작점(0)과 종점(1) 사이 fib. 0.62/0.705/0.79 표시.
  - Entry: 가격이 OTE band(0.62~0.79) 내 진입 + LTF CHOCH/FVG/OB confluence + LTF displacement candle 발생 시 진입.
  - SL: 0.79 너머 (impulse extreme 너머가 더 안전).
  - TP1: 0.0 retracement (impulse 시작점)
  - TP2: -0.27 (이전 swing 너머)
  - TP3: -0.62 (extension)
**결합 필터**:
  - OTE는 위치 기반 zone — 단독 사용 불가, 반드시 OB/FVG/structure confluence.
  - Killzone 내 진입 우선.
**실패 케이스**:
  - Strong trend continuation 시 0.5 이상 retrace 안 함 → entry miss.
  - OTE 너머 0.79 깊은 retracement → 추세 약화 신호, trade pass.
**출처**:
  - https://innercircletrader.net/tutorials/ict-optimal-trade-entry-ote-pattern/
  - https://www.writofinance.com/trading-with-ict-optimal-trade-entry-ote-zone/
  - https://fxnx.com/en/blog/ict-fibonacci-ote-your-precision-entry-guide
  - https://tradingfinder.com/education/forex/ict-optimal-trade-entry-pattern/

---

## 6. Killzones / Sessions — 크립토 24/7 적용

### 6.1 ICT 표준 Killzones (NY Time → UTC)
**개요**: ICT는 4개의 주요 killzone에서만 trade하라고 규정. 나머지 시간은 noise. 크립토는 24/7이지만 BTC/ETH의 변동성·거래량은 여전히 forex/주식 세션과 강하게 동조한다.
**시그널 정의 (시간 윈도우)**:
  - **Asian Killzone**: 19:00–22:00 NY (00:00–03:00 UTC). 보통 range/accumulation.
  - **London Killzone**: 02:00–05:00 NY (07:00–10:00 UTC). Manipulation/Judas swing 빈번.
  - **NY AM Killzone**: 08:00–11:00 NY (13:00–16:00 UTC). 주요 displacement.
  - **NY PM Killzone**: 13:00–16:00 NY (18:00–21:00 UTC). Continuation 또는 reversal.
  - **Silver Bullet windows**: 03:00–04:00 NY (London SB), 10:00–11:00 NY (AM SB), 14:00–15:00 NY (PM SB).
**결합 필터**:
  - 모든 entry 시그널에 killzone 필터 적용 가능 (시그널 발생 시간이 killzone 내인지 검증).
  - 크립토 추가 고려: 14:00–15:00 UTC가 BTC peak 모멘텀 시간대 (US 오전).
**실패 케이스 / 함정**:
  - 주말(토요일 00:00 UTC ~ 일요일 22:00 UTC) thin liquidity → killzone 시그널 신뢰도 급락.
  - 크립토 특이 이벤트(ETF 결정, 거래소 사고)는 모든 killzone 무시하고 변동성 폭증.
  - Holiday(미국 공휴일)의 NY 세션은 forex처럼 quiet하지 않음 — 크립토는 정상 가동.
**출처**:
  - https://innercircletrader.net/tutorials/master-ict-kill-zones/
  - https://tradingrage.com/learn/ict-killzone-explained
  - https://stoicresearch.substack.com/p/inside-the-killzone-timing-crypto
  - https://www.ebc.com/forex/what-are-ict-killzone-times-simple-trading-hours-guide

---

## 7. Power of Three (PO3) — Accumulation / Manipulation / Distribution

**개요**: 일중·주중·월중의 가격 행동을 3단계로 분해. (1) Accumulation: range, (2) Manipulation: 의도적 stop hunt(Judas swing), (3) Distribution: 진정한 방향으로의 expansion. 모든 timeframe에서 fractal하게 작동.
**시그널 정의 (Daily PO3 예)**:
  - Accumulation: Asia session(00:00–07:00 UTC) range 형성. high(A_H), low(A_L) 마킹.
  - Manipulation: London open(07:00–10:00 UTC)에서 A_H 또는 A_L sweep (Judas swing).
  - Distribution: NY session(13:00–21:00 UTC)에서 sweep 반대 방향으로 expansion.
  - Trade plan:
    - Bullish PO3: Asia range A_L sweep → bullish CHOCH on 5m → A_L OB/FVG retest → long. TP at A_H + extension.
    - Bearish PO3: A_H sweep → bearish CHOCH → A_H OB retest → short. TP at A_L - extension.
  - SL: sweep wick + 0.2×ATR.
**결합 필터**:
  - HTF bias가 manipulation 반대 방향과 일치해야 함 (일반적으로 daily bias가 진정한 방향).
  - DXY/SPX 같은 매크로 기준은 크립토에 약함 → BTC dominance, USDT pair flow로 대체.
**실패 케이스**:
  - Asia range가 너무 넓을 때 (>2% 변동) → sweep 실패율 증가.
  - 일중 PO3가 항상 발생하는 것은 아님 (특히 주말/holiday).
  - 더블 manipulation: London에서 양방향 sweep 후 NY에서 다시 swap → 잘못된 방향 진입 위험.
**출처**:
  - https://innercircletrader.net/tutorials/ict-power-of-3/
  - https://arongroups.co/technical-analyze/power-of-3/
  - https://fxnx.com/en/blog/mastering-the-ict-power-of-3-po3-strategy
  - https://fxopen.com/blog/en/what-is-ict-po3-and-how-do-traders-use-it/

---

## 8. SMT Divergence (Smart Money Technique Divergence)

**개요**: 상관도 높은 두 자산이 동시에 같은 swing point를 만들지 못할 때 발생하는 발산. 한 자산은 새 high/low를 만들지만 다른 자산은 실패 → "manipulation 가설"의 증거. 크립토에서는 BTC vs ETH, BTC vs Total Crypto Market Cap, BTC vs SOL 등이 주로 사용됨.
**시그널 정의**:
  - Bullish SMT: BTC가 새로운 LL을 형성(직전 SSL sweep) 했지만 ETH는 LL 갱신 실패(higher low). → BTC manipulation, bullish bias.
  - Bearish SMT: BTC가 새로운 HH(BSL sweep) 했지만 ETH는 HH 갱신 실패. → bearish bias.
  - Entry: SMT 확인 후 LTF CHOCH/MSS + FVG/OB confluence에서 진입.
  - SL: SMT가 발생한 swing extreme 너머.
**결합 필터**:
  - 같은 timeframe에서 두 자산 비교 (1m, 5m, 15m, 1H, 4H 모두 fractal).
  - 두 자산의 상관계수(rolling 100기간)가 0.7 이상일 때만 유효.
  - Killzone 내에서만 활용.
**실패 케이스 / 함정**:
  - 단독 사용 금지 — SMT는 hypothesis, 진입은 CISD(Change in State of Delivery) 또는 MSS 동반 시에만.
  - 상관 깨진 구간(e.g., ETH-only news)에서는 SMT 무의미.
  - Altcoin은 BTC와의 lag 때문에 noisy SMT 발생 빈번.
**출처**:
  - https://innercircletrader.net/tutorials/ict-smt-divergence-smart-money-technique/
  - https://tradingfinder.com/education/forex/ict-smt-divergence/
  - https://www.atmexx.com/educational-articles/mastering-divergence-trading-ict-smt-strategies-explained
  - https://medium.com/@leooinvests/smt-divergence-reading-manipulated-markets-through-correlated-assets-c4206a974a99

---

## 9. 크립토 적용 ICT Setups (조합형)

### 9.1 Silver Bullet — NY AM 10–11 NY
**개요**: NY 10:00–11:00 NY Time(15:00–16:00 UTC) 60분 윈도우 내에 발생하는 liquidity sweep + MSS + FVG retest 패턴. ICT가 가장 강조하는 정형 setup.
**시그널 정의**:
  - 시간 윈도우: 10:00:00 ~ 11:00:00 NY Time.
  - 단계:
    1. 09:30–10:00 NY 사이의 swing high/low 식별 (직전 60분 high/low가 BSL/SSL).
    2. 10:00 이후 BSL 또는 SSL을 wick으로 sweep.
    3. Sweep 직후 1m/5m에서 반대 방향 MSS (close beyond opposite swing).
    4. MSS 캔들이 FVG 형성.
    5. FVG로 retrace 시 진입.
  - SL: sweep wick + 0.2×ATR(14, 1m).
  - TP: 직전 swing 반대편 liquidity, 최소 1:2 RR.
**결합 필터**:
  - HTF bias 일치 시에만 진입.
  - OB가 FVG와 겹치면 stack confluence.
  - SMT divergence (BTC/ETH) 추가 시 highest prob.
**실패 케이스**:
  - 10:00 직전 큰 매크로 뉴스(US CPI 발표 08:30 ET 등) 시 setup 무효 빈번.
  - Sweep 후 immediate continuation (no MSS) → 진입 보류.
  - Range-bound 세션에서는 false MSS 빈번.
**출처**:
  - https://innercircletrader.net/tutorials/ict-silver-bullet-strategy/
  - https://smartmoneyict.com/ict-silver-bullet-strategy/
  - https://howtotrade.com/trading-strategies/ict-silver-bullet/
  - https://www.luxalgo.com/blog/ict-silver-bullet-setup-trading-methods/

### 9.2 Asian Range Sweep
**개요**: Asia session(19:00 NY ~ 03:00 NY = 00:00 ~ 08:00 UTC)의 range high/low가 London/NY 세션에서 sweep되는 패턴. 크립토에서는 BTC가 특히 자주 따른다.
**시그널 정의**:
  - 단계:
    1. Asia range high/low (A_H, A_L) 식별 — 19:00 NY ~ 03:00 NY 구간.
    2. London open(02:00–05:00 NY) 또는 NY open(08:00–10:00 NY)에서 A_H 또는 A_L sweep.
    3. Sweep 후 LTF CHOCH/MSS + FVG/OB.
    4. Retrace 진입.
  - SL: sweep wick + 0.2×ATR.
  - TP: opposite Asia range extreme + extension.
**결합 필터**:
  - HTF daily bias가 sweep 반대 방향이면 high prob (Judas swing 케이스).
  - Asia range 폭이 ATR(daily)의 30~70%일 때 가장 신뢰.
**실패 케이스**:
  - Asia range가 너무 작으면(< 0.3% BTC 기준) sweep 후 noise 많음.
  - 양방향 sweep (A_H sweep → A_L sweep 연속) 시 trade skip.
  - 주말 직후 월요일 Asia range는 신뢰도 낮음.
**출처**:
  - https://innercircletrader.net/tutorials/ict-asian-range/
  - https://tradingfinder.com/education/forex/ict-asian-range-trading-strategy/
  - https://www.cryptocraft.com/thread/1347080-explaining-ict-asian-range-strategy-tflab

### 9.3 Judas Swing
**개요**: 세션 시작 직후 진정한 방향과 반대로 가짜 움직임을 만들어 retail breakout trader를 trap. 가장 흔한 시간대는 London open.
**시그널 정의**:
  - 시간: London open 02:00–05:00 NY (07:00–10:00 UTC) 또는 NY midnight 00:00 NY (05:00 UTC).
  - 단계:
    1. Asian range A_H, A_L 마킹.
    2. 세션 open 직후 1~3시간 내 A_H 또는 A_L 돌파 (Judas).
    3. 가격이 range 내부로 회귀 → CHOCH/BOS confirmation.
    4. OB/FVG retest에서 진입 (반대 방향).
  - SL: Judas extreme + 0.2×ATR.
  - TP: 반대 range extreme, 그 너머의 HTF liquidity, 1:2 RR.
**결합 필터**:
  - HTF daily bias가 sweep 반대 방향과 일치해야 함.
  - 15m/1H timeframe 분석.
**실패 케이스**:
  - 진정한 breakout인 경우 (sustained close beyond) → SL 적중.
  - 양방향 Judas (London Judas → NY 또 reverse) → 두 번 stop-out 위험.
  - 주말 효과로 월요일 London Judas는 noisy.
**출처**:
  - https://innercircletrader.net/tutorials/ict-judas-swing-complete-guide/
  - https://tradingfinder.com/education/forex/ict-judas-swing/
  - https://arongroups.co/technical-analyze/judas-swing-strategy/
  - https://fxreplay.com/strategies/judas-swing-model

### 9.4 OTE + Liquidity Sweep Combo
**개요**: 가장 일반화된 ICT entry — sweep + OTE + OB/FVG confluence.
**시그널 정의**:
  - 단계:
    1. HTF impulse 식별 (last clear leg).
    2. Liquidity sweep (BSL or SSL) 발생.
    3. LTF CHOCH/MSS.
    4. 가격이 HTF impulse fib OTE(0.62–0.79)로 retrace.
    5. OTE band 내 OB 또는 FVG에서 진입.
  - SL: 0.79 너머 또는 OB extreme.
  - TP: 0.0 retracement, -0.27, -0.62 단계별 분할.
**결합 필터**: HTF bias, killzone, SMT.
**실패 케이스**: OTE를 깊게 침투(>0.79) 후 회귀 안 함 → 추세 약화로 해석, trade close.
**출처**: 5.2 OTE 출처와 동일.

---

## 10. ICT/SMC 일반 실패 모드 / 비판

**개요**: 자동 시스템 설계 시 다음 한계를 반드시 인식해야 한다.
**핵심 함정**:
  - **Subjectivity**: OB/FVG/swing point 식별이 lookback 파라미터에 매우 민감. 동일 차트에서 서로 다른 식별 결과 발생 → 백테스트 결과의 robustness가 낮음.
  - **Curve fitting 위험**: ICT 룰을 과도하게 세부화하면(예: "OB 50% midpoint + FVG midpoint + Killzone + SMT") 신호 빈도 급감, 과거 데이터에 과적합.
  - **No empirical edge proof**: 학술적 검증 부재. 일부 비판자들은 "기존 supply/demand의 rebrand"라고 평가.
  - **Confirmation bias**: 결과 본 후 swing point/OB를 backwards 식별 가능 → forward test 시 성과 급락.
  - **High-impact news invalidation**: FOMC, CPI, ETF 결정, 거래소 해킹 등 매크로 이벤트는 모든 ICT 구조 무효화.
  - **Crypto-specific issues**: 24/7 시장이라 ICT의 forex 세션 가정이 약화됨. 주말/holiday low-volume 구간에서 false signal 빈번.
  - **Equal level over-mining**: 동일 EQH/EQL이 2회 이상 sweep되면 효력 소진.
**완화 전략**:
  - HTF bias 엄격 적용 (Daily/4H 추세 반대 trade 금지).
  - 모든 setup에 최소 2개 이상 confluence 요구 (OB+FVG+killzone 등).
  - Walk-forward 백테스트 필수 (단일 train/test split 금지).
  - 매크로 이벤트 캘린더 필터 (이벤트 ±30분 trade 회피).
  - RR 최소 1:2, 1:3 권장.
  - 신호 빈도가 너무 낮으면(예: 월 < 5회) 시스템 가치 재평가.
**출처**:
  - https://www.earnforex.com/guides/smart-money-concepts-flaws/
  - https://tradingrush.net/debunking-smart-money-concepts-trading-strategies/
  - https://algostorm.com/ict-smc-entry-models/
  - https://financial-hacker.com/why-90-of-backtests-fail/
  - https://www.luxalgo.com/blog/what-is-overfitting-in-trading-strategies/

---

## 11. 자동화 구현 체크리스트 (Strategy Generator용)

자동 전략 생성기는 다음 컴포넌트를 ICT/SMC 룰을 algo로 변환할 때 표준 인터페이스로 제공해야 한다.

1. **Swing Point Detector**
   - Pivot lookback: external=50, internal=10 (parameterizable).
   - HH/HL/LH/LL 분류기.

2. **Order Block Identifier**
   - Last opposite candle before displacement (≥ 1.5×ATR).
   - Bullish/Bearish/Breaker/Mitigation 4종 분류.
   - Freshness 카운터 (touched count).

3. **FVG Detector**
   - 3-bar imbalance 검출.
   - Filled/Partially-filled/Active 상태 추적.
   - IFVG 전환 감지 (close beyond 시).

4. **Liquidity Mapper**
   - BSL/SSL pool 자동 마킹 (swing high/low + EQH/EQL ≤ 0.1% 동일).
   - Sweep 이벤트 emit.

5. **Structure State Machine**
   - 현재 추세 상태(Bullish/Bearish/Range).
   - BOS / CHOCH / MSS 이벤트 emit.

6. **Premium/Discount Calculator**
   - 최근 HTF impulse 기반 fib 0~1.
   - OTE band(0.62, 0.705, 0.79) 자동 표시.

7. **Killzone Time Filter**
   - 입력: 캔들 timestamp (UTC).
   - 출력: London/NY-AM/NY-PM/Asia/Silver-Bullet 여부.

8. **SMT Divergence Engine**
   - BTC ↔ ETH (또는 SOL) rolling correlation 계산 (window=100).
   - 상관 0.7 이상일 때만 swing point 비교.

9. **Confluence Scorer**
   - 각 setup에 점수: OB(2점) + FVG(2점) + OTE(1점) + Killzone(1점) + SMT(2점) → threshold 이상만 fire.

10. **Risk Manager**
    - SL: 시그널별 정의된 anchor + 0.2×ATR buffer.
    - TP: 1:2 / 1:3 / opposite liquidity 옵션.
    - News-event blackout (매크로 캘린더 hook).

---

## 12. 참고 (포괄적)

- ICT 공식 사이트(커뮤니티 운영): https://innercircletrader.net/
- ICT 공식 X(트위터, 강의 핵심 인사이트): https://x.com/I_Am_The_ICT (외부 인용용)
- LuxAlgo ICT 시리즈: https://www.luxalgo.com/blog/category/ict/
- TradingFinder ICT 카테고리: https://tradingfinder.com/education/forex/ (각 컨셉별 페이지)
- Mind Math Money (BOS/CHOCH 정리): https://www.mindmathmoney.com/articles/break-of-structure-bos-and-change-of-character-choch-trading-strategy
- Smart Money Concepts 비판: https://www.earnforex.com/guides/smart-money-concepts-flaws/
- 백테스트 함정: https://financial-hacker.com/why-90-of-backtests-fail/
- 크립토 적용 사례: https://stoicresearch.substack.com/p/inside-the-killzone-timing-crypto

---

> **중요 주의**: 본 문서의 모든 룰은 **결정론적 검출은 가능하나 절대 수익을 보장하지 않는다.** ICT/SMC는 학술적 검증이 부재한 price-action heuristic이다. 자동 생성기는 이를 hypothesis로만 취급하고, 백테스트·forward test·position sizing·risk management로 강건성을 검증해야 한다.

---

## 13. 부록 A — 구체 BTC 수치 예시 (Walk-through)

### A.1 Bullish Order Block on 1H BTC
가정: BTC 4H bias bullish (HH-HL 구조). 1H 차트.
1. 14:00 UTC 1H 캔들 = 음봉, open=64,800, high=65,000, low=64,500, close=64,600.
2. 15:00 UTC 1H 캔들 = 양봉, open=64,600, high=66,200, low=64,580, close=66,100. close > 65,000 (C1 high) → displacement 검증.
3. 15:00–18:00 UTC 누적 변위 = 66,800 - 64,500 = 2,300 ≥ 1.5 × ATR(14, 1H) (당일 ATR ≈ 1,400 가정 → 1.5× = 2,100). 검증 OK.
4. OB zone = [64,500, 65,000]. Midpoint = 64,750.
5. 21:00 UTC 가격 64,750 터치, 5m에서 bullish CHOCH (직전 5m LH 65,150 close above) 확인.
6. Long entry @ 64,800. SL @ 64,500 - 0.2×ATR(1H) = 64,500 - 280 = 64,220. Risk = 580 USD.
7. TP1 @ 직전 swing high 66,200 (+1,400, RR=2.4). TP2 @ HTF FVG 67,500 (+2,700, RR=4.7).

### A.2 Silver Bullet on 1m BTC (NY AM)
1. 09:30–10:00 NY: 1m chart에서 BSL = 67,420 (직전 high), SSL = 67,180 (직전 low).
2. 10:07 NY 1m 캔들이 67,425까지 wick 후 close=67,395. → BSL sweep 확정.
3. 10:09 NY 1m 캔들이 67,170 close 돌파 (직전 1m LL break) → bearish MSS 확정. 동시에 67,210–67,260 bearish FVG 형성.
4. 10:14 NY 가격이 67,250 터치 (FVG 내부 midpoint).
5. Short entry @ 67,250. SL @ 67,425 (sweep wick) + 0.2×ATR(1m) ≈ 67,460. Risk = 210.
6. TP1 @ SSL 67,180 (RR=0.33, partial). TP2 @ session low 66,800 (RR=2.1).

### A.3 Asian Range Sweep (Bullish PO3)
1. Asia range (00:00–08:00 UTC): A_H = 62,300, A_L = 61,650.
2. London open 07:30 UTC: 가격 61,580까지 하락 후 회귀 (1H wick) → A_L sweep + Judas swing 가설.
3. 09:00 UTC 15m bullish CHOCH (직전 15m LH 61,950 close 돌파). FVG 형성 [61,720, 61,820].
4. 10:30 UTC 가격이 61,770 (FVG midpoint) 터치.
5. Long entry @ 61,800. SL @ 61,580 - 0.2×ATR(15m) = 61,520. Risk = 280.
6. TP1 @ A_H 62,300 (RR=1.78). TP2 @ HTF BSL 62,900 (RR=3.9).

---

## 14. 부록 B — Pseudo-code (Strategy Engine 통합 힌트)

```python
# 의사 코드 — 실제 구현은 src/strategy/ict_smc.py 등에 위치
class IctSmcSignal:
    def detect(self, ohlcv_htf, ohlcv_ltf, btc_ohlcv, eth_ohlcv, now_utc):
        bias = self.htf_bias(ohlcv_htf)              # "bullish" | "bearish" | "range"
        if bias == "range":
            return None

        kz = killzone_of(now_utc)                     # "asia"|"london"|"nyam"|"nypm"|None
        if kz is None:
            return None

        liq = self.liquidity_pools(ohlcv_ltf)         # [BSL, SSL, EQH, EQL]
        sweep = self.detect_sweep(ohlcv_ltf, liq)
        if not sweep:
            return None

        mss = self.detect_mss(ohlcv_ltf, after=sweep) # MSS = sweep + close-break + FVG
        if not mss:
            return None

        ote = self.fib_ote(ohlcv_htf, mss.impulse)    # 0.62~0.79 band
        ob  = self.find_ob_in_zone(ohlcv_ltf, ote)
        fvg = self.find_fvg_in_zone(ohlcv_ltf, ote)
        if not (ob or fvg):
            return None

        smt = self.smt_divergence(btc_ohlcv, eth_ohlcv, sweep)

        score = (2 if ob else 0) + (2 if fvg else 0) \
              + (1 if ote.contains(price) else 0) \
              + (1 if kz in ("nyam", "london") else 0) \
              + (2 if smt else 0)

        if score < 5:
            return None

        return Signal(
            side="long" if bias == "bullish" else "short",
            entry=ob.midpoint() if ob else fvg.midpoint(),
            sl=sweep.wick_extreme + 0.2 * atr(ohlcv_ltf),
            tp=next_opposite_liquidity(liq, bias),
            confluence_score=score,
        )
```

핵심 책임 분리:
- `htf_bias()`: Daily/4H에서 HH-HL 또는 LH-LL 시퀀스 분류.
- `liquidity_pools()`: pivot detection + EQH/EQL clustering (≤ 0.1% 차이).
- `detect_sweep()`: wick > body × 1.5 AND wick beyond pool AND close inside pool.
- `detect_mss()`: 직전 swing point close break + FVG 형성 검증.
- `fib_ote()`: 마지막 impulse leg에 fib 0.62/0.705/0.79 그리기.
- `smt_divergence()`: rolling correlation > 0.7일 때만 swing point 비교.

---

## 15. 부록 C — 시그널별 빈도/리스크 프로파일 추정

> 아래 수치는 ICT 트레이더 커뮤니티의 공개 백테스트·discretionary 트레이딩 보고를 종합한 **추정치**이며, 본 시스템 내 backtest로 재검증해야 한다.

| Setup | 빈도 (asset당, 평일) | 평균 RR (보수) | 추정 Win Rate | 노트 |
|-------|----------------------|----------------|---------------|------|
| Silver Bullet (NY AM) | 0.5–1 | 1:2 | 40–55% | 매크로 뉴스 회피 시 향상 |
| Asian Range Sweep | 0.5–1 | 1:2 | 35–50% | London/NY open 동조 시 향상 |
| Judas Swing | 0.3–0.7 | 1:2.5 | 35–50% | HTF bias align 필수 |
| OTE + Sweep Combo | 0.2–0.5 | 1:3 | 40–55% | 가장 보수적, 빈도 낮음 |
| OB Retest (단독) | 1–3 | 1:1.5 | 30–45% | confluence 없으면 비추 |
| FVG Retest (단독) | 2–5 | 1:1.5 | 30–40% | noise 많음, 필터 필수 |
| IFVG | 0.5–1.5 | 1:2 | 40–55% | sweep 직후 IFVG 가장 강함 |
| BOS Continuation | 1–3 | 1:1.5 | 35–50% | 추세 강할수록 win rate 상승 |
| CHOCH Reversal | 0.3–0.8 | 1:2 | 30–45% | fakeout 자주 발생 |

가정:
- 슬리피지·수수료 미반영. 실제 backtest에서는 RR이 0.1~0.3 감소.
- 모든 setup은 단독 시 win rate 하단, 2개 confluence 시 상단.
- 크립토 변동성 폭증 구간 (예: 2024–2025 ETF approval 이벤트) 데이터 포함 시 win rate 변동성 큼.

---

## 16. 부록 D — 미해결 / 추후 조사 항목

다음 항목은 본 문서 작성 시 권위 있는 출처를 충분히 확보하지 못했거나, 크립토 특수 케이스에 대한 정량 데이터가 부족함:

1. **CISD (Change in State of Delivery)** — ICT 후기 강의에서 강조되나 공개 자료가 흩어져 있음. 추가 mentorship transcript 필요.
2. **Quarterly Theory / Time-based PD Array** — ICT 2024+ 강의 주제, 90분 분기 모델. 검증 가능한 자료 부족.
3. **Crypto-specific SMT pairs** — BTC/ETH 외에 BTC/SOL, BTC/Total3 등의 정량 상관 데이터 필요.
4. **NWOG (New Week Opening Gap), NDOG (New Day Opening Gap)** — 크립토 주말 갭 적용 가능성. forex 자료는 풍부하나 24/7 시장 검증 미진.
5. **Reddit/algorithmic 실증 백테스트** — r/algotrading, r/cryptocurrency에서 ICT/SMC 정식 backtest 결과 공개 사례 부족. 학술 검증된 edge 자료 미발견.
6. **IPDA (Interbank Price Delivery Algorithm)** — ICT 핵심 가정이지만 검증 불가능한 메타-개념. 알고리즘화 시 hypothesis 수준에서만 인용.

> 위 항목은 후속 research cycle 작업으로 별도 처리 권장.

