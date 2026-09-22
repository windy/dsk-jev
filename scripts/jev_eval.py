"""Run with JEV_API_KEY in environment. No keys are persisted.
Uses bounded concurrent requests, no retries. Reports synthetic-set accuracy only.
"""
import concurrent.futures,json,math,os,re,secrets,socket,subprocess,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
cases=json.loads((ROOT/'evals/cases.json').read_text())
key=os.environ['JEV_API_KEY']
def run(case):
 start=time.perf_counter();record={'id':case['id'],'group':case['group'],'questions':len(case['expected'])}
 req=urllib.request.Request('https://api.typesafe.ai/v1/systemone',data=json.dumps(case['request'],ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=40) as r:record.update(status=r.status,response=json.load(r))
 except urllib.error.HTTPError as e:record.update(status=e.code,error=e.read().decode().replace(key, '[REDACTED]'))
 except Exception as e:record.update(status=0,error=type(e).__name__)
 record['latency_ms']=round((time.perf_counter()-start)*1000,2)
 checks=[]
 if record['status']==200:
  answers=record['response']['answers']
  for qid,expected in case['expected'].items():
   a=answers[qid];typ=a['type']
   actual=a['choice'] if typ=='choice' else (a['noul']>=0.5 if typ=='noul' else math.floor(a['score']+0.5))
   checks.append({'question':qid,'type':typ,'expected':expected,'actual':actual,'pass':actual==expected})
 record['checks']=checks
 return record
results=[]
try:
 # Keep repeats sequential and batch-size experiments sequential; semantics concurrency=3.
 parallel=[c for c in cases if c['group'] not in ('repeat','batch')]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
  for row in ex.map(run,parallel):
   results.append(row);print(row['id'],row['status'],row['latency_ms'],'ms',sum(x['pass'] for x in row['checks']),'/',row['questions'],flush=True)
 for case in cases:
  if case['group'] in ('repeat','batch'):
   row=run(case);results.append(row);print(row['id'],row['status'],row['latency_ms'],'ms',sum(x['pass'] for x in row['checks']),'/',row['questions'],flush=True)
finally:
 (ROOT/'reports/jev-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
def pct(values,p):return sorted(values)[max(0,math.ceil(len(values)*p)-1)] if values else None
ok=[r for r in results if r['status']==200];checks=[c for r in ok for c in r['checks']]
summary={'requests':len(results),'successful_requests':len(ok),'judgments':sum(r['questions'] for r in results),'correct_judgments':sum(c['pass'] for c in checks),'completed_judgments':len(checks),'latency_ms':{'p50':pct([r['latency_ms'] for r in ok],.5),'p95':pct([r['latency_ms'] for r in ok],.95)},'usage':{k:sum(r['response']['usage'][k] for r in ok) for k in ['input_tokens','output_tokens']},'by_type':{t:{'correct':sum(c['pass'] for c in checks if c['type']==t),'total':sum(c['type']==t for c in checks)} for t in ['choice','score','noul']},'failures':[{'id':r['id'],'status':r['status'],'checks':[c for c in r['checks'] if not c['pass']]} for r in results if r['status']!=200 or any(not c['pass'] for c in r['checks'])]}
summary['usage_scope']='Successful Jev requests, no retries.'
summary['methodology']='Same frozen synthetic cases, thresholds, concurrency=3 for semantic/boundary, sequential batch/repeats as DeepSeek baseline. urllib.request with no explicit connection pool. Measured from same host at a different time.'
(ROOT/'reports/jev-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
