"""Paid, fixed development-subset ablation. Provider key is read from environment."""
import copy
import datetime
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time
import urllib.request
from accounting import costs
from compare_eval import percentile

ROOT = Path(__file__).resolve().parents[1]
ARMS = ['baseline_tool', 'neutral_tool', 'direct_off', 'direct_low', 'neutral_tool_low']
NEUTRAL = 'Answer the question supplied in the user message using its stated facts and the option descriptions in the tool schema. Call submit_decisions with a probability for every option. Probabilities must sum to 1. Return only the tool call.'
DIRECT = 'Answer the supplied question. Return only the exact answer label from the allowed labels. Do not include an explanation or any other text.'


def variants(case, baseline):
    result = {'baseline_tool': copy.deepcopy(baseline)}
    neutral = copy.deepcopy(baseline)
    neutral['messages'][0]['content'] = NEUTRAL
    result['neutral_tool'] = neutral
    labels = list(case['request']['questions']['answer']['criteria'])
    direct = {'model': baseline['model'], 'stream': False, 'thinking': {'type': 'disabled'}, 'max_tokens': 128,
              'messages': [{'role': 'system', 'content': DIRECT + ' Allowed labels: ' + json.dumps(labels)},
                           {'role': 'user', 'content': case['request']['state']}]}
    result['direct_off'] = direct
    low = copy.deepcopy(direct); low.update(thinking={'type': 'enabled'}, reasoning_effort='low', max_tokens=8192)
    result['direct_low'] = low
    low_tool = copy.deepcopy(neutral); low_tool.update(thinking={'type': 'enabled'}, reasoning_effort='low', max_tokens=8192, tool_choice='auto')
    result['neutral_tool_low'] = low_tool
    auto_off = copy.deepcopy(neutral); auto_off.update(tool_choice='auto', max_tokens=8192)
    result['neutral_tool_auto_off'] = auto_off
    long_off = copy.deepcopy(direct); long_off['max_tokens'] = 8192
    result['direct_off_long'] = long_off
    baseline_low = copy.deepcopy(baseline); baseline_low.update(thinking={'type': 'enabled'}, reasoning_effort='low', max_tokens=8192, tool_choice='auto')
    result['baseline_tool_low'] = baseline_low
    return result


def decode(arm, response, labels):
    choice = response['choices'][0]
    if choice.get('finish_reason') == 'length': raise ValueError('truncated')
    message = choice['message']
    if arm.startswith('direct_'):
        answer = (message.get('content') or '').strip()
        if answer not in labels: raise ValueError('invalid label')
        return answer
    calls = message.get('tool_calls') or []
    if choice.get('finish_reason') != 'tool_calls' or len(calls) != 1 or calls[0].get('type') != 'function' or calls[0]['function']['name'] != 'submit_decisions': raise ValueError('missing or wrong tool')
    payload = json.loads(calls[0]['function']['arguments'])
    if set(payload) != {'answers'} or set(payload['answers']) != {'q0'}: raise ValueError('invalid envelope')
    probs = payload['answers']['q0']
    if not isinstance(probs, dict) or set(probs) != set(labels): raise ValueError('invalid options')
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in probs.values()): raise ValueError('invalid probability')
    if abs(sum(probs.values())-1) > .02: raise ValueError('invalid probability sum')
    return max(sorted(labels), key=lambda k: probs[k])


