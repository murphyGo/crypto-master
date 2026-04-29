# Crypto-Native Trading Techniques

크립토 시장은 24/7 거래, 영구 선물(perpetual futures), 온체인 투명성, 고도 레버리지, 그리고 분산된 글로벌 거래소 구조 때문에 전통 시장에는 존재하지 않거나 매우 다른 형태로 존재하는 시그널을 만들어낸다. 본 문서는 우리 quant 시스템이 실제로 데이터를 수신/계산할 수 있는 기법만 정리한다. 각 기법은 데이터 소스(무료/유료 명시), 정확한 시그널 룰, 결합 필터, 함정을 포함한다.

데이터 소스 약어:
- **CG** = Coinglass (대부분 무료, 일부 Pro)
- **CQ** = CryptoQuant (free tier 제한, Pro $39~/월)
- **GN** = Glassnode (free tier 제한, Standard $29~, Pro/Advanced)
- **HB** = Hyblock Capital (Essential $49~/월부터)
- **AM** = Arkham Intelligence (대부분 무료)
- **NS** = Nansen (Standard $99~/월)
- **BM** = Bitcoin Magazine Pro / BMPro (대부분 무료)
- **CCXT** = 거래소 raw API (무료)

---

## 1. 파생상품 / Perp Microstructure

### 1.1 Funding Rate Extreme Mean Reversion (Long-side overcrowding)
**개요**: Perpetual futures funding rate는 perp가 spot에 anchoring되도록 longs/shorts가 8h(또는 일부 거래소 1h/4h)마다 서로 결제하는 메커니즘. funding이 비정상적으로 양수가 되면 longs가 과밀(overcrowded)이고 squeeze에 취약. 크립토 perp 특유의 자가 청산 메커니즘 때문에 전통 시장에는 없는 신호.
**시그널 정의**:
  - **Entry (Short)**: Binance/Bybit BTC-PERP funding > 0.05% (8h, 즉 annualized ~54%) for 3 consecutive periods (24h) AND price < EMA20 on 4H AND OI 7-day high. 0.5R~1R 사이즈로 short.
  - **Entry (Long)**: funding < -0.03% (8h) for 2 consecutive periods AND price > EMA20 on 4H. shorts overcrowded → long squeeze 후보.
  - **Exit/SL**: funding이 중립(±0.01%) 회귀시 익절. 진입 ATR(14) × 2 손절. 12h 내 미발현시 시간 손절.
**데이터 소스**: Coinglass `/api/futures/fundingRate/history` (무료), Binance `GET /fapi/v1/fundingRate` (무료), Bybit V5 API (무료).
**결합 필터**: OI 동시 상승(crowded long 확정), CVD spot 약세(현물 매수세 미흡), Long/Short ratio top accounts > 2.5.
**실패 케이스 / 함정**: 강한 추세장에서는 funding이 며칠간 0.1%+ 유지되면서도 가격이 계속 상승. ETF inflow 강세장(2024~2025 BTC) 같은 macro tailwind에선 mean reversion 룰이 부서진다 → BTC dominance + spot inflow 게이트로 보완.
**출처**:
- https://www.coinglass.com/learn/what-is-funding-rate-arbitrage
- https://blog.amberdata.io/the-ultimate-guide-to-funding-rate-arbitrage-amberdata
- https://ouinex.com/en/education/funding-rate-arbitrage-cashing-in-on-perpetual-swings
- https://bingx.com/en/learn/article/what-is-funding-rate-arbitrage-guide-for-futures-traders

### 1.2 Funding Rate Cross-Exchange Arbitrage (Delta-Neutral)
**개요**: 같은 자산에 대해 거래소 간 funding rate가 다르게 형성될 때 long(낮은 funding) + short(높은 funding)으로 가격 노출 0, funding spread만 수확. 시장 방향과 무관한 carry 전략.
**시그널 정의**:
  - **Entry**: Exchange_A funding − Exchange_B funding > 0.04% (8h) (annualized ~43% spread) AND 두 거래소 모두 OI > $50M (slippage 안전).
  - 진입: Exchange_B(고funding)에 short, Exchange_A(저funding)에 long, notional 동일.
  - **Exit**: spread < 0.005% (8h) 회귀시 청산. 또는 진입일 7일 경과시 만기.
  - **SL**: 한 쪽 거래소 청산위험(equity ratio < 30%) 또는 자산 가격 ±20% 이동시 risk-off.
**데이터 소스**: Coinglass aggregate funding, 또는 CCXT 직접 폴링(무료).
**결합 필터**: 거래소 페어의 historical spread σ > 1.5 (안정성), withdrawal/deposit availability(자금 이동 가능 여부).
**실패 케이스 / 함정**: 한 거래소가 갑자기 거래/출금 정지(FTX, Mt.Gox 사례)시 leg 한 쪽이 잠긴다. counterparty risk가 PnL을 압도할 수 있음.
**출처**:
- https://www.gate.com/learn/articles/perpetual-contract-funding-rate-arbitrage/2166
- https://www.sciencedirect.com/science/article/pii/S2096720925000818
- https://arbitragescanner.io/funding-rates

### 1.3 Spot-Perp Cash & Carry Basis Trade
**개요**: Spot long + perp short(또는 dated futures short)로 delta-neutral 포지션을 구성, funding/basis 수확. ETF 도입 후 institutional flow가 가장 큰 시장-중립 carry trade. crypto 특유: funding이 8h마다 자동 결제되므로 구조적 carry 가능.
**시그널 정의**:
  - **Entry**: 30-day rolling avg funding rate > 0.02% (8h, ~22% APR) AND spot-perp basis > 0 AND 자금조달비용(스테이블코인 lending APR) < 8%.
  - 진입: BTC spot 1 BTC 매수, BTC-PERP 1 contract short, leverage 2~3x로 청산 buffer 확보.
  - **Exit**: funding 7-day MA가 0.005% 이하 회귀시 청산. APR 기준 리밸런싱 분기별.
  - **SL**: 한쪽 거래소 청산 위협(margin ratio < 25%)시 동시 청산.
