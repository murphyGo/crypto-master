"""Read only owned observer/collector and bounded idle-guard process matches."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

rows = subprocess.run(['ps', '-axo', 'pid=,ppid=,command='], check=True, capture_output=True, text=True).stdout.splitlines()
remaining = []
for line in rows:
    fields = line.strip().split(None, 2)
    if len(fields) < 3:
        continue
    pid, parent_pid, cmd = fields
    args = cmd.split()
    if not args:
        continue
    python = 'python' in Path(args[0]).name and len(args) > 1
    task = python and (
        args[1].endswith('/dashboard-initial-read-20261111/run_observation.py')
        or (args[1].endswith(('observe_dashboard_protocol.py', 'capture_diagnostics.py'))
            and any('/dashboard-initial-read-20261111/' in a for a in args[2:]))
    )
    guard = cmd.startswith('/usr/bin/caffeinate -i -s -t 2500 -w ')
    if task or guard:
        remaining.append({'pid': int(pid), 'parent_pid': int(parent_pid), 'kind': 'task_observer_or_collector' if task else 'bounded_idle_guard'})
result = {
    'captured_at': datetime.now(timezone.utc).isoformat(),
    'remaining_task_or_matching_bounded_guard': remaining,
    'runner_exit_zero': json.loads(Path('.tmp/dashboard-initial-read-20261111/runner-result.json').read_text())['observer_exit_code'] == 0,
    'scope': 'Exact observer/collector task paths and bounded guard command shape; no unrelated process terminated.',
}
Path('.tmp/dashboard-initial-read-20261111/local-cleanup.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
assert not remaining
