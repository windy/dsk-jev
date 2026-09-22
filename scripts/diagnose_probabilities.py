"""Small live diagnostic. Requires DEEPSEEK_API_KEY. Saves only synthetic data/results."""
import json,os,re,urllib.request,concurrent.futures
from pathlib import Path
root=Path(__file__).resolve().parents[1]
cases=json.loads((root/'evals/cases.json').read_text())
prompt=re.search(r'const systemPrompt = `(.*?)`',(root/'internal/decision/server.go').read_text(),re.S).group(1)
def run(case):
 qs=[]
 for i,(id,q) in enumerate(sorted(case['request']['questions'].items())):
  q=dict(q);q['id']=f'q{i}'
  if q['type']=='choice':q['criteria']=dict(sorted(q['criteria'].items()))
  elif q['type']=='score':q['criteria']={str(i):v for i,v in enumerate(q['criteria'])}
  qs.append(q)
 def obj(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
 props={}
 for q in qs:
  if q['type']=='noul':props[q['id']]={'type':'number','minimum':0,'maximum':1,'description':'Probability of yes/true. '+json.dumps(q['instructions'],ensure_ascii=False)+' Criteria: '+json.dumps(q.get('criteria'),ensure_ascii=False)}
  else:
   props[q['id']]=obj({k:{'type':'number','minimum':0,'maximum':1,'description':json.dumps(v,ensure_ascii=False)} for k,v in q['criteria'].items()})
   props[q['id']]['description']=q['type']+': '+json.dumps(q['instructions'],ensure_ascii=False)+' Return probabilities summing to 1 across all keys.'
 schema=obj({'answers':obj(props)})
 payload={'model':'deepseek-flash','thinking':{'type':'disabled'},'tools':[{'type':'function','function':{'name':'submit_decisions','strict':True,'description':'Return typed decision probability distributions for the supplied state.','parameters':schema}}],'tool_choice':{'type':'function','function':{'name':'submit_decisions'}},'max_tokens':128+sum(32+(sum(24+len(k) for k in q['criteria']) if q['type']!='noul' else 0) for q in qs),'stream':False,'messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps(case['request']['state'],ensure_ascii=False,separators=(',',':'))}]}
 req=urllib.request.Request('https://api.deepseek.com/beta/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY'],'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=40) as r:result=json.load(r)
 content=result['choices'][0]['message']['tool_calls'][0]['function']['arguments'];issues=[]
 try:
  answers=json.loads(content)['answers']
  if len(answers)!=len(qs):issues.append('answer count mismatch')
  for i,q in enumerate(qs):
   a=answers[q['id']]
   if q['type']=='noul':
    if not isinstance(a,(float,int)) or isinstance(a,bool) or not 0<=a<=1:issues.append(f'q{i}: invalid noul')
   elif not isinstance(a,dict):issues.append(f'q{i}: expected keyed object')
   else:
    if len(a)!=len(q['criteria']):issues.append(f'q{i}: expected {len(q["criteria"])} probabilities, got {len(a)}')
    if set(a)!=set(q['criteria']):issues.append(f'q{i}: option keys mismatch')
    a=list(a.values())
    if all(type(v) in (float,int) for v in a):
     if any(not 0<=v<=1 for v in a):issues.append(f'q{i}: out-of-range probability')
     if abs(sum(a)-1)>0.02:issues.append(f'q{i}: sum={sum(a):.5f}')
    else:issues.append(f'q{i}: invalid probability type')
 except (ValueError,KeyError,TypeError):issues.append('invalid JSON/shape')
 return {'id':case['id'],'question_order':list(sorted(case['request']['questions'])),'compiled_questions':qs,'content':content,'issues':issues,'usage':result['usage']}
selected=[c for c in cases if c['id'] in ['refund_yes','outage','bug','demo','sales_deadline','choice_255']]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:results=list(ex.map(run,selected))
(root/'reports/v2-probability-diagnostics.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
for r in results:print(r['id'],r['issues'],r['content'][:350])
