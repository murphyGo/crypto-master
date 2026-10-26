"""Offline independent exact-cutoff proof; writes task-owned temp fixture only."""
import hashlib
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.dashboard.checkpoint_store import CheckpointStore
from src.dashboard.projections import build_projection
from src.dashboard.read_models import Limits, Query
from src.proposal.interaction import ProposalRecord
from tests.test_dashboard_trading import _make_proposal

OUT = Path('/private/tmp/crypto-master-cpu-cost-delivery-20261027/qa')
NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)
root = Path(tempfile.mkdtemp(prefix='boundary-', dir=OUT))
(root/'proposals').mkdir()
(root/'derived').mkdir()
for key, at in [('boundary', NOW-timedelta(hours=24)), ('current', NOW), ('future', NOW+timedelta(microseconds=1))]:
    p = _make_proposal(key).model_copy(update={'created_at': at, 'technique_name': key})
    row = ProposalRecord(proposal=p, decision='rejected', rejection_reason='composite 0.2000 below threshold 0.3000')
    (root/'proposals'/f'{key}.json').write_text(row.model_dump_json())
store = CheckpointStore(root/'derived')
def project(at, previous=None, enabled=False):
    return next(v for v in build_projection(Query(root,'proposals',window='24h',at=at), Limits(), previous=previous, checkpoint_store=store if enabled else None) if v is not None)
first = project(NOW)
raw = json.dumps(first).encode()
rows = []
for enabled in [False, True]:
    equal = project(NOW, raw, enabled)
    later = project(NOW+timedelta(microseconds=1), raw, enabled)
    canonical = project(NOW+timedelta(microseconds=1))
    assert equal == first
    assert later == canonical
    assert first['counts']['total'] == later['counts']['total'] == 2
    assert first['by_strategy']['boundary']['total'] == 1
    assert first['by_strategy']['future']['total'] == 0
    assert later['by_strategy']['boundary']['total'] == 0
    assert later['by_strategy']['future']['total'] == 1
    assert first['threshold'] == later['threshold'] == 3
    rows.append({'checkpoint_enabled': enabled, 'inclusive_lower_cutoff':True, 'future_upper_boundary':True, 'one_microsecond_expiry_matches_canonical': True, 'lifetime_threshold_unchanged':True, 'full_later_sha256':hashlib.sha256(json.dumps(later, sort_keys=True).encode()).hexdigest()})
report={'result':'PASS', 'fixture':str(root), 'rows':rows, 'limitations':'Local exact-function output proof only; no production/native/cold latency acceptance.'}
(OUT/'window-boundary-proof.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