**데이터 소스**: Coinglass funding history (무료), CME basis (https://www.cmegroup.com), CCXT spot+perp (무료).
**결합 필터**: 파생 OI/Spot volume ratio < 4 (과열 아님), 거래소 reserve 안정성(CQ exchange reserve).
**실패 케이스 / 함정**: 갑작스런 negative funding shock(2022 LUNA, FTX)시 perp 측이 양의 PnL을 내지만 spot leg가 깊이 떨어져도 청산되지 않으려면 충분한 collateral. 거래소 default = 100% 손실.
**출처**:
- https://www.bis.org/publ/work1087.pdf
- https://insights.deribit.com/education/cash-and-carry-trades/
- https://www.cmegroup.com/openmarkets/equity-index/2025/Spot-ETFs-Give-Rise-to-Crypto-Basis-Trading.html
- https://www.buildix.trade/blog/cash-and-carry-crypto-delta-neutral-funding-rate-strategy-2026

### 1.4 Open Interest + Price Divergence
**개요**: OI는 미결제약정(open contracts) 총량. Price와 OI의 4가지 조합이 시장 microstructure를 보여준다: ↑P+↑OI = 신규 long 진입(추세확인), ↑P+↓OI = short cover(약한 상승, 곧 약화), ↓P+↑OI = 신규 short 진입(추세확인), ↓P+↓OI = long 청산(약한 하락, 바닥 근접).
**시그널 정의**:
  - **Entry (Short)**: Price 신고가 갱신 BUT 24h aggregate OI(Coinglass) < 7-day OI peak × 0.95 → bearish divergence. 4H close < 직전 swing high 시 short.
  - **Entry (Long)**: Price 신저점 BUT OI < 7-day low (불 캐피츌레이션 종료 → 신규 short 진입 부재). reversal candle 후 long.
  - **Exit/SL**: 진입 ATR(14) × 2 손절. R-multiple 기반 1.5R 익절 또는 OI re-converge.
**데이터 소스**: Coinglass `/api/futures/openInterest/history` (무료), CCXT (무료).
**결합 필터**: CVD spot 방향성, funding rate 방향성, RSI(14) divergence.
**실패 케이스 / 함정**: aggregated OI는 거래소 간 합산이라 한 거래소가 데이터 lag을 일으키면 false signal. USDT-margined vs Coin-margined OI를 분리해서 봐야 한다(coin-margin은 가격에 따라 notional 변동).
**출처**:
- https://www.coinglass.com/learn/price-oi-and-cvd-en
- https://www.coinglass.com/pro/futures/OpenInterest
- https://www.coinglass.com/pro/futures/Cryptofutures

### 1.5 Liquidation Heatmap Magnet (Liquidity Sweep Targeting)
**개요**: 레버리지 포지션의 청산가는 leverage × entry price로 계산 가능. 특정 가격대에 청산 클러스터가 쌓이면 그곳이 가격을 끌어당기는 magnet 역할(MM/whale이 의도적으로 sweep). 크립토 특유: 모든 perp 포지션이 표준화 + 거래소 oracle price 공개 → heatmap 구축 가능.
**시그널 정의**:
  - **Entry (Long)**: 현재가 위 1~3% 구간에 long-liq cluster $50M+ (Hyblock magnitude high) AND 4H trend up AND funding flat. cluster 직전(0.5~1% 아래)에 long, target = cluster 통과 후 sweep 완료점.
  - **Entry (Short, sweep reversal)**: cluster를 wick으로 sweep한 candle close 후, candle body가 cluster 아래로 돌아오면 short. Sweep 자체를 stop hunt로 해석.
  - **Exit/SL**: liq cluster 방향 1.2× 진폭 익절. SL = swing high/low 너머.
**데이터 소스**: Hyblock Capital liquidation heatmap (유료 $49~), Coinglass Liquidation Heatmap (free + Pro), CoinAnk (free).
**결합 필터**: 현재 leverage ratio 극단(estimated leverage ratio CQ), funding < 0(short squeeze 가능성), volume spike on sweep candle.
**실패 케이스 / 함정**: heatmap은 추정치 — 실제 stop 분포와 다를 수 있음. 또한 강한 추세장에서는 sweep 후 그대로 추세 지속(reversal failure). 5분봉 같은 저TF에서 잡으면 노이즈가 많다.
**출처**:
- https://academy.hyblockcapital.com/tools/liquidation-levels-1
- https://www.coinglass.com/pro/futures/LiquidationHeatMap
- https://hyblockcapital.com/
- https://quadcode.com/blog/bitcoin-liquidation-heatmap-and-how-to-use-it-for-profitable-trading

### 1.6 Long/Short Ratio Extreme (Top Trader Accounts)
**개요**: Binance/Bybit는 "top trader long/short account ratio"와 "global accounts ratio"를 공개. retail(global)이 한쪽으로 쏠리면 contrarian, top traders가 한쪽으로 쏠리면 trend-follow 경향. 크립토 특유의 데이터(거래소 raw position 통계 공개).
**시그널 정의**:
  - **Entry (Short)**: Binance global accounts long ratio > 0.70 (즉 ratio > 2.33) for 12h AND top trader account ratio < global ratio (retail 과열, smart money 미동참) AND price 4H 하락 candle. short.
  - **Entry (Long)**: global long ratio < 0.40 (panic) AND top trader long ratio > global ratio. long.
  - **Exit/SL**: ratio가 0.50~0.55 회귀시 익절. ATR×2 SL.
**데이터 소스**: Binance `/futures/data/topLongShortAccountRatio` 및 `/globalLongShortAccountRatio` (무료), Coinglass aggregator (무료).
**결합 필터**: funding 방향, OI trend, price action(swing high/low).
**실패 케이스 / 함정**: small account가 ratio를 왜곡(account-based vs position-based 차이). top trader는 만들어진 정의 — 거래소가 정의 변경시 lookback 깨짐.
**출처**:
- https://www.coinglass.com/LongShortRatio
- https://www.gate.com/crypto-market-data/funds/long-short-ratio
- https://docs.amberdata.io/docs/longshort-ratio

### 1.7 CVD (Cumulative Volume Delta) Divergence
**개요**: CVD = Σ(시장가 매수 volume − 시장가 매도 volume). aggressor flow를 보여준다. price와 CVD가 어긋나면 hidden buying/selling 시그널. 크립토 특유: tick-by-tick aggressor side 데이터를 거래소가 공개(Binance trades stream).
**시그널 정의**:
  - **Entry (Long, bullish divergence)**: 1H에서 price 신저점 BUT spot CVD가 직전 swing low보다 high(매도 압력 약화). reversal candle 후 long.
  - **Entry (Short, bearish divergence)**: price 신고점 BUT CVD lower high. perp CVD 동시 약세(공격적 long 부재).
  - **Exit/SL**: divergence 해소(CVD가 price 방향과 다시 sync) 또는 1.5R 익절. SL = divergence 형성 swing 너머.
**데이터 소스**: Binance/Bybit trade stream (CCXT WebSocket, 무료), Coinglass Spot Taker CVD (무료), Hyblock Volume Delta (유료), Bookmap (유료 desktop).
**결합 필터**: spot CVD vs perp CVD 분리(spot이 leading 경향), large print 동반(absorption 가능성).
**실패 케이스 / 함정**: 거래소 한 곳의 CVD만 보면 cross-exchange flow 누락. 또한 sub-second wash trade가 CVD를 더럽힐 수 있음 → trade size 필터(>$1k) 권장.
**출처**:
- https://www.coinglass.com/learn/what-is-cumulative-volume-delta-cvd
- https://academy.hyblockcapital.com/indicators/orderflow-and-open-interest/volume-delta-cvd
- https://cryptoquant.com/asset/btc/chart/market-indicator/spot-taker-cvdcumulative-volume-delta-90-day
- https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy

### 1.8 Footprint Absorption / Exhaustion
**개요**: Footprint chart는 각 candle의 가격 레벨별 bid/ask volume을 보여준다. **Absorption** = 큰 aggressor flow가 들어왔지만 가격이 밀리지 않음(passive 반대편이 흡수, 반전 시그널). **Exhaustion** = 강한 추세 candle 끝에 volume이 마르며 momentum 소진. 크립토 특유: 24/7 + 거래소별 microstructure 차이가 footprint를 더 풍부하게 만든다.
**시그널 정의**:
  - **Entry (Long, absorption at support)**: 5m candle에서 specific price level에 sell market volume > 4× 평균이지만 lower wick 형성, close > 50% candle range. absorption confirmed → long.
  - **Entry (Short, exhaustion at resistance)**: 강한 상승 후 마지막 candle volume < 직전 3개 candle 평균 × 0.7, doji/shooting star + bearish delta. short.
  - **Exit/SL**: absorption candle low/high 너머 SL. R 1.5~2 익절 or POC(point of control) 회귀.
**데이터 소스**: Bookmap (유료), Cignals.io (유료), Buildix orderflow (유료/무료 mix), Tradingview footprint scripts (free).
**결합 필터**: HVN/LVN(volume profile high/low node), liquidation cluster 위치, CVD divergence 동시 발생.
**실패 케이스 / 함정**: 저유동성 알트는 footprint 노이즈가 많다. 또한 hidden iceberg orders는 footprint에 정확히 안 잡힘 — DOM(depth of market)과 결합 필요.
**출처**:
- https://bookmap.com/learning-center/en/supply-demand-setups/supply-demand-setups/absorption-exhaustion
- https://ninjatrader.com/futures/blogs/ninjatrader-order-flow/
- https://www.litefinance.org/blog/for-beginners/trading-strategies/order-flow-trading-with-footprint-charts/
- https://cignals.io/

### 1.9 Whale Wallet Tracking (Smart Money Entry)
**개요**: 온체인 transparency 덕에 large wallet의 입출금/포지션을 실시간 모니터링 가능. 특정 wallet이 지속적으로 outperform하면 follow trade 후보. 크립토 고유: 전통 시장에는 hedge fund 13F가 분기 lag지만 크립토는 분 단위.
**시그널 정의**:
  - **Entry (Long)**: Nansen "Smart Money" wallet ≥ 5개가 24h 내 같은 토큰을 1% 이상 portfolio에 추가 AND token mcap > $50M(노이즈 제거). 4H confirmation candle.
  - **Entry (Short)**: 동일 wallet들이 거래소로 입금 + Arkham KOL 매도 흐름. trend break 후 short.
  - **Exit/SL**: smart money exit 시그널(거래소 입금) 또는 -ATR×2 SL.
**데이터 소스**: Nansen (유료 $99~), Arkham (대부분 무료), Whale Alert (free + Pro), Lookonchain Twitter feed (무료).
**결합 필터**: token unlock schedule(공급 충격), 거래소 reserve 변화, 일치 wallet 수.
**실패 케이스 / 함정**: smart money가 hedging일 수 있음(spot buy + derivative short). wallet labeling 오류(Nansen mis-label). copy-trading은 후행 — entry price 차이로 alpha 소멸.
**출처**:
- https://www.nansen.ai/post/top-smart-money-indicators-in-crypto-how-to-identify-and-track-whale-activity
- https://intel.arkm.com/explorer/token/whale
- https://www.nansen.ai/post/how-to-monitor-wallet-activity-track-smart-money-in-crypto
- https://www.altrady.com/blog/cryptocurrency/track-crypto-whales-smart-money

### 1.10 Bart Pattern / Doom Candle Reversal
**개요**: Bart pattern은 sharp pump → flat consolidation(머리카락 모양) → sharp dump 형태. 저유동성 시간대(아시아/주말)에 MM이 stop을 sweep하는 전형 패턴. 크립토 특유의 24/7 + 박한 주말 깊이 때문.
**시그널 정의**:
  - **Entry (Counter-trade)**: 5분~1H에서 1ATR×3 이상의 단일 candle 발생 AND volume spike(20-period avg × 4+) AND 직후 30분 내 가격이 candle 시작점 근처로 회귀하면 reversal 확정.
  - 진입: Bart의 머리(top/bottom)가 형성된 후 머리에서 mid-zone 회귀시 반대 방향 진입.
  - **Exit/SL**: Bart 시작점 도달시 익절. SL = Bart 머리(extreme) 너머.
**데이터 소스**: CCXT trades + 1m OHLCV (무료), Coinglass volatility tool (무료).
**결합 필터**: low-liquidity hour 필터(UTC 02:00~06:00 또는 weekend), spot volume vs perp volume 비율(perp-driven sweep).
**실패 케이스 / 함정**: 진짜 뉴스 driven move를 Bart로 오인하면 반대로 풀린다. 패턴 인식이 후행 — 이미 mid-zone에 와서야 confirm 가능 → R 비대칭.
**출처**:
- https://cryptocurrencyfacts.com/2018/04/16/the-bart-crypto-pattern/
- https://www.coindesk.com/opinion/2023/08/09/what-is-bitcoins-bart-pattern-and-does-it-mean-btc-is-heading-towards-a-rally
- https://beincrypto.com/what-causes-the-infamous-bitcoin-bart-pattern/
- https://www.newsbtc.com/news/bitcoin-price-bart-simpson-chart-pattern/

### 1.11 Estimated Leverage Ratio Spike (CryptoQuant)
**개요**: ELR = Total OI / Exchange Reserve. 거래소가 보유한 BTC 대비 perp 미결제약정 비율. 높을수록 시장 leverage 과열, deleveraging 충격에 취약. 크립토 특유의 복합 지표.
**시그널 정의**:
  - **Entry (Short bias)**: BTC ELR > 0.30 (역사적 상위 10%) AND funding > 0.03% AND 4H 약세 candle 형성. short bias.
  - **Entry (Long bias)**: ELR < 0.18 (deleveraging 완료 신호). 4H 반등 candle.
  - **Exit/SL**: ELR mean reversion 또는 ATR×2 SL.
**데이터 소스**: CryptoQuant Pro (유료 $39~/월), 일부 free dashboard.
**결합 필터**: open interest absolute level, funding combo, exchange netflow.
**실패 케이스 / 함정**: ETF holdings 증가하면 reserve 정의가 흔들린다(custodian 분산). ELR 자체는 lagging — flush 직전에 spike 후에 release.
**출처**:
- https://cryptoquant.com/asset/btc/chart/exchange-flows
- https://academy.cryptoquant.com/metrics/exchange-in-outflow

### 1.12 Funding + OI Combo Regime Filter
**개요**: 단일 시그널보다 funding과 OI를 4-quadrant 조합으로 보면 regime을 구분 가능. 1) high funding + rising OI = leveraged long mania(top), 2) high funding + falling OI = late-stage uptrend(weakening), 3) low funding + rising OI = healthy accumulation, 4) negative funding + rising OI = bear positioning(bottom near).
**시그널 정의**:
  - **Regime 1 (caution short)**: BTC funding 7d MA > 0.04% AND OI 7d %Δ > +15%. directional system은 long entries 차단, short setup 우선.
  - **Regime 4 (caution long)**: funding 7d MA < -0.01% AND OI 7d %Δ > +10%. long bias filter on, short trades 차단.
