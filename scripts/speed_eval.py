"""Interleaved standard vs experimental fast upstream encoding; same public API."""
import datetime as dt
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time
from compare_eval import grade,summarize,percentile
ROOT=Path(__file__).resolve().parents[1]

def main():
 prefix=os.environ.get('EVAL_PREFIX','speed-v6')
 if not re.fullmatch(r'[\w-]+',prefix):raise ValueError('invalid prefix')
 reports=ROOT/'reports'
 cases=[];hashes={}
 for name in ('cases','holdout'):
  raw=(ROOT/f'evals/{name}.json').read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest()
  for c in json.loads(raw):cases.append(dict(c,suite=name))
 if os.environ.get('EVAL_LIMIT'):cases=cases[:int(os.environ['EVAL_LIMIT'])]
 servers={};rows=[];start=dt.datetime.now(dt.timezone.utc).isoformat()
 try:
  for mode in ('standard','fast'):
   ledger=reports/f'{prefix}-{mode}-usage.jsonl'
   if ledger.exists():raise RuntimeError('Use a new prefix')
   with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
   key=secrets.token_urlsafe(24);log=open(reports/f'{prefix}-{mode}-server.log','w')
   env=dict(os.environ,PROXY_API_KEY=key,LISTEN_ADDR=f'127.0.0.1:{port}',USAGE_LEDGER_PATH=str(ledger),DEEPSEEK_BASE_URL='https://api.deepseek.com/beta',DEEPSEEK_MODEL='deepseek-flash',OUTPUT_MODE=mode,PROMPT_MODE='standard',MAX_RETRIES='3',UPSTREAM_TIMEOUT='30s')
   proc=subprocess.Popen([os.environ.get('DSK_JEV_BINARY',str(ROOT/'bin/dsk-jev'))],env=env,stdout=subprocess.DEVNULL,stderr=log)
   conn=http.client.HTTPConnection('127.0.0.1',port,timeout=35)
   servers[mode]=(proc,log,conn,key,ledger)
   for _ in range(100):
    try:conn.request('GET','/healthz');resp=conn.getresponse();resp.read();break
    except OSError:conn.close();time.sleep(.05)
   else:raise RuntimeError('server failed to start')
  for index,case in enumerate(cases):
   for mode in (('standard','fast') if index%2==0 else ('fast','standard')):
    proc,log,conn,key,ledger=servers[mode];begin=time.perf_counter();response={};status=0;headers={}
    try:
     conn.request('POST','/v1/systemone',body=json.dumps(case['request'],ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
     resp=conn.getresponse();status=resp.status;headers={k.lower():v for k,v in resp.getheaders()};response=json.loads(resp.read())
    except (OSError,http.client.HTTPException,ValueError):conn.close()
    row=dict(mode=mode,id=case['id'],suite=case['suite'],group=case['group'],questions=len(case['expected']),status=status,response=response,checks=grade(case,response) if status==200 else [],request_id=headers.get('x-request-id'),attempts=int(headers.get('x-upstream-attempts',0)),latency_ms=round((time.perf_counter()-begin)*1000,2))
    rows.append(row)
    print(mode,case['suite'],case['id'],status,row['latency_ms'],'ms',sum(c['pass'] for c in row['checks']),'/',row['questions'],flush=True)
 finally:
  for proc,log,conn,key,ledger in servers.values():
   conn.close();proc.terminate()
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   log.close()
  (reports/f'{prefix}-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
 summary={'encoding':'integer-arrays-v1; noul unscaled; sparse pairs at >=16 options','started_at':start,'finished_at':dt.datetime.now(dt.timezone.utc).isoformat(),'cases_sha256':hashes,
 'methodology':'Interleaved sequential A/B on same host, persistent connections, standard vs fast encoding (also shorter prompt). 3 retries/30s upstream budget. Warm cache not flushed. Existing regression and historical holdout, not unseen blind tests. USD costs are public peak/offpeak estimates. First-byte timings are HTTP bytes, not generated-token TTFT.'}
 for mode in ('standard','fast'):
  events=[json.loads(x) for x in servers[mode][4].read_text().splitlines()];rr=[r for r in rows if r['mode']==mode]
  s=summarize(rr,events,'deepseek');s['by_suite']={}
  for suite in ('cases','holdout'):
   sr=[r for r in rr if r['suite']==suite];ids={r['request_id'] for r in sr};s['by_suite'][suite]=summarize(sr,[e for e in events if e['request_id'] in ids],'deepseek')
  s['network']={'reused_connections':sum(e['network']['connection_reused'] for e in events),'observed_connections':sum(e['network']['connection_observed'] for e in events)}
  for key in ('get_connection_ms','first_byte_ms','after_first_byte_ms'):
   values=[e['network'][key] for e in events if e['network'][key] is not None];s['network'][key]={'p50':percentile(values,.5),'p95':percentile(values,.95)}
  s['reasoning_tokens']=sum((e.get('raw_usage',{}).get('completion_tokens_details') or {}).get('reasoning_tokens',0) for e in events)
  s['reasoning_tokens_field_present_attempts']=sum('reasoning_tokens' in (e.get('raw_usage',{}).get('completion_tokens_details') or {}) for e in events)
  if not s['reasoning_tokens_field_present_attempts']:s['reasoning_tokens']=None
  summary[mode]=s
 pairs={}
 for row in rows:pairs.setdefault((row['suite'],row['id']),{})[row['mode']]=row
 deltas=[]
 for pair in pairs.values():
  if len(pair)==2:deltas.append(pair['fast']['latency_ms']-pair['standard']['latency_ms'])
 summary['paired_latency_delta_ms']={'median':percentile(deltas,.5),'fast_wins':sum(x<0 for x in deltas),'pairs':len(deltas)}
 (reports/f'{prefix}-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 a,b=summary['standard'],summary['fast']
 lines=['# Standard vs fast output encoding','',summary['methodology'],'',f"UTC: {start} — {summary['finished_at']}",'','| Metric | Standard | Fast |','|---|---:|---:|']
 for name,x,y in [('Success',f"{a['successful_requests']}/{a['requests']}",f"{b['successful_requests']}/{b['requests']}"),('Correct judgments',f"{a['correct_judgments']}/{a['judgments']}",f"{b['correct_judgments']}/{b['judgments']}"),('P50 ms',a['latency_ms']['all_requests']['p50'],b['latency_ms']['all_requests']['p50']),('P95 ms',a['latency_ms']['all_requests']['p95'],b['latency_ms']['all_requests']['p95']),('Output tokens',a['usage_known_subtotals']['output_tokens'],b['usage_known_subtotals']['output_tokens']),('Attempts',a['upstream_attempts'],b['upstream_attempts']),('Cache hit ratio',a['cache_hit_ratio'],b['cache_hit_ratio']),('Peak USD / 1k requests',a['cost']['deepseek_peak']['usd_per_1000_requests'],b['cost']['deepseek_peak']['usd_per_1000_requests']),('Reused connections',a['network']['reused_connections'],b['network']['reused_connections'])]:lines.append(f'| {name} | {x} | {y} |')
 lines+=['','Fast mode is experimental: choice/score use dense thousandth-integer arrays or sparse [index,weight] arrays at >=16 options; noul remains an unscaled probability. Go reconstructs every public probability key and derives confidence/score normally. This changes model conditioning and probability precision; passing classification accuracy does not establish calibrated probabilities. Default remains standard.']
 (reports/f'{prefix}.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
