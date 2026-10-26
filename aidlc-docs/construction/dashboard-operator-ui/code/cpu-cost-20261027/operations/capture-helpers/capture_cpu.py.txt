"""Read recorded Fly CPU metrics; credentials are never printed or retained."""
import argparse
import json
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--summary', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
summary = json.loads(a.summary.read_text())
start = datetime.fromisoformat(summary['started_at']) - timedelta(seconds=30)
credentials = json.loads(subprocess.run(['flyctl', 'auth', 'token', '--json'],
                                       capture_output=True, text=True, check=True).stdout)
credential = credentials.get('token') or credentials.get('access_token')
if not isinstance(credential, str):
    raise RuntimeError('Credential response unavailable')
authorization = credential if credential.startswith(('FlyV1 ', 'Bearer ')) else (
    'FlyV1 ' + credential if credential.startswith('fm2_') else 'Bearer ' + credential)
query = '{__name__=~"fly_instance_cpu_(baseline|balance|throttle)",app="crypto-master",instance="6835752b711958"}'
params = urllib.parse.urlencode({'query': query, 'start': start.isoformat(),
                                'end': datetime.now(timezone.utc).isoformat(), 'step': '15'})
request = urllib.request.Request('https://api.fly.io/prometheus/personal/api/v1/query_range?' + params,
                                 headers={'Authorization': authorization})
with urllib.request.urlopen(request, timeout=30) as response:
    data = json.load(response)
assert data['status'] == 'success'
with a.output.open('x') as output:
    json.dump(data, output, indent=2)
    output.write('\n')
for row in data['data']['result']:
    print(json.dumps({'metric': row['metric']['__name__'], 'points': len(row.get('values', [])),
                      'first': row.get('values', [])[:1], 'last': row.get('values', [])[-1:]}))
