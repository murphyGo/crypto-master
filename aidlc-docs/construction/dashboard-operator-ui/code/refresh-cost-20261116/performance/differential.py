"""Seeded byte/error parity against frozen v72 methods, including codec limits."""
import ast
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import src.dashboard.projections as projection
import src.dashboard.checkpoint_store as checkpoint

base = Path('.tmp/dashboard-refresh-20261116')

def old_function(file, name, namespace, cls=None):
    nodes = ast.parse((base / file).read_text()).body
    if cls:
        nodes = next(n.body for n in nodes if isinstance(n, ast.ClassDef) and n.name == cls)
    node = next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = dict(namespace)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<frozen-v72>', 'exec'), scope)
    return scope[name]

old_size = old_function('projections_baseline.py', 'size', vars(projection), 'StateBudget')
old_encode = old_function('checkpoint_store_baseline.py', 'encode_state', vars(checkpoint))
new_size, new_encode = projection.StateBudget.size, checkpoint.encode_state
rng = random.Random(834617)
at = datetime(2026, 11, 17, tzinfo=timezone.utc)
counts = {'byte_matches': 0, 'error_matches': 0}

def outcome(size, encode, state, cap):
    projection.StateBudget.size = size
    try:
        return ('bytes', encode(state, cap=cap))
    except (checkpoint.CacheMiss, ValueError, TypeError, RecursionError) as error:
        return (type(error).__name__, str(error))

try:
    cases = []
    for index in range(120):
        rows = [{'n': rng.randrange(-100000,100000), 'text': '가\\"' * rng.randrange(20),
                 'decimal': Decimal(str(rng.randrange(10000))) / 100, 'time': at,
                 'tuple': (True, None, b'bytes')} for _ in range(rng.randrange(1,900))]
        state = {'rows': rows, 'shared': [rows, rows], 'set': {1,2,3},
                 'cycle': projection.CycleState((at,index))}
        if index % 15 == 0: state['invalid'] = float('inf')
        cases.append(state)
    deep = {'payload': list(range(10000))}
    for _ in range(66): deep = {'child': deep}
    cases.append(deep)
    for state in cases:
        for cap in (1024, 1024*1024-40):
            before = outcome(old_size, old_encode, state, cap)
            after = outcome(new_size, new_encode, state, cap)
            assert before == after, (len(cases), cap, before[0], after[0])
            counts['byte_matches' if before[0] == 'bytes' else 'error_matches'] += 1
finally:
    projection.StateBudget.size = new_size
report = {'seed':834617, 'cases':len(cases), 'comparisons':sum(counts.values()),
          'counts':counts, 'deep_split_limit_included':True,
          'baseline_commit':'71c87874222bb8b385583651f8c2b124e108fa05',
          'candidate_sha256':{name:hashlib.sha256(Path(name).read_bytes()).hexdigest()
                              for name in ('src/dashboard/projections.py','src/dashboard/checkpoint_store.py')}}
(base/'differential.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
