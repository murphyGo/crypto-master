"""CLI entrypoint for proposal replay reports."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import TextIO

from src.proposal.replay import (
    ProposalReplayExitAssumption,
    ProposalReplayInput,
    ProposalReplayInputError,
    ProposalReplayScenario,
    compare_replay_scenarios,
    render_replay_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare proposal replay scenarios and emit a Markdown report."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to a ProposalReplayInput JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional report path. Defaults to stdout.",
    )
    parser.add_argument(
        "--min-score",
        action="append",
        type=_nonnegative_finite_float,
        default=[],
        help=(
            "Approval threshold to replay. Can be repeated. "
            "Defaults to 0.0 when omitted."
        ),
    )
    parser.add_argument(
        "--exit-assumption",
        action="append",
        choices=[item.value for item in ProposalReplayExitAssumption],
        default=[],
        help=(
            "Same-candle TP/SL assumption to replay. Can be repeated. "
            "Defaults to stop_first when omitted."
        ),
    )
    return parser


def _nonnegative_finite_float(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative finite number")
    return value


def load_replay_input(path: Path) -> ProposalReplayInput:
    """Load a replay input JSON file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ProposalReplayInput.model_validate(payload)
    except OSError as exc:
        raise ProposalReplayInputError(
            f"failed to read replay input {path}: {exc}"
        ) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise ProposalReplayInputError(f"invalid replay input {path}: {exc}") from exc


def build_scenarios(
    *,
    min_scores: list[float],
    exit_assumptions: list[str],
) -> list[ProposalReplayScenario]:
    """Build scenario grid from CLI option values."""
    scores = min_scores or [0.0]
    assumptions = exit_assumptions or [ProposalReplayExitAssumption.STOP_FIRST.value]
    return [
        ProposalReplayScenario(
            min_score=score,
            exit_assumption=ProposalReplayExitAssumption(assumption),
        )
        for score in scores
        for assumption in assumptions
    ]


def run_report(
    *,
    input_path: Path,
    output_path: Path | None,
    min_scores: list[float],
    exit_assumptions: list[str],
    stdout: TextIO = sys.stdout,
) -> None:
    """Run replay comparison and write the Markdown report."""
    replay_input = load_replay_input(input_path)
    scenarios = build_scenarios(
        min_scores=min_scores,
        exit_assumptions=exit_assumptions,
    )
    report = render_replay_report(compare_replay_scenarios(replay_input, scenarios))
    if output_path is None:
        stdout.write(report + "\n")
        return
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report + "\n", encoding="utf-8")
    except OSError as exc:
        raise ProposalReplayInputError(
            f"failed to write replay report {output_path}: {exc}"
        ) from exc


def main(argv: list[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """CLI main."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        run_report(
            input_path=args.input,
            output_path=args.output,
            min_scores=args.min_score,
            exit_assumptions=args.exit_assumption,
            stdout=stdout,
        )
    except ProposalReplayInputError as exc:
        parser.exit(2, f"proposal replay: {exc}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