**데이터 소스**: Coinglass aggregate (무료), CryptoQuant (mix).
**결합 필터**: 다른 모든 directional 전략의 master filter로 사용.
**실패 케이스 / 함정**: regime 전환 구간에서는 false readings. ETF flow shock(news driven)으로 OI가 급변하면 일시적 regime mismatch.
**출처**:
- https://www.coinglass.com/learn/price-oi-and-cvd-en
- https://www.coinglass.com/


---

## 2. On-chain / Fundamental

### 2.1 Exchange Netflow Reversal
**개요**: 거래소로의 BTC 입금량(inflow)은 매도 의도, 출금(outflow)은 self-custody 보유 의도로 해석. Netflow = inflow − outflow. 큰 음수(out > in)는 supply shock 시그널. 크립토 고유: 모든 거래소 hot/cold wallet이 publicly traceable.
**시그널 정의**:
  - **Entry (Long)**: BTC 7-day netflow < -30,000 BTC AND price 4H above EMA50. long.
  - **Entry (Short)**: 7-day netflow > +20,000 BTC (대형 매도 준비) AND funding > 0.02% AND price < EMA20. short.
  - **Exit**: netflow가 ±5,000 BTC 회귀시 익절. SL = swing 기반 ATR×2.5.
**데이터 소스**: CryptoQuant `/exchange-flows` (free tier, 7-day MA Pro), Glassnode `transactions/transfers_volume_to_exchanges_net` (Standard $29~).
**결합 필터**: stablecoin inflow 동시(매수 자금 대기), miner outflow, MVRV 위치.
**실패 케이스 / 함정**: 거래소 wallet labeling 오류(internal transfer를 inflow로 카운팅), 커스터디 이전(예: GBTC/ETF 전환)이 대규모 false flow. 분기/연말 회계 정리도 노이즈 유발.
**출처**:
- https://userguide.cryptoquant.com/cryptoquant-metrics/exchange/exchange-in-outflow-and-netflow
- https://cryptoquant.com/asset/btc/chart/exchange-flows/exchange-netflow-total
- https://academy.cryptoquant.com/metrics/exchange-in-outflow
- https://intercom.help/cryptoquant/en/articles/4990634-keywords-you-must-know-to-understand-on-chain-charts

### 2.2 Stablecoin Supply Expansion (Dry Powder)
**개요**: USDT/USDC 발행량은 fiat → crypto onramp의 proxy. 발행 급증 = 매수 자금 대기. 거래소 stablecoin reserve는 더 직접적 buy-pressure proxy. 크립토 특유 macro indicator.
**시그널 정의**:
  - **Entry (Long bias)**: USDT + USDC aggregate supply 14-day %Δ > +1.5% AND 거래소 stablecoin reserve 7d 상승. directional long bias 활성화 또는 daily long entry 가중치 1.3×.
  - **Entry (Short bias)**: 14-day %Δ < -0.5% (redemption) AND 거래소 reserve 감소. risk-off filter on.
