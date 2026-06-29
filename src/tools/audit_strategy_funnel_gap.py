"""Read-only operator audit for strategy-level proposal funnel gaps.

DEBT-074 surfaced a confusing shape: a strategy can have thousands of
``proposals_emitted`` in fail-closed metrics but zero persisted proposal
records and zero opened trades. That is not a downstream gate rejection in the
proposal funnel, because the runtime only persists the single selected proposal
after the proposal engine's per-symbol candidate selection.

This tool makes that distinction explicit from on-disk runtime data.
It never mutates data.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.config import get_settings
from src.logger import get_logger

logger = get_logger("crypto_master.tools.audit_strategy_funnel_gap")

AuditConclusion = Literal[
    "no_activity",
    "pre_funnel_candidate_selection_or_history_gap",
    "pre_funnel_fail_closed",
    "funnel_rejected",
    "opened",
    "mixed",
]

_OPENED_STATES = {"proposal_opened", "trade_opened", "outcome_linked"}


@dataclass(frozen=True)
class StrategyFunnelAudit:
    """Counts for one strategy's path through persisted proposal surfaces."""

    technique_name: str
    sub_account_id: str | None
    proposals_emitted: int
    proposals_fail_closed: int
    proposal_records: int
    score_rejected: int
    gate_rejected: int
    opened_or_linked: int
    linked_trades: int
    malformed_files: int
    conclusion: AuditConclusion
    suggested_follow_up: str


def audit_strategy_funnel_gap(
    data_dir: Path,
    technique_name: str,
    *,
    sub_account: str | None = None,
) -> StrategyFunnelAudit:
    """Audit one strategy's emitted/proposal/opened funnel footprint.

    Args:
        data_dir: Runtime data root.
        technique_name: Strategy name to inspect.
        sub_account: Optional sub-account namespace. When omitted, counts are
            aggregated across all sub-accounts and legacy root proposal files.

    Returns:
        A read-only summary classifying where the strategy disappears.
    """
    emitted, fail_closed, malformed_metrics = _load_fail_closed_counts(
        data_dir / "performance",
        technique_name,
        sub_account,
    )
    proposal_counts = _count_proposal_records(
        data_dir / "proposals",
        technique_name,
        sub_account,
    )
    malformed = malformed_metrics + proposal_counts.malformed_files
    conclusion = _classify(
        proposals_emitted=emitted,
        proposals_fail_closed=fail_closed,
        proposal_records=proposal_counts.total,
        score_rejected=proposal_counts.score_rejected,
        gate_rejected=proposal_counts.gate_rejected,
        opened_or_linked=proposal_counts.opened_or_linked,
    )
    return StrategyFunnelAudit(
        technique_name=technique_name,
        sub_account_id=sub_account,
        proposals_emitted=emitted,
        proposals_fail_closed=fail_closed,
        proposal_records=proposal_counts.total,
        score_rejected=proposal_counts.score_rejected,
        gate_rejected=proposal_counts.gate_rejected,
        opened_or_linked=proposal_counts.opened_or_linked,
        linked_trades=proposal_counts.linked_trades,
        malformed_files=malformed,
        conclusion=conclusion,
        suggested_follow_up=_suggest_follow_up(conclusion),
    )


@dataclass(frozen=True)
class _ProposalCounts:
    total: int = 0
    score_rejected: int = 0
    gate_rejected: int = 0
    opened_or_linked: int = 0
    linked_trades: int = 0
    malformed_files: int = 0


def _load_fail_closed_counts(
    performance_root: Path,
    technique_name: str,
    sub_account: str | None,
) -> tuple[int, int, int]:
    paths: list[Path]
    if sub_account is not None:
        paths = [performance_root / sub_account / technique_name / "fail_closed.json"]
    elif performance_root.exists():
        paths = sorted(performance_root.glob(f"*/{technique_name}/fail_closed.json"))
    else:
        paths = []

    emitted = 0
    fail_closed = 0
    malformed = 0
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            malformed += 1
            logger.warning("Skipping unreadable fail-closed metrics %s: %s", path, exc)
            continue
        if not isinstance(payload, dict):
            malformed += 1
            logger.warning("Skipping malformed fail-closed metrics %s", path)
            continue
        emitted += _int_field(payload, "proposals_emitted")
        fail_closed += _int_field(payload, "proposals_fail_closed")
    return emitted, fail_closed, malformed


