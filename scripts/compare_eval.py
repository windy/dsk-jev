"""Paired live comparison. Keys come exclusively from environment.
Same cases, sequential concurrency=1, alternating provider order, persistent HTTP
connections. At most 3 retries, 30s budget; proxy manages its own retries.
"""
import datetime as dt
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import socket
import subprocess
import time
from email.utils import parsedate_to_datetime
from accounting import PRICING, costs
ROOT = Path(__file__).resolve().parents[1]

def grade(case, response):
    checks = []
    for qid, expected in case['expected'].items():
        typ = case['request']['questions'][qid]['type']
        try:
            a = response['answers'][qid]
            actual = a['choice'] if typ == 'choice' else (a['noul'] >= .5 if typ == 'noul' else math.floor(a['score'] + .5))
            checks.append({'question': qid, 'pass': actual == expected, 'actual': actual, 'expected': expected})
        except (KeyError, TypeError, ValueError, OverflowError):
            checks.append({'question': qid, 'pass': False, 'invalid_answer': True})
    return checks

def percentile(xs, p):
    return sorted(xs)[max(0, math.ceil(len(xs)*p)-1)] if xs else None

def summarize(rows, events, provider):
    ok = [r for r in rows if r['status'] == 200 and not any(c.get('invalid_answer') for c in r['checks'])]
    judgments = sum(r['questions'] for r in rows)
    correct = sum(c['pass'] for r in rows for c in r['checks'])
    money = {s: costs(events, s) for s in (['jev'] if provider == 'jev' else ['deepseek_peak', 'deepseek_offpeak'])}
    for v in money.values():
        total = v['total_estimated_usd']
        v['usd_per_1000_requests'] = float(total)*1000/len(rows) if total is not None and rows else None
        v['usd_per_1000_correct_judgments'] = float(total)*1000/correct if total is not None and correct else None
    tokens = {k: sum(e[k] for e in events if type(e.get(k)) is int) for k in ('input_tokens','output_tokens','cached_tokens')}
    return dict(requests=len(rows), successful_requests=len(ok), judgments=judgments, correct_judgments=correct,
        effective_accuracy=correct/judgments if judgments else None, upstream_attempts=len(events),
        retried_requests=sum(r.get('attempts',0)>1 for r in rows), usage_known_subtotals=tokens,
        unknown_usage_attempts=sum(not e.get('usage_known') for e in events),
        cache_hit_ratio=tokens['cached_tokens']/tokens['input_tokens'] if provider=='deepseek' and tokens['input_tokens'] and all(e.get('cached_tokens') is not None and e.get('input_tokens') is not None for e in events) else None,
        latency_ms={scope:{'p50':percentile([r['latency_ms'] for r in rr],.5),'p95':percentile([r['latency_ms'] for r in rr],.95)} for scope,rr in [('all_requests',rows),('successful_requests',ok)]},cost=money)

