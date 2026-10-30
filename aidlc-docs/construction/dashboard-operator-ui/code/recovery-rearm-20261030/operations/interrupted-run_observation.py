"""Run the timeout-isolated guarded observer and retain read-only verification."""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path.cwd()
out = root / '.tmp/dashboard-rearm-20261030'
historical = root / 'aidlc-docs/construction/dashboard-operator-ui/code/home-recovery-20261026/operations'
stop_file = out / 'stop-diagnostics'
assert not stop_file.exists()
summary_path = out / 'observation/rearm-concurrency-summary.json'
metadata = {'started_at': datetime.now(timezone.utc).isoformat()}
with (out / 'diagnostic-collector-output.json').open('x') as collector_output:
    collector = subprocess.Popen([sys.executable, str(historical / 'capture_diagnostics.py'), '--output', str(out / 'diagnostics.jsonl'), '--stop-file', str(stop_file), '--seconds', '2500'], stdout=collector_output, stderr=subprocess.STDOUT)
    try:
        observer = subprocess.run([sys.executable, 'scripts/observe_dashboard_protocol.py', '--output-dir', str(out / 'observation'), '--descriptor', str(out / 'postdeploy-streamlit.pb'), '--phase', 'rearm', '--seconds', '600', '--max-seconds', '2100', '--cadence', '20'])
        metadata['observer_exit_code'] = observer.returncode
    finally:
        stop_file.touch()
        try:
            metadata['collector_exit_code'] = collector.wait(timeout=12)
        except subprocess.TimeoutExpired:
            collector.terminate()
            metadata['collector_exit_code'] = collector.wait(timeout=5)
if summary_path.exists():
    with (out / 'cpu-capture-output.txt').open('x') as handle:
        cpu = subprocess.run([sys.executable, str(historical / 'capture_cpu.py'), '--summary', str(summary_path), '--output', str(out / 'cpu-history.json')], stdout=handle, stderr=subprocess.STDOUT, timeout=60)
        metadata['cpu_capture_exit_code'] = cpu.returncode
post = subprocess.run([sys.executable, str(out / 'capture_runtime.py'), 'after'])
metadata['postflight_exit_code'] = post.returncode
metadata['ended_at'] = datetime.now(timezone.utc).isoformat()
(out / 'runner-result.json').write_text(json.dumps(metadata, indent=2)+'\n')
print(json.dumps(metadata), flush=True)
raise SystemExit(metadata.get('observer_exit_code', 1) or post.returncode)
