"""Proposal replay dashboard page.

Runs the deterministic proposal replay contract from an operator-supplied
``ProposalReplayInput`` JSON file and renders the Markdown report in-app.

Related Requirements:
- FR-043: Proposal replay simulator
- FR-032 / NFR-003: Streamlit dashboard
"""

from __future__ import annotations

import math
from pathlib import Path

import streamlit as st

from src.proposal.replay import (
    ProposalReplayExitAssumption,
    ProposalReplayInputError,
    compare_replay_scenarios,
    render_replay_report,
)
from src.tools.proposal_replay import build_scenarios, load_replay_input

DEFAULT_MIN_SCORES = "0.0, 1.0"


def parse_min_scores(raw: str) -> list[float]:
    """Parse comma-separated nonnegative replay thresholds."""
    values = [part.strip() for part in raw.split(",") if part.strip()]
    if not values:
        return []

    scores: list[float] = []
    for value in values:
        try:
            score = float(value)
        except ValueError as exc:
            raise ProposalReplayInputError(
                f"invalid min score {value!r}: must be a number"
            ) from exc
        if not math.isfinite(score) or score < 0:
            raise ProposalReplayInputError(
                f"invalid min score {value!r}: must be nonnegative and finite"
            )
        scores.append(score)
    return scores


def render_report_from_path(
    *,
    input_path: Path,
    min_score_text: str,
    exit_assumptions: list[str],
) -> str:
    """Load replay input and render a Markdown report for dashboard display."""
    replay_input = load_replay_input(input_path)
    scenarios = build_scenarios(
        min_scores=parse_min_scores(min_score_text),
        exit_assumptions=exit_assumptions,
    )
    return render_replay_report(compare_replay_scenarios(replay_input, scenarios))


def render() -> None:
    """Render the Proposal Replay page."""
    st.title("Proposal Replay")
    st.caption("Compare approval thresholds against deterministic replay inputs.")

    query_input = _query_param_first("input")
    input_text = st.text_input(
        "Replay input JSON",
        value=query_input or "",
        placeholder="reports/replay-input.json",
    )
    min_score_text = st.text_input(
        "Approval thresholds",
        value=_query_param_first("min_score") or DEFAULT_MIN_SCORES,
    )
    assumption_options = [item.value for item in ProposalReplayExitAssumption]
    requested_assumption = _query_param_first("exit_assumption")
    default_assumptions = (
        [requested_assumption]
        if requested_assumption in assumption_options
        else [ProposalReplayExitAssumption.STOP_FIRST.value]
    )
    exit_assumptions = st.multiselect(
        "Same-candle exit assumptions",
        options=assumption_options,
        default=default_assumptions,
    )

    if not input_text.strip():
        st.info("Provide a ProposalReplayInput JSON path to render a replay report.")
        return

    try:
        report = render_report_from_path(
            input_path=Path(input_text).expanduser(),
            min_score_text=min_score_text,
            exit_assumptions=exit_assumptions,
        )
    except ProposalReplayInputError as exc:
        st.error(str(exc))
        return

    st.markdown(report)
    st.download_button(
        "Download Markdown",
        data=report + "\n",
        file_name="proposal-replay-report.md",
        mime="text/markdown",
    )


def _query_param_first(name: str) -> str | None:
    raw = st.query_params.get(name)
    if raw is None:
        return None
    if isinstance(raw, list):
        return str(raw[0]) if raw else None
    return str(raw)


__all__ = [
    "DEFAULT_MIN_SCORES",
    "parse_min_scores",
    "render",
    "render_report_from_path",
]