def main():
    prefix=os.environ.get('EVAL_PREFIX','comparison-v4')
    if not re.fullmatch(r'[\w-]+',prefix): raise ValueError('Invalid prefix')
    reports=ROOT/'reports';reports.mkdir(exist_ok=True)
    ledger_path=reports/f'{prefix}-deepseek-usage.jsonl'
    if ledger_path.exists(): raise RuntimeError('Use a new EVAL_PREFIX; never append to an old benchmark ledger')
    cases_path=Path(os.environ.get('EVAL_CASES',str(ROOT/'evals/cases.json')))
    cases_bytes=cases_path.read_bytes();cases=json.loads(cases_bytes)
    local=secrets.token_urlsafe(24)
    with socket.socket() as sock: sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=dict(os.environ,PROXY_API_KEY=local,LISTEN_ADDR=f'127.0.0.1:{port}',MAX_RETRIES='3',UPSTREAM_TIMEOUT='30s',PROMPT_MODE='standard',OUTPUT_MODE='standard',USAGE_LEDGER_PATH=str(ledger_path),DEEPSEEK_BASE_URL='https://api.deepseek.com/beta',DEEPSEEK_MODEL='deepseek-flash')
    log=open(reports/f'{prefix}-server.log','w')
    proc=subprocess.Popen([os.environ.get('DSK_JEV_BINARY',str(ROOT/'bin/dsk-jev'))],env=env,stdout=subprocess.DEVNULL,stderr=log)
    conns={'jev':http.client.HTTPSConnection('api.typesafe.ai',timeout=30),'deepseek':http.client.HTTPConnection('127.0.0.1',port,timeout=35)}
    keys={'jev':os.environ['JEV_API_KEY'],'deepseek':local}
    rows=[];jev_events=[];started=dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        for _ in range(100):
            try:
                c=conns['deepseek'];c.request('GET','/healthz');r=c.getresponse();r.read();break
            except OSError: c.close();time.sleep(.05)
        else:raise RuntimeError('Server did not start')
        for index,case in enumerate(cases):
            for provider in (['jev','deepseek'] if index%2==0 else ['deepseek','jev']):
                begin=time.perf_counter();deadline=begin+30;response={};status=0;headers={};attempts=0
                request_id=secrets.token_hex(16)
                for attempt in range(1,5 if provider=='jev' else 2):
                    remaining=deadline-time.perf_counter()
                    if remaining<=0:break
                    attempts=attempt;c=conns[provider]
                    c.timeout=remaining if provider=='jev' else 35
                    if c.sock:c.sock.settimeout(c.timeout)
                    at=dt.datetime.now(dt.timezone.utc).isoformat();astart=time.perf_counter();response={};headers={};status=0
                    try:
                        c.request('POST','/v1/systemone',body=json.dumps(case['request'],ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+keys[provider],'Content-Type':'application/json'})
                        resp=c.getresponse();status=resp.status;headers={k.lower():v for k,v in resp.getheaders()};raw=resp.read()
                        try:response=json.loads(raw)
                        except ValueError:response={}
                        if not isinstance(response,dict):response={}
                    except (OSError,http.client.HTTPException): c.close()
                    checks=grade(case,response) if status==200 else []
                    valid=status==200 and not any(x.get('invalid_answer') for x in checks)
                    if provider=='jev':
                        usage=response.get('usage') or {};inp,out=usage.get('input_tokens'),usage.get('output_tokens')
                        known=all(type(v) is int and v>=0 for v in (inp,out))
                        jev_events.append(dict(request_id=request_id,case_id=case['id'],provider='jev',model=response.get('model','jev-1.13.0'),started_at=at,attempt=attempt,http_status=status,latency_ms=round((time.perf_counter()-astart)*1000,2),outcome='success' if valid else 'failed',usage_known=known,input_tokens=inp,output_tokens=out,cached_tokens=None,raw_usage=usage))
                    if provider=='deepseek' or valid or (status not in (0,200,408,429) and status<500) or attempt==4:break
                    delay=.1*(2**(attempt-1))*(1+random.random()/2)
                    retry_after=headers.get('retry-after','')
                    try:delay=max(delay,float(retry_after))
                    except ValueError:
                        try:delay=max(delay,(parsedate_to_datetime(retry_after)-dt.datetime.now(dt.timezone.utc)).total_seconds())
                        except (ValueError,TypeError,OverflowError):pass
                    if delay>=deadline-time.perf_counter():break
                    time.sleep(delay)
                row=dict(provider=provider,id=case['id'],group=case['group'],questions=len(case['expected']),status=status,response=response,checks=grade(case,response) if status==200 else [],latency_ms=round((time.perf_counter()-begin)*1000,2),request_id=headers.get('x-request-id',request_id) if provider=='deepseek' else request_id,attempts=int(headers.get('x-upstream-attempts',attempts)))
                rows.append(row)
                print(provider,case['id'],status,row['latency_ms'],sum(c['pass'] for c in row['checks']),'/',row['questions'],flush=True)
    finally:
        for c in conns.values():c.close()
        proc.terminate();proc.wait(timeout=10);log.close()
        (reports/f'{prefix}-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
        (reports/f'{prefix}-jev-usage.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in jev_events))
    ds_events=[json.loads(line) for line in ledger_path.read_text().splitlines()]
    summary={'started_at':started,'finished_at':dt.datetime.now(dt.timezone.utc).isoformat(),'cases_sha256':hashlib.sha256(cases_bytes).hexdigest(),'pricing':PRICING,
        'methodology':os.environ.get('EVAL_DATASET_DESCRIPTION', 'Frozen synthetic regression set (previously used for tuning)') + '; sequential paired calls with alternating order, persistent connections, same host/time window, max3 retries/30s upstream budget. DeepSeek includes local proxy overhead. Warm cache not flushed; results are not cold-start or load-test measurements. Peak/offpeak are cost scenarios, not actual debit. All attempts including failures billed when usage is available.'}
    for provider,events in [('jev',jev_events),('deepseek',ds_events)]:
        pr=[r for r in rows if r['provider']==provider]
        summary[provider]=summarize(pr,events,provider)
        groups={}
        for group in sorted({r['group'] for r in pr}):
            gr=[r for r in pr if r['group']==group];ids={r['request_id'] for r in gr}
            groups[group]=summarize(gr,[e for e in events if e['request_id'] in ids],provider)
        summary[provider]['by_group']=groups
    templates = {}
    for e in ds_events:
        templates.setdefault(e['template_id'], []).append(e)
    summary['deepseek']['cache_reuse_by_template'] = []
    for template, events in templates.items():
        streak = longest = 0
        for event in events:
            streak = streak + 1 if (event.get('cached_tokens') or 0) > 0 else 0
            longest = max(longest, streak)
        summary['deepseek']['cache_reuse_by_template'].append(dict(template_id=template, calls=len(events),
            longest_consecutive_calls_with_any_cache_hit=longest,
            cached_tokens_sequence=[e.get('cached_tokens') for e in events],
            input_tokens_sequence=[e.get('input_tokens') for e in events]))
    events_by_request = {}
    for e in ds_events + jev_events:
        events_by_request.setdefault((e['provider'],e['request_id']), []).append(e)
    for row in rows:
        events = events_by_request.get((row['provider'],row['request_id']), [])
        scenarios = ['jev'] if row['provider']=='jev' else ['deepseek_peak','deepseek_offpeak']
        row['cost'] = {scenario:costs(events,scenario) for scenario in scenarios}
        row['ledger_complete'] = len(events)==row['attempts'] and len(events)>0
        if not row['ledger_complete']:
            for value in row['cost'].values():value['total_estimated_usd']=None
    (reports/f'{prefix}-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    (reports/f'{prefix}-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    lines=['# Jev / DeepSeek paired comparison','',summary['methodology'],'',f"UTC: {started} — {summary['finished_at']}",'', '| Metric | Jev | DeepSeek standard |','|---|---:|---:|']
    j,d=summary['jev'],summary['deepseek']
    for label,a,b in [('Successful requests',f"{j['successful_requests']}/{j['requests']}",f"{d['successful_requests']}/{d['requests']}"),('Correct judgments',f"{j['correct_judgments']}/{j['judgments']}",f"{d['correct_judgments']}/{d['judgments']}"),('P50 ms',j['latency_ms']['all_requests']['p50'],d['latency_ms']['all_requests']['p50']),('P95 ms',j['latency_ms']['all_requests']['p95'],d['latency_ms']['all_requests']['p95']),('Upstream attempts',j['upstream_attempts'],d['upstream_attempts']),('Estimated USD (DeepSeek peak)',j['cost']['jev']['total_estimated_usd'],d['cost']['deepseek_peak']['total_estimated_usd']),('Estimated USD (DeepSeek offpeak)',j['cost']['jev']['total_estimated_usd'],d['cost']['deepseek_offpeak']['total_estimated_usd']),('USD / 1k requests (peak)',j['cost']['jev']['usd_per_1000_requests'],d['cost']['deepseek_peak']['usd_per_1000_requests']),('USD / 1k correct judgments (peak)',j['cost']['jev']['usd_per_1000_correct_judgments'],d['cost']['deepseek_peak']['usd_per_1000_correct_judgments'])]:lines.append(f'| {label} | {a} | {b} |')
    lines += ['', 'Accuracy applies only to the selected dataset and protocol. HTTP success does not imply a correct judgment. Full results contain all failures and answers; ledgers contain each attempt and cache usage. Missing usage produces a null total, not zero cost.','', '[Jev prices](https://docs.typesafe.ai/models) · [DeepSeek prices](https://api-docs.deepseek.com/quick_start/pricing/)']
    (reports/f'{prefix}.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({p:{k:v for k,v in summary[p].items() if k!='by_group'} for p in ('jev','deepseek')},indent=2))
if __name__=='__main__':main()
