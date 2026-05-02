"""Run multi-sub-account strategy-combination backtests."""

from __future__ import annotations

import argparse
import asyncio
import csv
import importlib
import struct
import zlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from src.backtest.harness import BacktestHarness
from src.backtest.multi_account_report import MultiAccountReport
from src.config import BinanceConfig, get_settings
from src.exchange.binance import BinanceExchange
from src.models import OHLCV
from src.strategy.loader import load_all_strategies
from src.trading.sub_account import SubAccount


async def fetch_ohlcv_window(**kwargs: Any) -> list[OHLCV]:
    """Proxy to the baseline fetcher without pulling it into static type checks."""
    module = importlib.import_module("scripts.backtest_baselines")
    fetched = await module.fetch_ohlcv_window(**kwargs)
    return list(fetched)


def load_sub_accounts_config(path: Path) -> list[SubAccount]:
    """Load the Phase 19.3 sub-account YAML shape."""
    parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    accounts = parsed.get("sub_accounts")
    if not isinstance(accounts, list):
        raise ValueError(f"{path}: sub_accounts must be a list")
    return [SubAccount(**item) for item in accounts]


async def run_from_config(
    config_path: Path,
    *,
    symbol: str,
    timeframe: str,
    candles: int,
    output_dir: Path | None = None,
) -> Path:
    """Fetch one OHLCV window, run the harness, and write artifacts."""
    settings = get_settings()
    target_dir = output_dir or settings.data_dir / "backtest" / "combinations"
    sub_accounts = load_sub_accounts_config(config_path)
    strategies = load_all_strategies()
    exchange = BinanceExchange(BinanceConfig(), testnet=False)
    await exchange.connect()
    try:
        ohlcv = await fetch_ohlcv_window(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,  # type: ignore[arg-type]
            total_candles=candles,
        )
    finally:
        await exchange.disconnect()

    harness = BacktestHarness(data_dir=target_dir)
    report = await harness.run_sub_accounts(
        sub_accounts,
        {(symbol, timeframe): ohlcv},
        strategies,
    )
    report_path = harness.save_report(report)
    _write_trades_csv(report_path.parent / "trades.csv", report)
    _write_equity_curves_png(report_path.parent / "equity_curves.png", report)
    return report_path


def _write_trades_csv(path: Path, report: MultiAccountReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "sub_account_id",
                "technique",
                "symbol",
                "side",
                "entry_time",
                "exit_time",
                "pnl",
                "close_reason",
            ],
        )
        writer.writeheader()
        for trade in report.merged_trade_ledger:
            writer.writerow(
                {
                    "sub_account_id": trade.sub_account_id,
                    "technique": trade.technique_name,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "entry_time": trade.entry_time.isoformat(),
                    "exit_time": trade.exit_time.isoformat(),
                    "pnl": str(trade.pnl),
                    "close_reason": trade.close_reason,
                }
            )


def _write_equity_curves_png(path: Path, report: MultiAccountReport) -> None:
    """Write a lightweight line-chart PNG without adding plotting dependencies."""
    width, height = 900, 480
    margin = 48
    canvas = bytearray([255, 255, 255] * width * height)
    colors = [
        (31, 119, 180),
        (214, 39, 40),
        (44, 160, 44),
        (148, 103, 189),
        (255, 127, 14),
        (23, 190, 207),
    ]
    curves = {
        account_id: [equity for _, equity in points]
        for account_id, points in report.equity_curves.items()
        if points
    }
    if curves:
        all_values = [value for values in curves.values() for value in values]
        min_value = min(all_values)
        max_value = max(all_values)
        span = max(max_value - min_value, Decimal("1"))
        max_len = max(len(values) for values in curves.values())
        x_span = max(max_len - 1, 1)
        for idx, values in enumerate(curves.values()):
            points: list[tuple[int, int]] = []
            for point_index, value in enumerate(values):
                x = margin + int((width - margin * 2) * point_index / x_span)
                y_ratio = float((value - min_value) / span)
                y = height - margin - int((height - margin * 2) * y_ratio)
                points.append((x, y))
            color = colors[idx % len(colors)]
            for left, right in zip(points, points[1:], strict=False):
                _draw_line(canvas, width, height, left, right, color)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_encode_png(width, height, bytes(canvas)))


def _draw_line(
    canvas: bytearray,
    width: int,
    height: int,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= x0 < width and 0 <= y0 < height:
            offset = (y0 * width + x0) * 3
            canvas[offset : offset + 3] = bytes(color)
        if x0 == x1 and y0 == y1:
            break
        doubled = 2 * err
        if doubled >= dy:
            err += dy
            x0 += sx
        if doubled <= dx:
            err += dx
            y0 += sy


def _encode_png(width: int, height: int, rgb: bytes) -> bytes:
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * stride : (y + 1) * stride])
    chunks = [
        _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    ]
    chunks.append(_png_chunk(b"IDAT", zlib.compress(bytes(raw), level=9)))
    chunks.append(_png_chunk(b"IEND", b""))
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return (
        struct.pack(">I", len(data))
        + payload
        + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
    )


def _candles_from_window(window: str, timeframe: str) -> int:
    if not window.endswith("d"):
        raise ValueError("--window currently accepts day strings like 90d")
    days = int(window[:-1])
    per_day = {"15m": 96, "1h": 24, "4h": 6}.get(timeframe)
    if per_day is None:
        raise ValueError("timeframe must be one of 15m, 1h, 4h")
    return days * per_day


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--window", default="90d")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    started = datetime.now().isoformat(timespec="seconds")
    candles = _candles_from_window(args.window, args.timeframe)
    path = asyncio.run(
        run_from_config(
            args.config,
            symbol=args.symbol,
            timeframe=args.timeframe,
            candles=candles,
            output_dir=args.output_dir,
        )
    )
    print(f"{started} wrote combination backtest report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
