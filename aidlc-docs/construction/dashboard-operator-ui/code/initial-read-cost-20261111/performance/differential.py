"""Seeded baseline/candidate checks, including malformed data and budgets."""
import hashlib,json,random
from pathlib import Path
from benchmark import baseline,OUT
from src.utils import bounded_read as current
old=baseline();rng=random.Random(8311);path=OUT/'differential-case.json'
blocks=[1,2,7,31,64,65536];checks=0

def signature(module,reader,limit):
    sequence=[];error=None
    try:
        for part in getattr(module,reader)(path,module.Generation.capture(path),record_bytes=limit):
            sequence.append(part)
    except current.ReadFailure as exc:error=exc.reason
    return sequence,error

def value(depth):
    choices=[None,True,False,rng.randrange(-100,100),rng.random(),''.join(rng.choices('ab한🙂\\"\n\t{}[]',k=rng.randrange(30)))]
    if depth:
        choices.extend([[value(depth-1) for _ in range(rng.randrange(4))],{f'k{i}':value(depth-1) for i in range(rng.randrange(4))}])
    return rng.choice(choices)

for case in range(150):
    rows=[{'v':value(2),'n':n} for n in range(rng.randrange(1,5))]
    valid=json.dumps(rows,ensure_ascii=bool(case%2),indent=case%3 or None).encode()
    cuts=[valid,valid[:rng.randrange(len(valid))],valid+b' false',valid.replace(b':',b'=',1),valid[:1]+b'null,'+valid[1:]]
    for content in cuts:
        path.write_bytes(content)
        for block in blocks:
            old.BLOCK_BYTES=current.BLOCK_BYTES=block
            limit=rng.choice([1,16,64,1024*1024])
            for reader in ('json_array_bytes','json_array_records'):
                expected=signature(old,reader,limit);actual=signature(current,reader,limit)
                assert expected==actual,(case,block,limit,reader,expected,actual)
                checks+=1
current.BLOCK_BYTES=65536
report={'seed':8311,'cases':150,'variants_per_case':5,'block_sizes':blocks,'readers':2,'comparisons':checks,'status':'PASS','baseline_sha256':hashlib.sha256((OUT/'bounded_read_baseline.py').read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256(Path('src/utils/bounded_read.py').read_bytes()).hexdigest()}
(OUT/'differential.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
