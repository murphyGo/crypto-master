#!/usr/bin/env python3
"""Reproduce original-window-only CPU proof from the separately frozen capture."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def at(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def main():
    manifest = json.loads((ROOT/'freeze-manifest.json').read_text())
    for row in manifest['files']:
        path = ROOT/row['relative_copy']
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']
    for name, expected in manifest['auditor_sha256'].items():
        assert sha(ROOT/name) == expected
    audit = json.loads((ROOT/'audit-summary.json').read_text())
    supplement = json.loads((ROOT/'cpu-supplement.json').read_text())
    source = ROOT/'supplements/cpu/v67-cpu-final.json'
    proof = supplement['cpu']['freeze']
    assert source.stat().st_size == proof['bytes'] and sha(source) == proof['sha256']
    data = json.loads(source.read_text())
    assert data['status'] == 'success'
    start, end = at(audit['window']['start']), at(audit['window']['end'])
    expected = {'fly_instance_cpu_baseline', 'fly_instance_cpu_balance', 'fly_instance_cpu_throttle'}
    results = {}
    for row in data['data']['result']:
        metric = row['metric']
        name = metric['__name__']
        assert name in expected and name not in results
        assert metric['app'] == 'crypto-master' and metric['instance'] == '6835752b711958'
        points = [(float(time), float(value)) for time, value in row['values']]
        assert all(math.isfinite(time) and math.isfinite(value) for time,value in points)
        times = [time for time,_ in points]
        assert times == sorted(set(times))
        within = [(time,value) for time,value in points if start.timestamp() <= time <= end.timestamp()]
        before = max(time for time in times if time <= start.timestamp())
        after = min(time for time in times if time >= end.timestamp())
        brackets = [time for time in times if before <= time <= after]
        assert all(b-a == 15 for a,b in zip(brackets,brackets[1:]))
        assert within
        values = [value for _,value in within]
        results[name] = {
            'all_capture_points':len(points), 'original_window_points':len(within),
            'first_original_window_point':stamp(within[0][0]),
            'last_original_window_point':stamp(within[-1][0]),
            'preceding_bracket':stamp(before), 'following_bracket':stamp(after),
            'bracketed_window_max_gap_seconds':15,
            'window_minimum':min(values), 'window_maximum':max(values),
            'window_zero_or_below_points':sum(value <= 0 for value in values),
            'window_positive_points':sum(value > 0 for value in values),
            'excluded_value_points':len(points)-len(within),
        }
    assert set(results) == expected
    captured = proof['source_mtime_ns']/1_000_000_000
    result = {
        'created_at':datetime.now(timezone.utc).isoformat(),
        'scope':'Original observation interval only; no new measurement or production query.',
        'observation_window':audit['window'],
        'initial_protocol_verdict':audit['verdict'],
        'initial_manifest_and_driver_hashes_verified':True,
        'frozen_cpu_sha256':proof['sha256'],
        'source_file_written_at_from_mtime':stamp(captured),
        'source_file_write_seconds_after_observation_end':captured-end.timestamp(),
        'late_capture_caveat':'This is a retrospectively queried CPU history written after observation ended. File mtime identifies local result publication, not query start. Later values are excluded from the original-window metrics.',
        'series':results,
        'sampled_original_window_coverage':True,
        'sampled_zero_balance_observed':results['fly_instance_cpu_balance']['window_zero_or_below_points'] > 0,
        'sampled_throttle_observed':results['fly_instance_cpu_throttle']['window_positive_points'] > 0,
        'depleted_cpu_qualified':False,
        'qualification_limits':'Balance and throttle are evaluated independently. Positive sampled balance does not imply buffered-only or unthrottled operation. Fifteen-second samples do not exclude shorter unsampled transients. No native, 1 GiB, or depleted-CPU acceptance follows.',
        'auditor_sha256':sha(Path(__file__)),
    }
    target = ROOT/'cpu-window-proof.json'
    with target.open('x') as file:
        json.dump(result,file,indent=2)
        file.write('\n')
    target.chmod(0o444)
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    main()
