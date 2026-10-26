"""Retain only allowlisted dashboard diagnostic events from read-only Fly logs."""
import argparse
import json
import os
import selectors
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--output', type=Path, required=True)
p.add_argument('--stop-file', type=Path, required=True)
p.add_argument('--seconds', type=int, default=2400)
a = p.parse_args()
assert 1 <= a.seconds <= 7200
keys = {'event', 'kind', 'status', 'reason', 'stage', 'cache_age_seconds', 'admitted'}
proc = subprocess.Popen(['flyctl', 'logs', '--app', 'crypto-master', '--json'],
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
selector = selectors.DefaultSelector()
selector.register(proc.stdout, selectors.EVENT_READ)
started = time.monotonic()
count = 0
seen = 0
pending = ''
decoded = 0
decoder = json.JSONDecoder()
stopped_by_collector = False
try:
    with a.output.open('x') as output:
        while time.monotonic() - started < a.seconds and not a.stop_file.exists():
            if not selector.select(timeout=1):
                if proc.poll() is not None:
                    break
                continue
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                break
            pending += chunk.decode('utf-8', errors='replace')
            if len(pending) > 1024 * 1024:
                pending = ''
            seen += chunk.count(b'\n')
            while pending.strip():
                pending = pending.lstrip()
                try:
                    outer, consumed = decoder.raw_decode(pending)
                except json.JSONDecodeError:
                    break
                pending = pending[consumed:]
                decoded += 1
                try:
                    message = outer.get('message', '')
                    marker = message.find('{')
                    if marker < 0:
                        continue
                    event, _ = json.JSONDecoder().raw_decode(message[marker:])
                    if event.get('event') != 'dashboard_read_incomplete' or set(event) != keys:
                        continue
                    row = {'received_at': datetime.now(timezone.utc).isoformat(),
                           'fly_timestamp': outer.get('timestamp'), 'diagnostic': event}
                    output.write(json.dumps(row) + '\n')
                    output.flush()
                    count += 1
                except (ValueError, TypeError, AttributeError):
                    continue
finally:
    selector.close()
    stopped_by_collector = proc.poll() is None
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
print(json.dumps({'diagnostic_events': count, 'log_lines_seen': seen,
                  'json_records_decoded': decoded,
                  'client_exit_code': proc.returncode,
                  'stopped_by_collector': stopped_by_collector,
                  'seconds': time.monotonic()-started}))
if not stopped_by_collector and proc.returncode != 0:
    raise SystemExit(2)
