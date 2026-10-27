"""Run the final source gate once, preserving logs and before/after hashes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import time

base = Path(__file__).resolve().parent
repo = Path('/private/tmp/crypto-master-source-recovery-20261027')

def snapshot():
    names = subprocess.check_output(
        ['rg', '--files', 'src', 'tests', 'scripts'], cwd=repo, text=True
    ).splitlines()
    return {name: hashlib.sha256((repo / name).read_bytes()).hexdigest()
            for name in sorted(names)}

before = snapshot()
env = os.environ.copy()
env['UV_PROJECT_ENVIRONMENT'] = '/Users/user/Desktop/Projects/crypto-master/.venv'
command = ['uv', 'run', '--no-sync', 'python', '-m', 'pytest', '-q']
started_at = datetime.now(timezone.utc).isoformat()
started = time.monotonic()
with (base / 'full-pytest.txt').open('x') as output:
    process = subprocess.run(command, cwd=repo, env=env,
                             stdout=output, stderr=subprocess.STDOUT)
after = snapshot()
record = {'command': command, 'started_at': started_at,
          'ended_at': datetime.now(timezone.utc).isoformat(),
          'seconds': time.monotonic() - started,
          'exit_code': process.returncode, 'source_count': len(before),
          'source_unchanged': before == after}
(base / 'source-input-sha256.json').write_text(json.dumps(before, indent=2) + '\n')
(base / 'full-gate.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
print('\n'.join((base / 'full-pytest.txt').read_text().splitlines()[-5:]))
assert process.returncode == 0 and before == after
