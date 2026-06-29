"""Shared proposal-bound lookup helpers for reconciliation tooling."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.logger import get_logger
from src.proposal.interaction import ProposalRecord
from src.utils.io import read_text

logger = get_logger("crypto_master.proposal.bounds")


@dataclass(frozen=True)
class ProposalBounds:
    """SL/TP bounds resolved from a proposal linked to a trade id."""

    stop_loss: str | None
    take_profit: str | None
    proposal_id: str
    sub_account_id: str
    technique_name: str


def load_proposal_trade_bounds_index(data_dir: Path) -> dict[str, ProposalBounds]:
    """Build ``trade_id -> proposal bounds`` from proposal history files."""
    proposal_root = data_dir / "proposals"
    if not proposal_root.exists():
        return {}

    index: dict[str, ProposalBounds] = {}
    for path in sorted(proposal_root.rglob("*.json")):
        try:
            payload = json.loads(read_text(path))
            record = ProposalRecord(**payload)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("Skipping unreadable proposal file %s: %s", path, exc)
            continue

        if not record.trade_id:
            continue
        proposal = record.proposal
        index[record.trade_id] = ProposalBounds(
            stop_loss=(
                str(proposal.stop_loss) if proposal.stop_loss is not None else None
            ),
            take_profit=(
                str(proposal.take_profit) if proposal.take_profit is not None else None
            ),
            proposal_id=proposal.proposal_id,
            sub_account_id=proposal.sub_account_id,
            technique_name=proposal.technique_name,
        )
    return index
