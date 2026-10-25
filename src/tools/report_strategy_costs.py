"""Read-only funding-coverage and adverse-carry report on a fixed snapshot.

Example: python -m src.tools.report_strategy_costs --snapshot /tmp/fly-snapshot
--sub-account rsi_universal --strategy rsi_universal --rate-per-interval 0.0001
--interval-hours 8

Rates/intervals are explicit scenario assumptions, not historical funding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from src.strategy.cost_coverage import adverse_carry_sensitivity
from src.strategy.performance import PerformanceRecord
from src.strategy.trade_history import TradeHistory


def report_strategy_costs(
    snapshot: Path,
    sub_account: str,
    strategy: str,
    *,
    rate_per_interval: Decimal,
    interval_hours: Decimal,
    quote_currency: str = "USDT",
    version: str | None = None,
) -> dict[str, Any]:
    """Hash and read two fixed files; no live fetch, tracker writes or repair."""
    for part in (sub_account, strategy):
        if not part or part in {".", ".."} or "/" in part or "\\" in part:
            raise ValueError("account and strategy must be single path components")
    record_path = snapshot / "performance" / sub_account / strategy / "records.json"
    trade_path = snapshot / "trades" / "paper" / sub_account / "trades.json"
    inputs: list[dict[str, str]] = []
    payloads: list[list[dict[str, Any]]] = []
    for path in (record_path, trade_path):
        raw = path.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, list) or any(
            not isinstance(row, dict) for row in payload
        ):
            raise ValueError(f"expected record array: {path}")
        payloads.append(payload)
        inputs.append(
            {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}
        )
    records = [PerformanceRecord.model_validate(row) for row in payloads[0]]
    if any(
        r.sub_account_id != sub_account
        or r.technique_name != strategy
        or r.mode != "paper"
        for r in records
    ):
        raise ValueError("performance file contains a different account/strategy/mode")
    if version is not None:
        records = [r for r in records if r.technique_version == version]
    trade_rows = [TradeHistory.model_validate(row) for row in payloads[1]]
    trades = {t.id: t for t in trade_rows}
    if len(trades) != len(trade_rows):
        raise ValueError("duplicate trade IDs in input ledger")
    result = adverse_carry_sensitivity(
        records,
        trades,
        rate_per_interval=rate_per_interval,
        interval_hours=interval_hours,
        quote_currency=quote_currency,
    )
    return {
        "sub_account_id": sub_account,
        "strategy": strategy,
        "version_filter": version,
        "inputs": inputs,
        **asdict(result),
        "scenario_complete": result.complete,
        "scenario_pnl": result.scenario_pnl,
        "actual_funding_cost": None,
    }


def _decimal_argument(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("expected a decimal number") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--sub-account", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--version")
    parser.add_argument("--rate-per-interval", type=_decimal_argument, required=True)
    parser.add_argument("--interval-hours", type=_decimal_argument, required=True)
    parser.add_argument("--quote-currency", default="USDT")
    args = parser.parse_args(argv)
    try:
        result = report_strategy_costs(
            args.snapshot,
            args.sub_account,
            args.strategy,
            rate_per_interval=args.rate_per_interval,
            interval_hours=args.interval_hours,
            quote_currency=args.quote_currency,
            version=args.version,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
