"""Run with DEEPSEEK_API_KEY in environment. No keys are persisted.
Uses bounded concurrent requests; server retries are included in totals. Reports synthetic-set accuracy only.
"""
import concurrent.futures,json,math,os,re,secrets,socket,subprocess,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
cases=json.loads(Path(os.environ.get('EVAL_CASES',str(ROOT/'evals/cases.json'))).read_text())
prefix=os.environ.get('EVAL_PREFIX','live')
if not re.fullmatch(r'[a-zA-Z0-9_-]+',prefix):raise ValueError('invalid EVAL_PREFIX')
key=os.environ['DEEPSEEK_API_KEY'];local=secrets.token_urlsafe(24)
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
env=dict(os.environ,PROXY_API_KEY=local,LISTEN_ADDR=f'127.0.0.1:{port}',DEEPSEEK_BASE_URL='https://api.deepseek.com/beta',DEEPSEEK_MODEL='deepseek-flash')
logfile=open(ROOT/f'reports/{prefix}-server.log','w')
p=subprocess.Popen([os.environ.get('DSK_JEV_BINARY', str(ROOT/'bin/dsk-jev'))],env=env,stdout=subprocess.DEVNULL,stderr=logfile)
def run(case):
 start=time.perf_counter();record={'id':case['id'],'group':case['group'],'questions':len(case['expected'])}
 req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/systemone',data=json.dumps(case['request'],ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+local,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=40) as r:
   record.update(status=r.status,response=json.load(r));record['upstream_attempts']=int(r.headers.get('X-Upstream-Attempts','1'));record['cached_input_tokens']=int(r.headers.get('X-Upstream-Cached-Tokens','0'))
 except urllib.error.HTTPError as e:
  record.update(status=e.code,error=e.read().decode(),upstream_attempts=int(e.headers.get('X-Upstream-Attempts','0')),cached_input_tokens=int(e.headers.get('X-Upstream-Cached-Tokens','0')))
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
 for _ in range(100):
  try:urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz',timeout=.2).close();break
  except OSError:time.sleep(.05)
 else:raise RuntimeError('server did not start')
 # Keep repeats sequential and batch-size experiments sequential; semantics concurrency=3.
 parallel=[c for c in cases if c['group'] not in ('repeat','batch')]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
  for row in ex.map(run,parallel):
   results.append(row);print(row['id'],row['status'],row['latency_ms'],'ms',sum(x['pass'] for x in row['checks']),'/',row['questions'],flush=True)
 for case in cases:
  if case['group'] in ('repeat','batch'):
   row=run(case);results.append(row);print(row['id'],row['status'],row['latency_ms'],'ms',sum(x['pass'] for x in row['checks']),'/',row['questions'],flush=True)
finally:
 p.terminate();p.wait(timeout=10);logfile.close()
 (ROOT/f'reports/{prefix}-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
def pct(values,p):return sorted(values)[max(0,math.ceil(len(values)*p)-1)] if values else None
ok=[r for r in results if r['status']==200];checks=[c for r in ok for c in r['checks']]
summary={'requests':len(results),'successful_requests':len(ok),'judgments':sum(r['questions'] for r in results),'correct_judgments':sum(c['pass'] for c in checks),'completed_judgments':len(checks),'latency_ms':{'p50':pct([r['latency_ms'] for r in ok],.5),'p95':pct([r['latency_ms'] for r in ok],.95)},'usage':{k:sum(r['response']['usage'][k] for r in ok) for k in ['input_tokens','output_tokens']},'by_type':{t:{'correct':sum(c['pass'] for c in checks if c['type']==t),'total':sum(c['type']==t for c in checks)} for t in ['choice','score','noul']},'failures':[{'id':r['id'],'status':r['status'],'checks':[c for c in r['checks'] if not c['pass']]} for r in results if r['status']!=200 or any(not c['pass'] for c in r['checks'])]}
summary['successful_cached_input_tokens']=sum(r.get('cached_input_tokens',0) for r in ok)
summary['total_upstream_attempts']=sum(r.get('upstream_attempts',0) for r in results)
summary['retried_requests']=sum(r.get('upstream_attempts',0)>1 for r in results)
summary['retry_config']={'max_retries':env.get('MAX_RETRIES','3'),'prompt_mode':env.get('PROMPT_MODE','standard')}
logs=(ROOT/f'reports/{prefix}-server.log').read_text()
summary['upstream_usage_all_parsed_responses']={k:sum(int(v) for v in re.findall(r'\b'+k+r'=(\d+)',logs)) for k in ['input_tokens','cached_tokens','output_tokens']}
summary['usage_scope']='Response usage is cumulative across attempts for successful requests; upstream_usage_all_parsed_responses includes all logged attempts (zero tokens when usage unknown).'
summary['unknown_usage_attempts']=logs.count('usage_known=false')
(ROOT/f'reports/{prefix}-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
