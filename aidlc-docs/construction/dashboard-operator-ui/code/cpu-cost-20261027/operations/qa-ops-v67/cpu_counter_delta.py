"""Additional offline throttle COUNTER interpretation; never rewrites prior audits."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def utc(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat()

def counter_analysis(points, start, end):
    assert points and start <= end
    assert [t for t,v in points] == sorted({t for t,v in points})
    assert all(math.isfinite(t) and math.isfinite(v) and v >= 0 for t,v in points)
    within=[(t,v) for t,v in points if start <= t <= end]
    assert within
    intervals=[]
    for (left,before),(right,after) in zip(points,points[1:]):
        if right < start or left > end:
            continue
        inside=start <= left <= right <= end
        intervals.append({'left_at':utc(left),'right_at':utc(right),'before_centiseconds':before,'after_centiseconds':after,'delta_centiseconds':after-before,'entire_interval_inside_observation':inside,'crosses_observation_boundary':not inside,'decrease_or_reset':after<before})
    increases=[row for row in intervals if row['entire_interval_inside_observation'] and row['delta_centiseconds']>0]
    resets=[row for row in intervals if row['decrease_or_reset']]
    boundary=[row for row in intervals if row['crosses_observation_boundary'] and row['delta_centiseconds'] != 0]
    return {'positive_counter_samples_inside_window':sum(v>0 for t,v in within),'first_window_counter_centiseconds':within[0][1],'last_window_counter_centiseconds':within[-1][1],'net_change_between_first_and_last_window_samples_centiseconds':within[-1][1]-within[0][1],'new_throttling_observed_in_wholly_inside_sample_intervals':bool(increases),'sum_positive_deltas_in_wholly_inside_intervals_centiseconds':sum(row['delta_centiseconds'] for row in increases),'positive_delta_intervals_inside_window':increases,'decrease_or_reset_intervals_touching_window':resets,'changed_boundary_crossing_intervals':boundary,'interpretation':'A positive cumulative counter alone does not show new throttling. Positive deltas with both samples inside the observation prove increases during that sampled interval. Boundary-crossing increases cannot be assigned wholly to the observation. Decreases may indicate a reset; positive deltas are reported separately and are not an exact reset-corrected total. Fifteen-second samples can miss resets and do not localize request causality.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-check',action='store_true');args=parser.parse_args()
    if args.self_check:
        cases=[('flat_positive',[(0,10),(15,10)],0,15,False,0),('increase',[(0,0),(15,2)],0,15,True,0),('reset_then_increase',[(0,10),(15,1),(30,3)],0,30,True,1),('only_boundary_increase',[(-15,0),(0,5),(15,5)],-1,15,False,0)]
        rows=[]
        for name,points,start,end,increase,resets in cases:
            value=counter_analysis(points,start,end)
            assert value['new_throttling_observed_in_wholly_inside_sample_intervals'] is increase
            assert len(value['decrease_or_reset_intervals_touching_window'])==resets
            rows.append({'name':name,'pass':True})
        result={'result':'PASS','cases':rows,'script_sha256':sha(Path(__file__))}
        target=OUT/'cpu-counter-self-check.json'
    else:
        audit=json.loads((OUT/'audit-summary.json').read_text())
        supplement=json.loads((OUT/'cpu-supplement.json').read_text())
        proof=supplement['cpu']['freeze'];source=OUT/'supplements/cpu/v67-cpu-final.json'
        assert source.stat().st_size==proof['bytes'] and sha(source)==proof['sha256']
        raw=json.loads(source.read_text());assert raw['status']=='success'
        rows=[r for r in raw['data']['result'] if r['metric']['__name__']=='fly_instance_cpu_throttle'];assert len(rows)==1
        metric=rows[0]['metric'];assert metric['app']=='crypto-master' and metric['instance']=='6835752b711958'
        start=datetime.fromisoformat(audit['window']['start']).timestamp();end=datetime.fromisoformat(audit['window']['end']).timestamp()
        points=[(float(t),float(v)) for t,v in rows[0]['values']]
        value=counter_analysis(points,start,end)
        result={'scope':'Separate interpretation supplement; initial audits/raw captures retained unchanged. Original observation interval only.','observation_window':audit['window'],'source_cpu_sha256':sha(source),'script_sha256':sha(Path(__file__)),'metric_semantics':{'fly_instance_cpu_throttle':'cumulative counter, centiseconds','fly_instance_cpu_balance':'gauge, centiseconds','fly_instance_cpu_baseline':'CPU units'},'primary_sources':['https://docs.fly.io/monitoring/metrics','https://docs.fly.io/machines/cpu-performance'],'source_verification':'Current official metric semantics checked by parent; this offline auditor makes no network request.','counter_analysis':value,'initial_positive_throttle_flag_interpretation':'cpu-window-proof.sampled_throttle_observed records positive counter samples; use the counter-delta field here to identify newly observed throttling.','depleted_cpu_qualified':False,'production_load_added':False}
        target=OUT/'cpu-counter-interpretation.json'
    with target.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))

if __name__=='__main__':main()
