"""Pre-Claude market-condition filters for prompt strategies."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.models import OHLCV
from src.strategy.base import BaseStrategy


@dataclass(frozen=True)
class PromptTriggerDecision:
    """Decision returned before a prompt strategy may call Claude."""

    allowed: bool
    reason: str


def should_run_prompt_strategy(
    strategy: BaseStrategy,
    primary_ohlcv: list[OHLCV],
    *,
    ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
    current_price: Decimal | None = None,
) -> PromptTriggerDecision:
    """Evaluate a prompt strategy's pre-Claude trigger."""
    if strategy.info.technique_type != "prompt":
        return PromptTriggerDecision(True, "not_prompt_strategy")

    trigger = strategy.info.prompt_trigger
    if trigger == "none":
        return PromptTriggerDecision(True, "no_prompt_trigger")

    if trigger in {"ict_smc_setup", "ict_smc_context"}:
        return _ict_smc_context(
            primary_ohlcv,
            ohlcv_by_timeframe=ohlcv_by_timeframe,
            current_price=current_price,
        )

    if trigger == "trend_context":
        return _trend_context(primary_ohlcv)

    return PromptTriggerDecision(False, f"unknown_prompt_trigger:{trigger}")


def _ict_smc_context(
    primary_ohlcv: list[OHLCV],
    *,
    ohlcv_by_timeframe: dict[str, list[OHLCV]] | None,
    current_price: Decimal | None,
) -> PromptTriggerDecision:
    """Broad ICT/SMC context filter before spending Claude tokens."""
    frames = _ordered_frames(primary_ohlcv, ohlcv_by_timeframe)
    price = current_price if current_price is not None else primary_ohlcv[-1].close

    for label, candles in frames:
        if _has_liquidity_sweep(candles) or _had_recent_liquidity_sweep(candles):
            return PromptTriggerDecision(True, f"{label}:liquidity_sweep")
        if _near_recent_order_block(candles, price, tolerance_bps=Decimal("100")):
            return PromptTriggerDecision(True, f"{label}:order_block_revisit")
        if _near_recent_fvg(candles, price, tolerance_bps=Decimal("100")):
            return PromptTriggerDecision(True, f"{label}:fvg_revisit")
        if _near_recent_swing_extreme(candles, price, tolerance_bps=Decimal("75")):
            return PromptTriggerDecision(True, f"{label}:swing_liquidity_nearby")
        if _near_range_boundary(candles, price, tolerance_bps=Decimal("100")):
            return PromptTriggerDecision(True, f"{label}:range_boundary")

    return PromptTriggerDecision(False, "ict_smc_context_not_present")


def _trend_context(primary_ohlcv: list[OHLCV]) -> PromptTriggerDecision:
    """Broad trigger for simple trend/support-resistance prompts."""
    candles = primary_ohlcv
    if _has_directional_move(candles):
        return PromptTriggerDecision(True, "directional_move")
    if _near_recent_swing_extreme(
        candles, candles[-1].close, tolerance_bps=Decimal("75")
    ):
        return PromptTriggerDecision(True, "support_resistance_nearby")
    if _volume_expanded(candles):
        return PromptTriggerDecision(True, "volume_expansion")
    if _range_expanded(candles):
        return PromptTriggerDecision(True, "range_expansion")
    return PromptTriggerDecision(False, "trend_context_not_present")


def _ordered_frames(
    primary_ohlcv: list[OHLCV],
    ohlcv_by_timeframe: dict[str, list[OHLCV]] | None,
) -> list[tuple[str, list[OHLCV]]]:
    if not ohlcv_by_timeframe:
        return [("primary", primary_ohlcv)]

    preferred = ["5m", "15m", "1h", "4h", "1d"]
    ordered: list[tuple[str, list[OHLCV]]] = []
    for tf in preferred:
        candles = ohlcv_by_timeframe.get(tf)
        if candles:
            ordered.append((tf, candles))
    for tf, candles in ohlcv_by_timeframe.items():
        if tf not in preferred and candles:
            ordered.append((tf, candles))
    return ordered or [("primary", primary_ohlcv)]


def _has_liquidity_sweep(candles: list[OHLCV], lookback: int = 20) -> bool:
    if len(candles) < 4:
        return False

    latest = candles[-1]
    prior = candles[-(lookback + 1) : -1]
    if not prior:
        return False

    prior_high = max(c.high for c in prior)
    prior_low = min(c.low for c in prior)
    swept_high_rejected = latest.high > prior_high and latest.close < prior_high
    swept_low_rejected = latest.low < prior_low and latest.close > prior_low
    return swept_high_rejected or swept_low_rejected


def _had_recent_liquidity_sweep(candles: list[OHLCV], recent_bars: int = 5) -> bool:
    if len(candles) < recent_bars + 4:
        return False
    for offset in range(1, min(recent_bars, len(candles) - 3) + 1):
        window = candles[: len(candles) - offset + 1]
        if _has_liquidity_sweep(window):
            return True
    return False


