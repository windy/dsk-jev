"""Continuous prefix reuse with changing states; no local result cache or retries by harness."""
import json,os,secrets,socket,subprocess,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
questions={
 'product':{'type':'choice','instructions':'订单中的商品属于哪一类？','criteria':{'phone':'智能手机','laptop':'笔记本电脑','camera':'数码相机'}},
 'paid':{'type':'noul','instructions':'订单记录是否明确标记为已付款？仅依据paid字段。'},
 'priority':{'type':'score','instructions':'按订单要求的发货速度评级。','criteria':['不着急，普通发货','希望尽快，但无确定期限','明确要求今天发货']}}
servers=[];results=[]
def start(mode):
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 key=secrets.token_urlsafe(24);log=open(ROOT/f'reports/cache-{mode}-server.log','w')
 env=dict(os.environ,PROXY_API_KEY=key,DEEPSEEK_BASE_URL='https://api.deepseek.com/beta',DEEPSEEK_MODEL='deepseek-flash',LISTEN_ADDR=f'127.0.0.1:{port}',PROMPT_MODE=mode,MAX_RETRIES='3')
 p=subprocess.Popen([os.environ['DSK_JEV_BINARY']],env=env,stdout=subprocess.DEVNULL,stderr=log);servers.append((p,log))
 for _ in range(100):
  try:urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz',timeout=.2).close();return port,key
  except OSError:time.sleep(.05)
 raise RuntimeError('server did not start')
def phase(server,label,n,start_index):
 port,key=server
 for i in range(n):
  index=start_index+i;kind=index%3
  state={'order_id':f'ORDER-{index:04}','product':['智能手机','笔记本电脑','数码相机'][kind],'paid':index%2==0,'shipping':['普通发货即可，不急','请尽快安排发货','请今天发货'][kind]}
  body={'model':'jev-latest','state':state,'questions':questions}
  req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/systemone',data=json.dumps(body,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
  row={'phase':label,'sequence':i+1,'state':state};t=time.perf_counter()
  try:
   with urllib.request.urlopen(req,timeout=40) as r:
    row.update(status=r.status,template=r.headers['X-Upstream-Template'],attempts=int(r.headers['X-Upstream-Attempts']),cached_tokens=int(r.headers['X-Upstream-Cached-Tokens']),response=json.load(r))
   u=row['response']['usage'];row['hit_ratio']=row['cached_tokens']/u['input_tokens']
   row['estimated_peak_usd']=((u['input_tokens']-row['cached_tokens'])*.3+row['cached_tokens']*.006+u['output_tokens']*1.2)/1e6
  except urllib.error.HTTPError as e:row.update(status=e.code,error=e.read().decode())
  row['latency_ms']=round((time.perf_counter()-t)*1000,2);results.append(row)
  print(label,i+1,row['status'],row.get('cached_tokens'),row.get('response',{}).get('usage'),row['latency_ms'],flush=True)
try:
 standard=start('standard');phase(standard,'standard-continuous',12,0)
 compact=start('compact');phase(compact,'compact-continuous',12,12)
 phase(standard,'standard-revisit',4,24)
finally:
 for p,log in servers:
  p.terminate()
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  log.close()
 (ROOT/'reports/cache-reuse-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
