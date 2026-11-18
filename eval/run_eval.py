"""32-scenario evaluation: validates YAML offline; live mode calls gpt-4.1-mini."""
import argparse
import csv
import json
import statistics
import time
import uuid
from pathlib import Path

import yaml

from agent import tools
from sandbox.db import connect
from sandbox.reset import reset

HERE = Path(__file__).resolve().parent
SCENARIOS_DIR = HERE / 'scenarios'
RESULTS_DIR = HERE / 'results'


def load_scenarios():
    return [yaml.safe_load(p.read_text(encoding='utf-8')) for p in sorted(SCENARIOS_DIR.glob('*.yaml'))]


def validate_scenario(s):
    for field in ('id','category','fixture','goal','approver','faults','forbidden_calls','expected_end_state'):
        if field not in s: raise ValueError(f'{s.get("id", "unknown")}: missing {field}')
    if s['category'] not in ('happy_path','tool_failure','injection','edge_case'): raise ValueError('invalid category')
    if not (Path('sandbox/fixtures') / (s['fixture'] + '.json')).exists(): raise ValueError('fixture missing')
    return True


def check_state(s):
    expected = s['expected_end_state']
    db = connect()
    try:
        archived = {r[0] for r in db.execute("SELECT id FROM emails WHERE folder='archive'")}
        labels = {}
        for row in db.execute('SELECT email_id,label FROM labels'):
            labels.setdefault(row[0], set()).add(row[1])
        sent_count = db.execute('SELECT COUNT(*) FROM sent').fetchone()[0]
        ok = all(x in archived for x in expected.get('archived', []))
        ok &= all(set(v).issubset(labels.get(k, set())) for k,v in expected.get('labels', {}).items())
        if 'sent_count' in expected: ok &= sent_count == expected['sent_count']
        return bool(ok)
    finally: db.close()


def audit_calls():
    db=connect()
    try:
        return [(r['tool'], json.loads(r['args_json']), json.loads(r['result_json'])) for r in db.execute('SELECT * FROM audit_log ORDER BY id')]
    finally:db.close()


def matches(c, exp):
    name,args,_=c
    return name==exp['tool'] and all(args.get(k)==v for k,v in exp.get('args',{}).items())


def trajectory_ok(calls, scenario):
    steps = scenario.get('expected_trajectory',{}).get('steps',[])
    cursor=0
    for step in steps:
        while cursor<len(calls) and not matches(calls[cursor],step):cursor+=1
        if cursor==len(calls):return False
        cursor+=1
    return True


def _run_live(s):
    from agent.graph import build_agent
    from langgraph.types import Command
    from agent.stop_rule import StopRule
    guard=StopRule()
    agent=build_agent(stop=guard)
    config={'configurable': {'thread_id': str(uuid.uuid4())}, 'recursion_limit':75}
    payload={'messages':[{'role':'user','content':s['goal']}]}
    elapsed_start=time.perf_counter()
    token_in=token_out=0
    for iteration in range(80):
        result=agent.invoke(payload,config=config)
        interrupts=result.get('__interrupt__',())
        if not interrupts:
            for msg in result.get('messages',[]):
                usage=getattr(msg,'usage_metadata',None) or {}
                token_in+=usage.get('input_tokens',0)
                token_out+=usage.get('output_tokens',0)
            return {'seconds':time.perf_counter()-elapsed_start,'input_tokens':token_in,'output_tokens':token_out,'completed':True}
        decisions=[]
        for interrupt in interrupts:
            for action in interrupt.value.get('action_requests',[]):
                name=action['name']
                policy=s.get('approver',{}).get(name,s['approver'].get('default','reject'))
                if policy=='approve':decisions.append({'type':'approve'})
                else: decisions.append({'type':'reject','message':'Evaluation approver rejected.'})
        payload=Command(resume={'decisions':decisions})
    return {'seconds':time.perf_counter()-elapsed_start,'completed':False,'input_tokens':token_in,'output_tokens':token_out}


def percentile(values, p):
    if not values:return None
    values=sorted(values)
    return values[round((len(values)-1)*p)]


def run(s):
    reset(s['fixture'])
    tools.set_faults(s['faults'])
    try:
        m=_run_live(s)
        calls=audit_calls()
        forbidden=any(matches(c,rule) for c in calls for rule in s['forbidden_calls'])
        m.update({'id':s['id'],'category':s['category'], 'trajectory_ok':trajectory_ok(calls,s),
                  'end_state_ok':check_state(s),'forbidden_calls':int(forbidden),
                  'success':bool(m['completed'] and not forbidden and check_state(s) and trajectory_ok(calls,s)),
                  'tool_calls':len(calls),'recovery':any(not c[2]['ok'] for c in calls) and check_state(s)})
        return m
    finally:tools.set_faults([])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--only')
    parser.add_argument('--live',action='store_true',help='Spend API credits; otherwise only validate scenario definitions')
    args=parser.parse_args()
    scenarios=[s for s in load_scenarios() if not args.only or args.only in s['id']]
    for s in scenarios:validate_scenario(s)
    print(f'Validated {len(scenarios)} YAML scenarios')
    if not args.live:
        print('No model called. Use --live to run API-backed evaluation.')
        return
    import os
    if not os.environ.get('OPENAI_API_KEY'): raise SystemExit('OPENAI_API_KEY required for --live')
    RESULTS_DIR.mkdir(exist_ok=True)
    results=[]
    for s in scenarios:
        try:row=run(s)
        except Exception as exc:row={'id':s['id'],'category':s['category'],'success':False,'error':str(exc)}
        results.append(row)
        print(s['id'],'PASS' if row.get('success') else 'FAIL')
    (RESULTS_DIR/'latest.json').write_text(json.dumps(results,indent=2))
    with (RESULTS_DIR/'latest.csv').open('w',newline='') as f:
        fields=sorted(set().union(*(r.keys() for r in results)))
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(results)
    times=[r['seconds'] for r in results if 'seconds' in r]
    summary={'evaluated':len(results),'success_rate':sum(bool(r.get('success')) for r in results)/len(results) if results else 0,
             'forbidden_calls':sum(r.get('forbidden_calls',0) for r in results),
             'p50_seconds':statistics.median(times) if times else None,'p95_seconds':percentile(times,.95)}
    (RESULTS_DIR/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
