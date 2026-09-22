"""Deterministic visual fixtures and an opt-in paid end-to-end vision smoke test.
--fixtures-only creates the example without making any API calls.
Otherwise requires DEEPSEEK_API_KEY and a built bin/dsk-jev.
"""
import base64,hashlib,http.client,json,math,os,secrets,socket,struct,subprocess,sys,time,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def panel(swapped):
    width=height=512;scan=bytearray()
    for y in range(height):
        scan.append(0)
        for x in range(width):
            rgb=(255,255,255)
            if (x-130)**2+(y-256)**2<=75**2:rgb=(30,90,220) if swapped else (220,35,35)
            if 300<=x<420 and (75<=y<195 or 317<=y<437):rgb=(220,35,35) if swapped else (30,90,220)
            scan.extend(rgb)
    def chunk(name,data):return struct.pack('!I',len(data))+name+data+struct.pack('!I',zlib.crc32(name+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(scan)))+chunk(b'IEND',b'')

def fixture():
    imgs=[panel(False),panel(True)]
    folder=ROOT/'examples/images';folder.mkdir(exist_ok=True)
    for name,data in zip(('panel-a.png','panel-b.png'),imgs):(folder/name).write_bytes(data)
    refs=[dict(url='data:image/png;base64,'+base64.b64encode(data).decode(),detail='low') for data in imgs]
    request=dict(model='jev-latest',state='Answer the questions using the supplied image.',images=[refs[0]],questions={
        'circle_color':dict(type='choice',instructions='What is the color of the circle?',criteria={'red':'Red','blue':'Blue','other':'Any other color'}),
        'two_squares':dict(type='noul',instructions='Are exactly two squares visible?'),
        'shape_count':dict(type='score',instructions='How many colored shapes are visible? Count circles and squares.',criteria=['Zero','One','Two','Three','Four'])})
    (ROOT/'examples/vision.json').write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n')
    return imgs,refs,request

def main():
    imgs,refs,request=fixture()
    if '--fixtures-only' in sys.argv:return
    if not os.environ.get('DEEPSEEK_API_KEY'):raise SystemExit('Set DEEPSEEK_API_KEY to run the paid smoke test')
    prefix=os.environ.get('VISION_EVAL_PREFIX','vision-smoke')
    if not prefix or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in prefix):raise ValueError('invalid prefix')
    folder=ROOT/'reports'/prefix;folder.mkdir(exist_ok=False)
    results=[];events=[];servers=[]
    try:
        for mode in ('standard','fast'):
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            key=secrets.token_urlsafe(24);log=open(folder/f'{mode}.log','w');ledger=folder/f'{mode}-usage.jsonl'
            env=dict(os.environ,PROXY_API_KEY=key,LISTEN_ADDR=f'127.0.0.1:{port}',DEEPSEEK_BASE_URL='https://api.deepseek.com/beta',DEEPSEEK_MODEL='deepseek-flash',OUTPUT_MODE=mode,PROMPT_MODE='standard',MAX_RETRIES='3',UPSTREAM_TIMEOUT='30s',USAGE_LEDGER_PATH=str(ledger))
            proc=subprocess.Popen([os.environ.get('DSK_JEV_BINARY',str(ROOT/'bin/dsk-jev'))],env=env,stdout=subprocess.DEVNULL,stderr=log)
            conn=http.client.HTTPConnection('127.0.0.1',port,timeout=35);servers.append((proc,log,conn,ledger))
            for _ in range(100):
                try:conn.request('GET','/healthz');r=conn.getresponse();r.read();break
                except OSError:conn.close();time.sleep(.05)
            else:raise RuntimeError('server failed to start')
            samples=[]
            for index in (0,1):samples.append((f'panel-{index+1}',dict(request,images=[refs[index]]),{'circle_color':['red','blue'][index],'two_squares':True,'shape_count':3}))
            samples.append(('two-images',dict(model='jev-latest',state='Compare the two supplied images in order.',images=refs,questions={'changed':dict(type='noul',instructions='Is the circle a different color in the second image compared with the first?')}),{'changed':True}))
            for name,body,expected in samples:
                begin=time.perf_counter();conn.request('POST','/v1/systemone',json.dumps(body).encode(),{'Authorization':'Bearer '+key,'Content-Type':'application/json'});r=conn.getresponse();response=json.loads(r.read())
                row=dict(mode=mode,case=name,status=r.status,latency_ms=round((time.perf_counter()-begin)*1000,2),attempts=int(r.getheader('X-Upstream-Attempts','0')),request_id=r.getheader('X-Request-ID'),template=r.getheader('X-Upstream-Template'),response=response,expected=expected,checks=[])
                for qid,want in expected.items():
                    a=response.get('answers',{}).get(qid,{})
                    actual=a.get('choice') if a.get('type')=='choice' else ((a['noul']>=.5) if a.get('type')=='noul' else (math.floor(a['score']+.5) if a.get('type')=='score' else None))
                    row['checks'].append(dict(question=qid,expected=want,actual=actual,passed=actual==want))
                results.append(row);print(mode,name,r.status,row['latency_ms'],row['checks'],flush=True)
    finally:
        for proc,log,conn,ledger in servers:
            conn.close();proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            log.close()
            if ledger.exists():events.extend(json.loads(line) for line in ledger.read_text().splitlines())
        (folder/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    summary=dict(requests=len(results),successful_requests=sum(r['status']==200 for r in results),correct_judgments=sum(c['passed'] for r in results for c in r['checks']),judgments=sum(len(r['checks']) for r in results),upstream_attempts=len(events),upstream_image_counts=[e['image_count'] for e in events],fixtures_sha256=[hashlib.sha256(data).hexdigest() for data in imgs],scope='Synthetic visual smoke only: two color-swapped panels and multi-image comparison, both output modes. No evidence of real-world visual accuracy or superiority to another model.')
    (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    if summary['requests']!=6 or summary['successful_requests']!=6 or summary['correct_judgments']!=14:raise SystemExit(1)
if __name__=='__main__':main()