def capture(cases):
    bodies = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length']))); bodies.append(payload)
            props = payload['tools'][0]['function']['parameters']['properties']['answers']['properties']['q0']['properties']
            answers = {'q0': {k: float(i == 0) for i, k in enumerate(props)}}
            response = {'choices': [{'finish_reason': 'tool_calls', 'message': {'tool_calls': [{'type': 'function', 'function': {'name': 'submit_decisions', 'arguments': json.dumps({'answers': answers})}}]}}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}
            raw = json.dumps(response).encode(); self.send_response(200); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    local = secrets.token_urlsafe(20)
    env = dict(os.environ, DEEPSEEK_API_KEY='capture-only', PROXY_API_KEY=local, LISTEN_ADDR=f'127.0.0.1:{port}', DEEPSEEK_BASE_URL=f'http://127.0.0.1:{server.server_port}', DEEPSEEK_MODEL='deepseek-flash', OUTPUT_MODE='standard', PROMPT_MODE='standard', MAX_RETRIES='0', USAGE_LEDGER_PATH='')
    proc = subprocess.Popen([str(ROOT/'bin/dsk-jev')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=.2): break
            except OSError: time.sleep(.05)
        else: raise RuntimeError('capture proxy did not start')
        for case in cases:
            request = urllib.request.Request(f'http://127.0.0.1:{port}/v1/systemone', data=json.dumps(case['request']).encode(), headers={'Authorization': 'Bearer '+local, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=5) as response: response.read()
    finally:
        proc.terminate(); proc.wait(timeout=10); server.shutdown(); server.server_close()
    if len(bodies) != len(cases): raise ValueError('capture count mismatch')
    return bodies


def main():
    prefix = os.environ.get('DIAG_PREFIX', 'bbh-diagnostic-v1')
    if not prefix.replace('-', '').replace('_', '').isalnum(): raise ValueError('invalid prefix')
    dest = ROOT/'reports'/prefix; dest.mkdir(exist_ok=False)
    arms = os.environ.get('DIAG_ARMS', ','.join(ARMS)).split(',')
    allowed = set(ARMS) | {'neutral_tool_auto_off', 'direct_off_long', 'baseline_tool_low'}
    if not arms or len(set(arms)) != len(arms) or not set(arms) <= allowed: raise ValueError('invalid arms')
    per_task = int(os.environ.get('DIAG_PER_TASK', '4'))
    if not 1 <= per_task <= 10: raise ValueError('invalid per-task count')
    dev_path = ROOT/'evals/public-bbh/dev.json'; all_cases = json.loads(dev_path.read_text())
    # First N in the pre-existing hash order per task, independent of previous test outcomes.
    cases = []; counts = {}
    for c in all_cases:
        if counts.get(c['group'], 0) < per_task:
            cases.append(c); counts[c['group']] = counts.get(c['group'], 0)+1
    baselines = capture(cases)
    manifest = {'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'cases': [c['id'] for c in cases], 'dev_sha256': hashlib.sha256(dev_path.read_bytes()).hexdigest(), 'arms': arms, 'per_task': per_task,
                'methodology': f'{len(cases)} dev cases, first {per_task} per task in frozen dev-file order; {len(arms)} arms rotated by case index; sequential persistent HTTPS, no retries, 60s timeout each. Baseline payload captured from actual Go proxy then replayed directly. Gold labels never submitted. Low thinking uses 8192-token cap and tool auto where applicable; forced tool unsupported with thinking. Latency is direct upstream, not proxy end-to-end. Public data and single-run diagnostic, not held-out proof. Raw reasoning text omitted; completion usage includes reasoning.'}
    (dest/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (dest/'baseline-payloads.json').write_text(json.dumps(baselines, indent=2)+'\n')
    conn = http.client.HTTPSConnection('api.deepseek.com', timeout=60); rows = []
    try:
        with (dest/'results.jsonl').open('w') as output:
            for i, (case, baseline) in enumerate(zip(cases, baselines)):
                payloads = variants(case, baseline)
                for arm in arms[i % len(arms):] + arms[:i % len(arms)]:
                    start = time.perf_counter(); response = {}; status = 0; answer = None; error = None
                    try:
                        conn.request('POST', '/beta/chat/completions', body=json.dumps(payloads[arm]).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+os.environ['DEEPSEEK_API_KEY']})
                        res = conn.getresponse(); status = res.status; response = json.loads(res.read())
                        if status == 200: answer = decode(arm, response, case['request']['questions']['answer']['criteria'])
                        else: error = 'upstream HTTP ' + str(status)
                    except (OSError, http.client.HTTPException, ValueError, KeyError, TypeError, IndexError) as exc:
                        error = type(exc).__name__ + ': ' + str(exc); conn.close()
                    usage = response.get('usage', {})
                    event = {'input_tokens': usage.get('prompt_tokens'), 'output_tokens': usage.get('completion_tokens'), 'cached_tokens': usage.get('prompt_cache_hit_tokens', (usage.get('prompt_tokens_details') or {}).get('cached_tokens'))}
                    reasoning_chars = 0
                    for item in response.get('choices', []):
                        reasoning = item.get('message', {}).pop('reasoning_content', None)
                        reasoning_chars += len(reasoning or '')
                    row = {'id': case['id'], 'group': case['group'], 'arm': arm, 'status': status, 'valid': answer is not None, 'answer': answer, 'expected': case['expected']['answer'], 'correct': answer == case['expected']['answer'], 'error': error, 'latency_ms': round((time.perf_counter()-start)*1000, 2), 'usage': event, 'raw_usage': usage, 'reasoning_characters': reasoning_chars, 'response': response}
                    rows.append(row); output.write(json.dumps(row)+'\n'); output.flush()
                    print(i+1, arm, case['group'], status, row['correct'], row['latency_ms'], error or '', flush=True)
    finally: conn.close()
    summary = {}
    for arm in arms:
        rr = [r for r in rows if r['arm']==arm]; events = [r['usage'] for r in rr]
        summary[arm] = {'requests':len(rr), 'valid':sum(r['valid'] for r in rr), 'correct':sum(r['correct'] for r in rr), 'p50_ms':percentile([r['latency_ms'] for r in rr], .5), 'p95_ms':percentile([r['latency_ms'] for r in rr], .95), 'cost':{s:costs(events,s) for s in ['deepseek_peak','deepseek_offpeak']}, 'output_tokens_known':sum(e['output_tokens'] or 0 for e in events), 'by_group':{g:sum(r['correct'] for r in rr if r['group']==g) for g in sorted(counts)}}
    (dest/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))

if __name__ == '__main__': main()