def _count_proposal_records(
    proposals_root: Path,
    technique_name: str,
    sub_account: str | None,
) -> _ProposalCounts:
    counts = _ProposalCounts()
    for path in _proposal_paths(proposals_root, sub_account):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping unreadable proposal record %s: %s", path, exc)
            counts = _replace_counts(
                counts,
                malformed_files=counts.malformed_files + 1,
            )
            continue
        if not isinstance(payload, dict):
            counts = _replace_counts(
                counts,
                malformed_files=counts.malformed_files + 1,
            )
            continue
        proposal = payload.get("proposal")
        if not isinstance(proposal, dict):
            counts = _replace_counts(
                counts,
                malformed_files=counts.malformed_files + 1,
            )
            continue
        if proposal.get("technique_name") != technique_name:
            continue
        state = str(payload.get("final_state") or "generated")
        total = counts.total + 1
        score_rejected = counts.score_rejected + int(state == "score_rejected")
        gate_rejected = counts.gate_rejected + int(state.startswith("gate_rejected_"))
        opened_or_linked = counts.opened_or_linked + int(state in _OPENED_STATES)
        linked_trades = counts.linked_trades + int(bool(payload.get("trade_id")))
        counts = _ProposalCounts(
            total=total,
            score_rejected=score_rejected,
            gate_rejected=gate_rejected,
            opened_or_linked=opened_or_linked,
            linked_trades=linked_trades,
            malformed_files=counts.malformed_files,
        )
    return counts


def _proposal_paths(proposals_root: Path, sub_account: str | None) -> list[Path]:
    if not proposals_root.exists():
        return []
    if sub_account is not None:
        roots = [proposals_root / sub_account]
    else:
        roots = [proposals_root]
        roots.extend(sorted(path for path in proposals_root.iterdir() if path.is_dir()))

    paths: list[Path] = []
    for root in roots:
        paths.extend(root.glob("*.json"))
    return sorted(
        path
        for path in paths
        if "archive" not in path.relative_to(proposals_root).parts
    )


def _classify(
    *,
    proposals_emitted: int,
    proposals_fail_closed: int,
    proposal_records: int,
    score_rejected: int,
    gate_rejected: int,
    opened_or_linked: int,
) -> AuditConclusion:
    if proposals_emitted == 0 and proposal_records == 0:
        return "no_activity"
    if proposals_emitted > 0 and proposal_records == 0:
        if proposals_fail_closed > 0:
            return "pre_funnel_fail_closed"
        return "pre_funnel_candidate_selection_or_history_gap"
    if opened_or_linked > 0:
        return "opened"
    if proposal_records > 0 and (score_rejected > 0 or gate_rejected > 0):
        return "funnel_rejected"
    return "mixed"


def _suggest_follow_up(conclusion: AuditConclusion) -> str:
    if conclusion == "pre_funnel_candidate_selection_or_history_gap":
        return (
            "Persist or emit candidate-level deselection evidence before "
            "per-symbol dedup so emitted-but-unselected strategies are "
            "visible in the funnel."
        )
    if conclusion == "pre_funnel_fail_closed":
        return "Inspect strategy errors or sizing/RR validation failures."
    if conclusion == "funnel_rejected":
        return "Use proposal final_state counts to inspect the rejecting gate."
    if conclusion == "opened":
        return "No gap: at least one proposal reached an opened/linked state."
    if conclusion == "no_activity":
        return "No recorded emissions or proposals for this strategy."
    return "Mixed evidence; inspect proposal records and fail-closed metrics together."


def _int_field(payload: dict[str, object], key: str) -> int:
    value = payload.get(key, 0)
    return value if isinstance(value, int) and value >= 0 else 0


def _replace_counts(counts: _ProposalCounts, **updates: int) -> _ProposalCounts:
    data = {
        "total": counts.total,
        "score_rejected": counts.score_rejected,
        "gate_rejected": counts.gate_rejected,
        "opened_or_linked": counts.opened_or_linked,
        "linked_trades": counts.linked_trades,
        "malformed_files": counts.malformed_files,
    }
    data.update(updates)
    return _ProposalCounts(**data)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit one strategy's fail-closed emissions versus persisted "
            "proposal funnel records. Read-only."
        )
    )
    parser.add_argument("technique_name", help="Strategy name to audit.")
    parser.add_argument(
        "--sub-account",
        type=str,
        default=None,
        help="Restrict the audit to one sub-account.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = get_settings()
    audit = audit_strategy_funnel_gap(
        settings.data_dir,
        args.technique_name,
        sub_account=args.sub_account,
    )
    logger.info(
        "strategy=%s sub_account=%s emitted=%d fail_closed=%d "
        "proposal_records=%d score_rejected=%d gate_rejected=%d "
        "opened_or_linked=%d linked_trades=%d malformed=%d conclusion=%s",
        audit.technique_name,
        audit.sub_account_id or "*",
        audit.proposals_emitted,
        audit.proposals_fail_closed,
        audit.proposal_records,
        audit.score_rejected,
        audit.gate_rejected,
        audit.opened_or_linked,
        audit.linked_trades,
        audit.malformed_files,
        audit.conclusion,
    )
    logger.info("suggested_follow_up=%s", audit.suggested_follow_up)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