**데이터 소스**: DefiLlama Stablecoins (https://defillama.com/stablecoins, 무료), CryptoQuant Stablecoin metrics (free + Pro), Glassnode Stablecoin Supply Ratio (Standard).
**결합 필터**: BTC dominance(자금이 BTC로 갈지 alt로 갈지), Fear & Greed.
**실패 케이스 / 함정**: USDT 발행은 종종 "예약(authorize)"만 되고 실제 시장 진입은 lag. Tron USDT 발행(아시아 OTC)이 즉시 매수로 이어지지 않을 수 있음. 규제 이벤트(BIS warning, USDC depeg)시 supply 변화는 매도 시그널이 될 수 있음.
**출처**:
- https://defillama.com/stablecoins
- https://www.coindesk.com/markets/2024/04/08/stablecoin-growth-is-more-important-cue-for-crypto-bull-market-than-bitcoin-etf-inflows-analyst
- https://www.coindesk.com/markets/2025/07/11/tethercircle-stablecoin-supply-growth-signals-strong-liquidity-backing-crypto-rally
- https://crystalintelligence.com/thought-leadership/usdt-maintains-dominance-while-usdc-faces-headwinds/

### 2.3 MVRV Z-Score Macro Cycle Indicator (BTC)
**개요**: MVRV = Market Cap / Realized Cap. Realized cap은 각 UTXO의 마지막 이동 가격을 합한 cost basis. Z-Score는 표준편차 단위로 정규화. > 7 = top zone, < 0 = bottom zone. 크립토 고유 — 전통 자산엔 cost basis aggregate가 없음.
**시그널 정의**:
  - **Entry (Long, accumulation)**: MVRV Z-Score < 0.5 AND 4-week 횡보. spot DCA 전략 활성화. 단기 매매 시스템은 long bias 가중치 1.5×.
  - **Entry (Short bias / de-risk)**: MVRV Z-Score > 5 (역사적 distribution zone). 단기 short setup 가중치 1.3×, long entries 사이즈 0.5×.
  - **Exit**: Z-Score 평균(2~3) 회귀.
**데이터 소스**: Glassnode `market.MvrvZScore` (Standard $29~), Bitcoin Magazine Pro (무료), LookIntoBitcoin (무료).
**결합 필터**: NUPL, Puell Multiple, 200WMA.
**실패 케이스 / 함정**: ETF/institutional cost basis가 realized cap 정의 변형. 2024~2025 cycle은 MVRV ceiling이 과거보다 낮을 수 있음(structural shift). 단기 매매에 직접 사용 부적합 — bias filter용.
**출처**:
- https://insights.glassnode.com/mastering-the-mvrv-ratio/
- https://www.bitcoinmagazinepro.com/charts/mvrv-zscore/
- https://docs.glassnode.com/guides-and-tutorials/metric-guides/mvrv/mvrv-ratio
- https://academy.glassnode.com/market/mvrv/mvrv-ratio

### 2.4 NUPL (Net Unrealized Profit/Loss) Sentiment Phases
**개요**: NUPL = (Market Cap − Realized Cap) / Market Cap. 시장 전체의 미실현 손익 비율. 5 phase: Capitulation(<0), Hope(0~0.25), Optimism(0.25~0.5), Belief(0.5~0.75), Euphoria(>0.75).
**시그널 정의**:
  - **Entry (Long)**: NUPL Capitulation phase 진입(< 0 cross) AND price 4H reversal candle. 분할 매수.
  - **Exit (Distribute)**: NUPL > 0.75(Euphoria) 진입시 spot exposure 단계적 감소.
**데이터 소스**: Glassnode `indicators.NetUnrealizedProfitLoss` (Standard), LookIntoBitcoin (무료), BMPro (무료).
**결합 필터**: STH-NUPL(short term holder NUPL, < 155일 보유) 분리해서 단기 매매 timing.
**실패 케이스 / 함정**: bull market 후반에는 Belief~Euphoria 사이를 수 개월 횡보 — entry signal로 단독 사용 불가.
**출처**:
- https://insights.glassnode.com/sth-lth-sopr-mvrv/
- https://academy.glassnode.com/market/mvrv/mvrv-ratio
- https://www.bitcoinmagazinepro.com/charts/relative-unrealized-profit--loss/

### 2.5 SOPR (Spent Output Profit Ratio) — Short Term Holder
**개요**: SOPR = 매도 가격 / 매수 가격(UTXO 기준). 1.0 cross가 핵심. STH-SOPR(< 155일 보유)이 1을 cross down하면 단기 보유자가 손실 매도 시작 = 단기 바닥 후보. cross up하면 회복 시작.
**시그널 정의**:
  - **Entry (Long)**: STH-SOPR < 0.97 (의미 있는 손절 매도) → 다음 봉이 STH-SOPR > 1 전환시 long.
  - **Entry (Short)**: STH-SOPR > 1.03 (단기 보유자 과열 익절) AND price 4H 약세. short.
  - **Exit/SL**: SOPR이 1.0 회귀시 익절. ATR×2 SL.
**데이터 소스**: Glassnode `indicators.SoprAdjusted`, `indicators.Sth*` (Standard/Pro), CryptoQuant.
**결합 필터**: aSOPR(adjusted), MVRV, exchange netflow.
**실패 케이스 / 함정**: 거래소 internal transfer가 SOPR을 흐림(Glassnode adjusted SOPR 사용 권장). intra-day 노이즈가 커서 1H 이하 매매에는 부적합.
**출처**:
- https://insights.glassnode.com/sth-lth-sopr-mvrv/
- https://docs.glassnode.com/basic-api/endpoints/indicators
- https://studio.glassnode.com/charts

### 2.6 Realized Price Trend Filter
**개요**: Realized Price = Realized Cap / Circulating Supply. 시장 평균 cost basis. price < realized price = aggregate 손실 상태(역사적 macro bottom zone).
**시그널 정의**:
  - **Long bias gate**: Spot price < Realized Price → directional system long bias 가중치 2×, short setups 비활성. Spot price > Realized Price × 2.5 → distribution bias.
**데이터 소스**: Glassnode `market.PriceRealizedUsd` (Standard), BMPro (무료).
**결합 필터**: 200WMA, MVRV, Puell Multiple.
**실패 케이스 / 함정**: realized price는 매우 매끄러운 lagging indicator — 단기 alpha 아님. bias gate로만 사용.
**출처**:
- https://www.bitcoinmagazinepro.com/charts/bitcoin-realized-price/
- https://docs.glassnode.com/guides-and-tutorials/metric-guides/mvrv/mvrv-ratio
- https://studio.glassnode.com/metrics?a=BTC&m=market.Mvrv

### 2.7 Puell Multiple — Miner Revenue Cycle (BTC only)
**개요**: Puell Multiple = (Daily issuance USD value) / (365-day MA of daily issuance USD value). David Puell 고안. 미너 수익의 historical norm 대비 비율. < 0.5 = 미너 capitulation zone(macro bottom), > 4 = miner profit euphoria(macro top).
**시그널 정의**:
  - **Entry (Long DCA)**: Puell Multiple < 0.5 → BTC spot DCA 시작. weekly 분할.
  - **Exit (de-risk)**: Puell Multiple > 4 → 단계적 매도.
**데이터 소스**: Glassnode `indicators.PuellMultiple` (Standard), BMPro (무료), LookIntoBitcoin (무료).
**결합 필터**: Hash Ribbon, MVRV Z-Score.
**실패 케이스 / 함정**: halving 후 issuance 50% 감소 → Puell baseline reset. ETF/대형 holder가 미너 매도 buffer 역할 → 신호 둔화 가능. Macro positioning 전용, 단기 매매 부적합.
**출처**:
- https://www.bitcoinmagazinepro.com/charts/puell-multiple/
- https://bitcoinmagazine.com/markets/what-is-the-bitcoin-puell-multiple-indicator-and-how-does-it-work
- https://coinmarketcap.com/academy/article/what-is-puell-multiple-in-crypto-and-how-to-use-it
- https://charts.bitbo.io/puell-multiple/

### 2.8 Hash Ribbon — Miner Capitulation Recovery (BTC only)
**개요**: Charles Edwards(Capriole) 고안. Hashrate 30D MA가 60D MA 아래로 cross = miner capitulation 시작, 다시 cross up = 회복 신호. 역사적으로 14번 buy signal 중 약 64% 수익.
**시그널 정의**:
  - **Entry (Long, swing)**: Hashrate 30D MA가 60D MA를 cross-up AND price 30D MA가 60D MA를 cross-up. spot/swing long.
  - **Exit**: 다음 capitulation 진입(30D < 60D crossover) 또는 +200% gain rule.
**데이터 소스**: Glassnode Hash Ribbon (https://studio.glassnode.com/charts/indicators.HashRibbon), TradingView Hash Ribbons by capriole_charles (free), BMPro (무료).
**결합 필터**: Puell Multiple < 1, MVRV Z-Score < 1.
**실패 케이스 / 함정**: 매우 저빈도 신호(연 1~2회). 짧은 capitulation은 거짓 신호 가능 — Edwards 자신도 "first signal"만 사용 권장. ASIC efficiency 변화로 hashrate 추세 자체가 구조 변화중.
**출처**:
- https://www.bitcoinmagazinepro.com/charts/hash-ribbons/
- https://studio.glassnode.com/charts/indicators.HashRibbon?a=BTC
- https://www.tradingview.com/script/kT7jIvqv-Hash-Ribbons/
- https://arbitragescanner.io/blog/hash-ribbons-indicator-complete-bitcoin-trading-guide

### 2.9 Active Addresses Network Growth Momentum
**개요**: 일별 활성 주소 수가 yearly average를 상회하면 network adoption expansion → demand 기반. 크립토 특유: 모든 트랜잭션이 publicly verifiable.
**시그널 정의**:
  - **Long bias gate**: BTC active addresses 30D MA > 365D MA (Glassnode "Active Address Momentum") AND new addresses 7D MA 양수 추세. directional long 가중치 1.2×.
  - **De-risk gate**: 30D MA가 365D MA 아래로 cross-down → long 사이즈 0.7×.
**데이터 소스**: Glassnode `addresses.ActiveCount`, `addresses.NewNonZeroCount` (Standard), CryptoQuant (mix).
**결합 필터**: transaction count, transfer volume USD, fee revenue.
**실패 케이스 / 함정**: L2/Lightning이 on-chain active count를 흐림. spam tx(Ordinals, Runes)로 inflated count. ETH는 contract address가 노이즈 — chain별 정의 필요.
**출처**:
- https://docs.glassnode.com/guides-and-tutorials/getting-started/use-case-tutorials/tutorial-2-introduction-to-on-chain-activity
- https://insights.glassnode.com/glassnode-supports-bnb-and-ton/
- https://studio.glassnode.com/charts/btc-active-address-momentum
- https://insights.glassnode.com/btc-market-pulse-week-41/

### 2.10 Miner Outflow Spike (Sell Pressure)
**개요**: 미너 wallet → 거래소 입금 = 매도 임박. 미너 reserve 감소가 공격적이면 bearish, 미너가 hodl이면 bullish.
**시그널 정의**:
  - **Entry (Short bias)**: Miner-to-Exchange flow 7-day MA가 30-day MA × 1.5 초과 AND price < EMA50. short bias on.
  - **Entry (Long bias, miner accumulation)**: Miner reserve 7-day net 양의 변화 AND price 횡보. accumulation 시그널.
**데이터 소스**: CryptoQuant `flow-indicator/miner-to-exchange-flow` (Pro), Glassnode `mining.MinersOutflowAdjustedSum` (Standard).
**결합 필터**: Puell Multiple, Hash Ribbon, Coinbase premium.
**실패 케이스 / 함정**: ETF custodian wallet과 미너 wallet 구분 모호. 미너가 OTC 매도하면 on-chain flow에 안 나타남 → 진정 매도 압력 누락.
**출처**:
- https://academy.cryptoquant.com/metrics/exchange-in-outflow
- https://cryptoquant.com/asset/btc/chart/miner-flows
- https://www.tradingview.com/news/newsbtc:2728b7779094b:0-bitcoin-miner-capitulation-ends-hash-ribbons-flash-buy-signal/

### 2.11 ETF Net Flow Tracker (Spot BTC/ETH ETF)
**개요**: 2024년 spot BTC ETF 승인 이후 institutional flow가 BTC price의 dominant driver. daily ETF net flow는 leading indicator. 크립토 고유 macro 변수.
**시그널 정의**:
  - **Long bias**: 5-day cumulative ETF net inflow > +$500M AND BTC price > 50DMA. long entries 가중치 1.4×.
  - **Short bias**: 5-day cumulative net outflow > -$300M AND BTC price < 50DMA. short bias on.
**데이터 소스**: SoSoValue (https://sosovalue.com/, 무료), Farside Investors (https://farside.co.uk/btc/, 무료), CoinGlass ETF flow.
**결합 필터**: spot premium(Coinbase), MVRV, BTC dominance.
**실패 케이스 / 함정**: weekend/holiday data 공백. CME futures basis arb과 연결된 flow는 directional이 아니라 carry — 순수 long bias로 해석 불가. GBTC redemption 같은 일회성 충격.
**출처**:
- https://farside.co.uk/btc/
- https://sosovalue.com/
- https://www.coinglass.com/


---

## 3. 시장 Microstructure / Sentiment

### 3.1 Crypto Fear & Greed Index Extreme Contrarian
**개요**: alternative.me Fear & Greed Index는 변동성, volume, social, dominance, surveys, momentum을 합성한 0~100 sentiment score. 0~10(Extreme Fear)에서 90일 평균 +48% 수익(역사적), 80~100(Extreme Greed)는 단기 reversal 빈번.
**시그널 정의**:
  - **Entry (Long bias / DCA)**: F&G < 15 for 3 consecutive days → spot DCA 활성, long entry 가중치 1.5×, short setups 비활성.
  - **Entry (Short bias / take profit)**: F&G > 85 for 3 days AND price 4H 약세 candle → short setup 가능, spot 분할 매도.
  - **Exit**: F&G 40~60(neutral) 회귀.
**데이터 소스**: https://alternative.me/crypto/fear-and-greed-index/ (무료, JSON API), CoinMarketCap own index (무료).
**결합 필터**: MVRV, RSI, BTC dominance(rotation 단계).
**실패 케이스 / 함정**: 강한 추세장에서 Extreme Fear/Greed가 수 주간 지속 → contrarian early entry시 large drawdown. Index 구성은 black-box, 가중치 변경 가능.
**출처**:
- https://alternative.me/crypto/fear-and-greed-index/
- https://coinmarketcap.com/charts/fear-and-greed-index/
- https://www.techi.com/bitcoin-fear-and-greed-index-extreme-fear-buying-signal/
- https://www.binance.com/en/square/fear-and-greed-index

### 3.2 Coinbase Premium Index
**개요**: (Coinbase BTC-USD price − Binance BTC-USDT price) / Binance price. 양의 premium = 미국 institutional 매수 dominance(특히 ETF), 음의 premium = 미국 매도/아시아 매수 우위. 크립토 특유의 region-flow proxy.
**시그널 정의**:
  - **Entry (Long)**: 1H Coinbase premium > +0.05% for 6+ hours AND price 4H bullish. long.
  - **Entry (Short)**: premium < -0.10% for 6+ hours (미국 매도 강) AND price 4H bearish.
  - **Exit/SL**: premium 중립(0±0.02%) 회귀 또는 ATR×2 SL.
**데이터 소스**: CryptoQuant Coinbase Premium Index (free 가능, Pro 자세), Coinglass 지원, 직접 계산은 CCXT(무료).
**결합 필터**: ETF flow data, BTC dominance, US session 시간 가중.
**실패 케이스 / 함정**: stablecoin 차이(USD vs USDT) 디페그시 premium false. Bitfinex/Korea premium처럼 region 별로 다양 — single source 의존 위험.
**출처**:
- https://cryptoquant.com/asset/btc/chart/market-data/coinbase-premium-index
- https://insights.glassnode.com/
- https://www.cnbc.com/2024/04/03/south-koreas-kimchi-premium-in-the-spotlight-after-btcs-record-highs.html

### 3.3 Korean (Kimchi) Premium
**개요**: (Upbit/Bithumb KRW price → USD 환산) − (Binance USDT price). 한국 시장은 capital control + retail-dominant → premium이 retail euphoria proxy. 5%+ premium은 역사적 cycle top 근접 시그널, 음수 premium은 panic.
**시그널 정의**:
  - **Caution short bias**: kimchi premium > +5% for 3+ days → BTC short setup 가중치 1.3×, long 사이즈 0.6×.
  - **Long bias**: kimchi premium < -2% (한국 매도 패닉) → counter long bias.
**데이터 소스**: CryptoQuant Korea Premium Index (free 가능), CoinGecko 직접 fetch(Upbit KRW × KRW/USD), Bithumb API + USD/KRW (모두 무료).
**결합 필터**: F&G, US session vs Asia session 비교, MVRV.
**실패 케이스 / 함정**: KRW capital control로 arb 불가능 — premium이 mean revert 안 함, 추세 추종 시그널이 됨. KRW 변동성도 premium 왜곡. 한국 거래소 maintenance시 false reading.
**출처**:
- https://www.coingecko.com/learn/kimchi-premium
- https://corporatefinanceinstitute.com/resources/cryptocurrency/kimchi-premium/
- https://cryptoslate.com/does-thes-kimchi-premium-still-front-run-btc/
- https://www.spotedcrypto.com/kimchi-premium-explained/

### 3.4 Bitcoin Dominance (BTC.D) Rotation
**개요**: BTC.D = BTC mcap / Total crypto mcap. BTC.D 상승 = BTC outperform, BTC.D 하락 = altcoin outperform("altseason"). 50~60% 영역에서 변곡 빈번.
**시그널 정의**:
  - **Altcoin entry signal**: BTC.D weekly close < 200WMA 또는 weekly close가 직전 swing low 이탈 AND BTC price > 50WMA(BTC도 상승 중) → ETH/SOL/major alt long bias on.
  - **BTC concentrated bias**: BTC.D weekly 상승 추세 + altcoin alt 약세 → portfolio BTC 비중 증가, alt entry 차단.
**데이터 소스**: TradingView CRYPTOCAP:BTC.D (무료), CoinGecko (무료), CoinMarketCap dominance chart (무료).
**결합 필터**: TOTAL2/TOTAL3 추세, ETH/BTC 비율, stablecoin dominance(USDT.D 하락은 alt buying 시그널).
**실패 케이스 / 함정**: stablecoin 발행이 BTC.D를 흐림(stablecoin도 비-BTC mcap에 포함). new altcoin listing이 Total mcap 점프 — BTC.D 변동이 가짜 rotation. 거래량 동반되지 않은 BTC.D 변동은 무시.
**출처**:
- https://www.tradingview.com/symbols/BTC.D/
- https://coinmarketcap.com/charts/bitcoin-dominance/
- https://www.coingecko.com/en/charts/bitcoin-dominance
- https://web3.gate.com/crypto-wiki/article/bitcoin-dominance-understanding-btc-d-and-market-cycles-20260103
- https://newhedge.io/bitcoin/bitcoin-dominance

### 3.5 TOTAL3 / OTHERS.D Small-Cap Risk Appetite
**개요**: TOTAL3 = total mcap excl. BTC + ETH. OTHERS.D = (Total mcap − top10) / Total mcap. 이들이 상승 = small-cap risk-on(투기 극단). 알트시즌 final phase indicator.
**시그널 정의**:
  - **Late altseason warning**: OTHERS.D weekly +20% 이상 상승 + TOTAL3 신고가 + BTC.D 신저점 → small-cap exposure 단계 축소(top 신호).
  - **Risk-on early**: TOTAL3 weekly close가 50WMA 위로 cross-up + ETH/BTC 상승 → mid-cap alt long bias.
**데이터 소스**: TradingView CRYPTOCAP:TOTAL3, CRYPTOCAP:OTHERS.D (무료).
**결합 필터**: BTC.D, USDT.D, F&G.
**실패 케이스 / 함정**: 신규 listing이 Total3 점프, 실제 자금 유입 부재. 메이저 alt(SOL, XRP) 자체 movement가 OTHERS.D 왜곡.
**출처**:
- https://mudrex.com/learn/altcoin-dominance-how-to-read/
- https://www.tradingview.com/symbols/CRYPTOCAP-TOTAL3/
- https://beincrypto.com/bitcoin-dominance-surge-altcoin-season/
- https://www.theblock.co/post/354125/bitcoin-dominance-slips-in-three-day-feedback-loop-raising-odds-of-short-term-altcoin-rotation

### 3.6 Bitcoin Halving Cycle Macro Position
**개요**: 매 210,000 블록(~4년) 마다 block reward 50% 감소. 2012, 2016, 2020, 2024 halving이 historical bull phase의 catalyst였음. 2024+ cycle은 ETF/institutional flow가 변형 요인.
**시그널 정의**:
  - **Pre-halving accumulation**: halving 6개월 전부터 BTC spot DCA scaling up.
  - **Post-halving bull bias**: halving 후 6~18개월간 long bias 가중치 1.5×, short setups 사이즈 0.5×.
  - **Cycle exit**: post-halving 18~24개월 + MVRV Z-Score > 5 + 200WMA × 5 도달시 단계적 매도.
**데이터 소스**: 블록 height 데이터 (CCXT, Mempool.space, BTCmagazinePro Halving countdown — 모두 무료).
**결합 필터**: M2 momentum, DXY, 실질금리, ETF flow, MVRV.
**실패 케이스 / 함정**: 2024 halving 이후 ETF 인입이 cycle pattern 변형. macro flatness/하락(연준 긴축)에선 halving tailwind 무력화. "4-year cycle dead" 시나리오.
**출처**:
- https://www.bydfi.com/en/cointalk/btc-halving-chart-guide
- https://www.bitcoinsuisse.com/learn/macro-dynamics-bitcoin-halving
- https://onrampbitcoin.com/research/bitcoins-macro-liquidity-cycle
- https://blockeden.xyz/blog/2026/02/06/bitcoin-four-year-cycle-dead-institutional-flows-etfs-sovereign-adoption/

### 3.7 CME Bitcoin Gap Fill Strategy
**개요**: CME BTC futures는 평일만 거래(2026년 5월 24/7 transition 예정). 주말 spot 변동이 월요일 open에 gap을 만든다. 역사적으로 gap fill 확률 ~77%(<$500 gap은 ~85%).
**시그널 정의**:
  - **Entry (Gap fill)**: CME BTC1! Friday close vs Sunday/Monday open price gap이 Friday close 대비 >0.5%, <3% AND gap 위/아래 즉시 인접 swing 구조 없음.
  - 진입: gap 방향으로 confirmation candle 후 진입(현재가 > 시작점이면 short, < 시작점이면 long), target = Friday close price(gap top/bottom).
  - **SL**: gap 너머 0.5×ATR.
  - **시간 손절**: 5거래일 미발현시 청산.
**데이터 소스**: TradingView CME:BTC1! (free), CME 직접(유료 institutional), CCXT BTC/USDT spot으로 proxy도 가능 (무료).
**결합 필터**: 주말 BTC volatility, OI 변화, ETF flow Friday close.
**실패 케이스 / 함정**: 큰 macro 이벤트 driven gap(예: ETF approval, Mt.Gox bankruptcy)는 fill 확률 낮음. CME가 24/7로 전환되면 전략 자체 폐기.
**출처**:
- https://whaleportal.com/blog/bitcoin-cme-gaps-and-cme-trading-strategy-explained/
- https://phemex.com/academy/cme-futures-gap
- https://www.bitget.com/academy/cme-bitcoin-gap
- https://coinmarketcap.com/academy/article/what-are-bitcoin-cme-gaps-and-how-to-trade-them
- https://coinswitch.co/switch/crypto/bitcoin-cme/

### 3.8 Weekend Volatility Pattern (Low-Liquidity Hours)
**개요**: 토/일은 institutional bid 부재 + retail/MM dominance로 thin orderbook. 변동성 spike + Bart pattern + stop hunt 빈발. 크립토 24/7 특유 패턴.
**시그널 정의**:
  - **Volatility filter**: 주말(UTC Sat 00:00 ~ Sun 23:59) 동안 maker-only 모드 또는 사이즈 0.5×, taker entry 차단.
  - **Mean-reversion entry**: 주말 1H candle ATR×3 이상 spike + 직후 30분 동안 60% 회귀시 reversal entry. (Bart 1.10과 결합)
  - **Exit**: Monday UTC 13:00(US session open) 도달시 잔여 포지션 청산.
**데이터 소스**: CCXT OHLCV (무료), Coinglass volatility (무료).
**결합 필터**: aggregate OI 7d 변화, funding flat 여부, BTC.D 안정.
**실패 케이스 / 함정**: 주말에도 macro 뉴스(중동, 중국 규제) 발생 → 추세 driven 큰 candle은 mean revert 안 함. ETF inflow/outflow data가 주말에 없어 후행적 fill.
**출처**:
- https://www.coindesk.com/opinion/2023/08/09/what-is-bitcoins-bart-pattern-and-does-it-mean-btc-is-heading-towards-a-rally
- https://beincrypto.com/what-causes-the-infamous-bitcoin-bart-pattern/

### 3.9 Stablecoin Dominance (USDT.D) Inverse Signal
**개요**: USDT.D = USDT mcap / Total crypto mcap. 상승 = 자금이 stablecoin으로 retreat(risk-off), 하락 = stablecoin이 risk asset으로 deploy(risk-on). 인버스 BTC 가격과 강한 상관.
**시그널 정의**:
  - **Long bias**: USDT.D weekly close가 50WMA 아래로 cross-down → BTC/alt long bias on.
  - **Risk-off**: USDT.D weekly higher high + BTC weekly lower low → 단기 short setup 또는 cash 보유.
**데이터 소스**: TradingView CRYPTOCAP:USDT.D (무료), DefiLlama (무료).
**결합 필터**: BTC.D, TOTAL3, ETF flow.
**실패 케이스 / 함정**: 신규 stablecoin(USDS, FDUSD, PYUSD) 발행이 USDT.D를 인위적으로 압박 — 정확히는 total stablecoin dominance(SC.D)로 모니터링 권장.
**출처**:
- https://defillama.com/stablecoins
- https://www.tradingview.com/symbols/CRYPTOCAP-USDT.D/

### 3.10 Open Interest USD-Margined vs Coin-Margined Split
**개요**: USDT-margined OI는 stablecoin 마진(notional이 가격과 무관). Coin-margined OI는 BTC 마진(notional이 BTC 가격에 비례, 하락시 자동 deleveraging). Coin-margined OI 상승은 약세장 reflexive risk.
**시그널 정의**:
  - **Caution short setup**: Coin-margined BTC OI 7d %Δ > +20% AND price 4H bearish reversal candle → short setup 신뢰도 가중.
  - **Bottom fish bias**: Coin-margined OI flush(7d %Δ < -25%) AND price reversal candle → long entry 가중치 1.3×.
**데이터 소스**: Coinglass (https://www.coinglass.com/pro/futures/OpenInterest, 무료), CCXT (무료).
**결합 필터**: funding 방향, liquidation cluster.
**실패 케이스 / 함정**: USDC/BUSD/FDUSD margined도 분리 — single token 충격(USDC depeg) 영향. Inverse contract decommission(예: Binance 일부 quanto 만기)으로 OI structural shift.
**출처**:
- https://www.coinglass.com/pro/futures/OpenInterest
- https://www.coinglass.com/learn/price-oi-and-cvd-en

### 3.11 Options Skew / Put-Call Ratio (Deribit)
**개요**: Deribit options skew = OTM put IV − OTM call IV. 양의 skew = put 수요 우위(hedging fear), 음의 skew = call 수요(상승 베팅). put/call 비율도 sentiment proxy.
**시그널 정의**:
  - **Contrarian long**: 25-delta skew > +5% (강한 put bid, panic) AND price 4H reversal candle → long bias.
  - **Caution short**: 25-delta skew < -3% (call mania) AND price 4H bearish + funding 양수 → short bias.
**데이터 소스**: Deribit Insights (무료), Block Scholes / Genesis Volatility (유료), Coinglass options page (free + Pro).
**결합 필터**: funding, OI, ATM IV term structure.
**실패 케이스 / 함정**: options market은 BTC/ETH only(major). short-dated skew는 단기 sentiment shock(이벤트 일정) 반영 — directional alpha 아닐 수 있음.
**출처**:
- https://insights.deribit.com/
- https://www.coinglass.com/pro/options/OIStrike
- https://www.coinglass.com/pro/options/OpenInterest

### 3.12 GBTC / ETF Discount/Premium (NAV proxy)
**개요**: 과거 GBTC trust premium/discount는 institutional sentiment 척도. 현재는 spot ETF에서는 작아졌지만 여전히 일별 net flow와 short-term price 사이 lead/lag 존재.
**시그널 정의**:
  - **Long bias**: BlackRock IBIT 5-day premium consistently > +0.10% AND aggregate ETF inflow > $300M/day. long bias on.
  - **Short bias**: persistent discount > -0.20% AND outflow days. short bias.
**데이터 소스**: Farside (무료), SoSoValue (무료), Bloomberg (유료).
**결합 필터**: spot Coinbase premium, BTC.D.
**실패 케이스 / 함정**: ETF mechanism이 in-kind / cash creation 차이로 premium 자체가 거의 없음(수렴). GBTC 시절 premium은 unique한 historical artifact — 현재는 weak signal.
**출처**:
- https://farside.co.uk/btc/
- https://sosovalue.com/


---

## 4. 추가 크립토-네이티브 패턴

### 4.1 Liquidation Cascade Tape Reading
**개요**: 청산이 연쇄적으로 발생하는 "cascade" 이벤트는 crypto perp 특유. Coinglass total liquidation USD가 1H에 $100M+ spike하면 leverage flush 완료 시그널.
**시그널 정의**:
  - **Entry (Long, post-liq)**: 1H total liquidation USD > $200M (long 청산 dominant) AND funding flat/negative AND 직전 1H candle high-volume reversal → long.
  - 진입: cascade 종료 candle close 후, 다음 candle entry, target = pre-flush price level.
  - **SL**: cascade low 너머 1×ATR.
**데이터 소스**: Coinglass `/api/futures/liquidation/v2` (무료), TradingView CryptoCap liquidation widget.
**결합 필터**: funding 변화 (flush 후 funding이 negative 전환), OI 급감, exchange netflow.
**실패 케이스 / 함정**: news driven cascade(거래소 default)는 회복 안 함. cross-margin cascade는 alt에 더 큰 충격 — major(BTC, ETH)에서만 신뢰.
**출처**:
- https://www.coinglass.com/LiquidationData
- https://www.coinglass.com/pro/futures/LiquidationHeatMap

### 4.2 Top Trader Position Ratio Divergence (Smart vs Dumb Money)
**개요**: Binance "top trader position ratio"(상위 PnL 트레이더의 long/short)와 "global account ratio"(전체 retail) 간 divergence가 핵심 signal. 둘이 같은 방향이면 추세 추종, 반대면 contrarian.
**시그널 정의**:
  - **Smart-money long**: top trader long ratio > 0.55 AND global long ratio < 0.45 (smart는 long, retail은 short) → long.
  - **Smart-money short**: top trader long ratio < 0.45 AND global > 0.55 → short.
  - **Exit**: ratio convergence 또는 R 1.5 익절.
**데이터 소스**: Binance `/futures/data/topLongShortPositionRatio`, `/topLongShortAccountRatio`, `/globalLongShortAccountRatio` (무료).
**결합 필터**: funding, price action confirmation.
**실패 케이스 / 함정**: "top trader" 정의가 거래소별로 다름. position ratio vs account ratio 구분 모호 — 동일 trader 다중 account 사용.
**출처**:
- https://www.binance.com/en/square/post/33205648801961
- https://docs.amberdata.io/docs/longshort-ratio
- https://www.coinglass.com/LongShortRatio

### 4.3 Realized Cap HODL Waves (Long-Term Holder Behavior)
**개요**: HODL Waves는 UTXO age 분포. 1Y+ supply 비중 증가 = 장기 holder accumulation, 감소 = distribution. 사이클 phase 식별.
**시그널 정의**:
  - **Long bias gate**: 1Y+ supply 비중 monthly +0.5%p 이상 증가 추세 AND price 횡보 → long bias 가중치.
  - **Distribution warning**: 1Y+ supply 감소 + STH cost basis 상승 → late-cycle warning.
**데이터 소스**: Glassnode `supply.HodlWaves`, BMPro (무료), LookIntoBitcoin.
**결합 필터**: STH/LTH SOPR, MVRV.
**실패 케이스 / 함정**: ETF 보유분이 wave 정의를 흐림(custodian wallet age는 LTH로 분류되지만 redemption시 즉시 sell). slow indicator — macro filter 전용.
**출처**:
- https://insights.glassnode.com/sth-lth-sopr-mvrv/
- https://www.bitcoinmagazinepro.com/charts/hodl-waves/

### 4.4 Open Interest 1H Spike + Price Stagnation
**개요**: 1시간 내 OI가 급격히 증가하지만 price가 거의 변동 없음 = 큰 player 양방향 진입(squeeze setup). 직후 한쪽 청산 cascade 가능성.
**시그널 정의**:
  - **Setup detection**: 1H OI %Δ > +5% AND price 1H 변동폭 < 0.3% → "compressed energy" 상태. 즉시 진입 X, breakout 후 진입.
  - **Entry**: 다음 candle ATR×1.5 이상 단방향 close → 추세 방향 진입(추세 추종).
  - **Exit**: 1.5R 익절, candle close 반대로 SL.
**데이터 소스**: Coinglass real-time OI API (무료), CCXT (무료).
**결합 필터**: 향후 economic event calendar(FOMC, CPI 직전 squeeze 빈번).
**실패 케이스 / 함정**: macroevent 직전에는 양방향 hedge가 OI를 키움 — break direction이 fundamental driven, technical 시그널 무효.
**출처**:
- https://www.coinglass.com/pro/futures/OpenInterest
- https://www.coinglass.com/learn/price-oi-and-cvd-en

### 4.5 Spot Volume vs Perp Volume Ratio
**개요**: spot volume / perp volume이 낮으면 leverage 우세(pure speculation), 높으면 organic spot demand. 추세 지속력 척도.
**시그널 정의**:
  - **Sustainable trend filter**: 7-day spot/perp volume ratio > 0.20 AND price uptrend → 추세 신뢰도 가중치 1.3×.
  - **Speculative warning**: ratio < 0.10 AND uptrend → 추세 약함, R 축소.
**데이터 소스**: Coinglass(무료), CCXT spot+perp volume(무료).
**결합 필터**: funding rate level, OI trend.
**실패 케이스 / 함정**: wash trade가 perp volume 부풀림 — Coinglass adjusted volume 사용 권장. ETF spot bid는 거래소 외에서 일어나서 ratio에 누락.
**출처**:
- https://www.coinglass.com/learn/price-oi-and-cvd-en
- https://www.coinglass.com/

### 4.6 Aggregated Spot Inflow Rejection (Buy the Dip Identification)
**개요**: 거래소 BTC spot inflow가 특정 임계 초과(panic deposit) 후 가격이 반등하지 못하면 진정 매도; 반등하면 panic flush 종료 시그널.
**시그널 정의**:
  - **Entry (Long)**: 1H spot exchange inflow > 5,000 BTC (95th percentile) AND 직후 4H candle reversal(close > 50% range) → long.
  - **Exit/SL**: 직전 swing low 너머 SL, 1.5~2R 익절.
**데이터 소스**: CryptoQuant exchange inflow (Pro/free), Glassnode.
**결합 필터**: funding negative 전환, F&G < 20.
**실패 케이스 / 함정**: 거래소 wallet shuffling이 가짜 inflow spike 생성. ETF rebalancing day(분기말)이 노이즈.
**출처**:
- https://userguide.cryptoquant.com/cryptoquant-metrics/exchange/exchange-in-outflow-and-netflow
- https://academy.cryptoquant.com/metrics/exchange-in-outflow

### 4.7 Funding Reset After Cascade
**개요**: long-cascade liquidation 후 funding이 빠르게 negative 또는 0 근처로 수렴 = positioning reset 완료. 다음 leg up 전초.
**시그널 정의**:
  - **Entry (Long)**: 24h 내 long liquidation > $300M AND funding이 reset 후 -0.005% ~ +0.005% range 12h 유지 AND 4H reversal candle → long.
  - **Exit**: funding 양의 영역 복귀 + 1.5R 익절.
**데이터 소스**: Coinglass funding history + liquidation API (무료).
**결합 필터**: OI flush 확인, CVD spot 매수 우위.
**실패 케이스 / 함정**: 추세 하락 중 reset이 여러 번 반복 — 한 번에 진입 X, 반등 confirmation 필수.
**출처**:
- https://www.coinglass.com/LiquidationData
- https://blog.amberdata.io/the-ultimate-guide-to-funding-rate-arbitrage-amberdata

### 4.8 Stablecoin Exchange Reserve Build-Up
**개요**: 거래소 stablecoin reserve가 증가 = 매수 자금 대기. 직전에 stablecoin이 대량 유입되면 다음 BTC up leg 가능성 상승.
**시그널 정의**:
  - **Long bias on**: 거래소 USDT+USDC reserve 7-day 증가 > +$1B AND BTC reserve 동시 감소 → long bias 가중치 1.4×.
**데이터 소스**: CryptoQuant Stablecoins to Exchange flow (free + Pro).
**결합 필터**: BTC exchange netflow(반대 방향), F&G, MVRV.
**실패 케이스 / 함정**: stablecoin 발행 분 자체가 거래소 reserve로 first land — 실제 매수 의도 없을 수 있음. Tether OTC 운용 inflow는 매도용일 수도 있음.
**출처**:
- https://academy.cryptoquant.com/metrics/exchange-in-outflow
- https://intercom.help/cryptoquant/en/articles/4990634-keywords-you-must-know-to-understand-on-chain-charts

### 4.9 Aggregate Open Interest All-Time-High Warning
**개요**: 글로벌 BTC perp OI가 ATH를 갱신할 때 leverage 시스템 위험 극단 → 큰 deleveraging 임박. ETF 시대에는 절대치보다 OI/MarketCap ratio가 더 의미.
**시그널 정의**:
  - **Risk-off filter**: aggregate BTC OI / mcap ratio가 90일 percentile 95th 초과 → 신규 long entry 사이즈 0.5×, 신규 short bias 1.3×.
**데이터 소스**: Coinglass aggregate OI (무료), CryptoQuant.
**결합 필터**: funding, ELR, leverage.
**실패 케이스 / 함정**: ratio 정규화가 ETF 도입으로 mcap이 sticky하게 커진 환경에서 신호 둔화. 단순 ATH보다 distribution-based threshold(percentile) 권장.
**출처**:
- https://www.coinglass.com/pro/futures/OpenInterest
- https://www.coinglass.com/learn/price-oi-and-cvd-en

### 4.10 ETH/BTC Ratio Rotation
**개요**: ETH/BTC ratio는 알트시즌 leading indicator. ETH가 BTC를 outperform하기 시작하면 자금이 BTC → ETH → 알트 순으로 rotate.
**시그널 정의**:
  - **Alt rotation start**: ETH/BTC weekly close가 50WMA 위로 cross-up + 6주 trendline break → ETH 및 large-cap alt long bias.
  - **BTC season gate**: ETH/BTC 신저점 + BTC.D 상승 → BTC concentrated bias.
**데이터 소스**: TradingView ETHBTC (무료), Binance ETH/BTC (무료).
**결합 필터**: BTC.D, TOTAL2, USDT.D.
**실패 케이스 / 함정**: ETH 자체 catalyst(ETF, upgrade)에 의한 ratio 상승은 알트시즌 시작 아님 — broad rotation은 SOL, AVAX 등 동시 outperform 확인 필요.
**출처**:
- https://www.coingecko.com/en/charts/bitcoin-dominance
- https://mudrex.com/learn/altcoin-dominance-how-to-read/

### 4.11 Realized Volatility Regime Change
**개요**: BTC RV(realized volatility) 30D는 cycle phase별 다른 분포. RV < 30%(annualized) = compression, RV > 80% = euphoria/panic. 현재는 ETF 효과로 RV 구조적 하락 중.
**시그널 정의**:
  - **Volatility breakout setup**: RV 30D < 25th percentile of last 365d → 다음 directional break candle ATR×2 위에 stop entry order(양방향).
  - **Trend exhaust filter**: RV 30D > 90th percentile → 새 추세 진입 금지, mean-reversion 시스템만 활성.
**데이터 소스**: Deribit DVOL (https://www.deribit.com/, free), Glassnode `market.RealizedVolatility` (Standard).
**결합 필터**: ATM IV term structure, OI 변화.
**실패 케이스 / 함정**: vol cluster effect로 low-vol regime이 수 개월 지속 — breakout signal이 매우 적음. ETF 환경에서 historical RV 분포가 shift, percentile 정의 갱신 필요.
**출처**:
- https://insights.deribit.com/
- https://studio.glassnode.com/metrics?a=BTC&m=market.RealizedVolatility

### 4.12 Spot Taker Buy/Sell Volume Ratio (CryptoQuant)
**개요**: Spot taker buy / taker sell volume ratio는 aggressor flow의 spot 한정 버전. perp CVD와 함께 보면 spot organic buying인지 leverage driven인지 구분.
**시그널 정의**:
  - **Long confirmation**: spot taker buy/sell ratio 1H > 1.20 AND price 4H uptrend AND perp funding moderate → trend continuation long.
  - **Trend warning**: spot ratio < 0.85 AND price 4H uptrend(spot 매도 불구 perp이 가격 sustain) → 단기 reversal warning.
**데이터 소스**: CryptoQuant `market-indicator/taker-buy-sell-ratio` (Pro), Coinglass.
**결합 필터**: perp CVD, OI 변화, funding.
**실패 케이스 / 함정**: 거래소별 spot volume 정의 다름(market order vs aggregator). Coinbase spot은 institutional이 dominant — separate해서 분석 권장.
**출처**:
- https://cryptoquant.com/asset/btc/chart/market-indicator/spot-taker-cvdcumulative-volume-delta-90-day
- https://www.coinglass.com/learn/what-is-cumulative-volume-delta-cvd

---

## 5. 시그널 결합 매트릭스 (Composite Filters)

각 단일 시그널은 noise가 많아 production에서는 combo로 사용한다. 권장 composite:

### 5.1 "Crowded Long Top" Composite
- funding 7d MA > 0.04% 8h
- aggregate OI 7d %Δ > +15%
- top global long ratio > 0.65
- F&G > 75
- 4 중 3개 이상 충족시 → short bias 활성, 신규 long entry 차단.

### 5.2 "Macro Bottom" Composite
- MVRV Z-Score < 1
- Puell Multiple < 0.6
- 200WMA 부근 또는 아래
- F&G < 20 for 7+ days
- 거래소 netflow 7d 음수
- 5 중 4개 이상 → spot DCA scale-up, swing long 가중치 2×.

### 5.3 "Altseason Trigger" Composite
- BTC.D weekly close < 200WMA
- ETH/BTC weekly close > 50WMA cross up
- USDT.D weekly close < 50WMA cross down
- TOTAL3 weekly higher high
- 4 중 3개 이상 → alt long bias, BTC concentrated bias 해제.

### 5.4 "Squeeze Imminent" Composite
- 1H OI %Δ > +5% with price stagnation (< 0.3% range)
- aggregate liquidation cluster within 2% of price
- funding > 0.03% 또는 < -0.02% (extreme)
- 3개 충족시 → 양방향 stop entry order, breakout direction follow.

---

## 6. 데이터 소스 요약

### Free / Open
- Coinglass (대부분 free): funding, OI, liquidation heatmap, long/short ratio
- alternative.me Fear & Greed
- DefiLlama Stablecoins
- Farside ETF flows
- SoSoValue ETF flows
- Bitcoin Magazine Pro charts (Puell, MVRV-Z, Hash Ribbon, HODL Waves)
- LookIntoBitcoin
- TradingView CRYPTOCAP indices (BTC.D, TOTAL2, TOTAL3, OTHERS.D, USDT.D)
- 거래소 API (Binance, Bybit, Coinbase) via CCXT
- mempool.space (블록 정보)
- Whale Alert (basic Twitter/web)
- Arkham Intelligence (대부분 free)
- Lookonchain (Twitter feed, free)

### Paid / Subscription
- CryptoQuant Pro $39+/월 — exchange flows, ELR, miner flows, premium
- Glassnode Standard $29+, Pro/Advanced more — on-chain core metrics
- Hyblock Capital $49+/월 — liquidation heatmap precision, orderflow
- Nansen $99+/월 — smart money labeling, wallet analytics
- Bookmap (desktop, $99+/월) — footprint, DOM heatmap
- Cignals.io (subscription) — orderflow charts
- Deribit Insights / Block Scholes / Genesis Volatility — options analytics

---

## 7. 자동화 시그널 생성을 위한 구현 노트

1. **Polling vs WebSocket**: funding/OI는 1분 또는 5분 polling 충분. CVD/footprint은 trade WebSocket 필수.
2. **Aggregation**: 단일 거래소 의존 X. 최소 3개 거래소(Binance, Bybit, OKX) aggregate 권장.
3. **Outlier filtering**: trade size < $1k 노이즈 제거(wash trade 영향).
4. **Lookback periods**: short-term(1H) 시그널은 24~72h lookback, macro(MVRV, Puell)는 4년+ lookback.
5. **Regime detection**: F&G, MVRV, BTC.D를 master regime variable로 사용 → directional system이 regime별 다른 룰 적용.
6. **Backtest 주의**: on-chain metric의 historical revision 빈번(Glassnode/CryptoQuant 정의 변경) → as-of-date snapshot 보존.
7. **Latency budget**: liquidation cascade, sweep 같은 microstructure 시그널은 sub-second latency. macro/cycle 시그널은 daily refresh로 충분.
8. **Composite scoring**: 각 시그널 binary on/off 대신 z-score 기반 weighted sum → R 사이즈 동적 조정.

---