def _near_recent_order_block(
    candles: list[OHLCV],
    price: Decimal,
    *,
    lookback: int = 30,
    tolerance_bps: Decimal = Decimal("30"),
) -> bool:
    if len(candles) < 3:
        return False

    recent = candles[-lookback:]
    avg_body = _average_body(recent)
    if avg_body <= 0:
        return False

    for idx in range(len(recent) - 2, 0, -1):
        candidate = recent[idx - 1]
        impulse = recent[idx]
        impulse_body = abs(impulse.close - impulse.open)
        if impulse_body < avg_body * Decimal("1.5"):
            continue

        bullish_ob = candidate.close < candidate.open and impulse.close > impulse.open
        bearish_ob = candidate.close > candidate.open and impulse.close < impulse.open
        if not bullish_ob and not bearish_ob:
            continue

        zone_low = min(candidate.open, candidate.close)
        zone_high = max(candidate.open, candidate.close)
        if _price_near_zone(price, zone_low, zone_high, tolerance_bps):
            return True
    return False


def _near_recent_fvg(
    candles: list[OHLCV],
    price: Decimal,
    *,
    lookback: int = 30,
    tolerance_bps: Decimal = Decimal("30"),
) -> bool:
    if len(candles) < 3:
        return False

    recent = candles[-lookback:]
    for idx in range(2, len(recent)):
        left = recent[idx - 2]
        right = recent[idx]
        if left.high < right.low:
            if _price_near_zone(price, left.high, right.low, tolerance_bps):
                return True
        if left.low > right.high:
            if _price_near_zone(price, right.high, left.low, tolerance_bps):
                return True
    return False


def _near_recent_swing_extreme(
    candles: list[OHLCV],
    price: Decimal,
    *,
    lookback: int = 40,
    tolerance_bps: Decimal = Decimal("75"),
) -> bool:
    if len(candles) < 5:
        return False
    recent = candles[-lookback:]
    swing_high = max(c.high for c in recent)
    swing_low = min(c.low for c in recent)
    return _price_near_range_extreme(
        price, range_low=swing_low, range_high=swing_high, tolerance_bps=tolerance_bps
    )


def _near_range_boundary(
    candles: list[OHLCV],
    price: Decimal,
    *,
    lookback: int = 30,
    tolerance_bps: Decimal = Decimal("100"),
) -> bool:
    if len(candles) < 8:
        return False
    recent = candles[-lookback:]
    range_high = max(c.high for c in recent)
    range_low = min(c.low for c in recent)
    range_size = range_high - range_low
    if range_size <= 0:
        return False
    midpoint = (range_high + range_low) / Decimal("2")
    compressed = range_size / midpoint <= Decimal("0.06")
    if not compressed:
        return False
    return _price_near_range_extreme(
        price, range_low=range_low, range_high=range_high, tolerance_bps=tolerance_bps
    )


def _price_near_range_extreme(
    price: Decimal,
    *,
    range_low: Decimal,
    range_high: Decimal,
    tolerance_bps: Decimal,
) -> bool:
    range_size = range_high - range_low
    if range_size <= 0:
        return False
    midpoint = (range_high + range_low) / Decimal("2")
    bps_tolerance = midpoint.copy_abs() * tolerance_bps / Decimal("10000")
    range_tolerance = range_size * Decimal("0.2")
    tolerance = min(bps_tolerance, range_tolerance)
    return price >= range_high - tolerance or price <= range_low + tolerance


def _has_directional_move(
    candles: list[OHLCV],
    *,
    lookback: int = 20,
    min_move_bps: Decimal = Decimal("150"),
) -> bool:
    if len(candles) < 5:
        return False
    recent = candles[-lookback:]
    start = recent[0].close
    end = recent[-1].close
    if start == 0:
        return False
    move_bps = (end - start).copy_abs() / start.copy_abs() * Decimal("10000")
    return move_bps >= min_move_bps


def _volume_expanded(
    candles: list[OHLCV],
    *,
    lookback: int = 20,
    multiplier: Decimal = Decimal("1.5"),
) -> bool:
    if len(candles) < 5:
        return False
    recent = candles[-lookback:]
    baseline = recent[:-1]
    if not baseline:
        return False
    avg_volume = sum(c.volume for c in baseline) / Decimal(len(baseline))
    return avg_volume > 0 and recent[-1].volume >= avg_volume * multiplier


def _range_expanded(
    candles: list[OHLCV],
    *,
    lookback: int = 20,
    multiplier: Decimal = Decimal("1.5"),
) -> bool:
    if len(candles) < 5:
        return False
    recent = candles[-lookback:]
    baseline = recent[:-1]
    if not baseline:
        return False
    avg_range = sum(c.high - c.low for c in baseline) / Decimal(len(baseline))
    latest_range = recent[-1].high - recent[-1].low
    return avg_range > 0 and latest_range >= avg_range * multiplier


def _price_near_zone(
    price: Decimal,
    zone_low: Decimal,
    zone_high: Decimal,
    tolerance_bps: Decimal,
) -> bool:
    low = min(zone_low, zone_high)
    high = max(zone_low, zone_high)
    midpoint = (low + high) / Decimal("2")
    tolerance = max(
        midpoint.copy_abs() * tolerance_bps / Decimal("10000"), Decimal("0")
    )
    return low - tolerance <= price <= high + tolerance


def _average_body(candles: list[OHLCV]) -> Decimal:
    if not candles:
        return Decimal("0")
    total = sum((c.close - c.open).copy_abs() for c in candles)
    return total / Decimal(len(candles))
