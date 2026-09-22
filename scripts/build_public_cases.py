"""Reproducible BBH subset, selected before running either provider. No API keys."""
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = '9ee07bd481feebf959a6b59d61ea57bdcf30964d'
BASE = f'https://raw.githubusercontent.com/suzgunmirac/BIG-Bench-Hard/{REVISION}/'
TASKS = ['boolean_expressions', 'causal_judgement', 'date_understanding',
         'disambiguation_qa', 'logical_deduction_three_objects',
         'logical_deduction_seven_objects', 'tracking_shuffled_objects_three_objects',
         'tracking_shuffled_objects_seven_objects', 'sports_understanding', 'web_of_lies']
SEED = 'dsk-jev-bbh-20260922-v1'


def adapt(task, index, example):
    prompt, target = example['input'], example['target']
    options = dict(re.findall(r'^\(([A-Z])\) (.+)$', prompt, re.M))
    if options:
        match = re.fullmatch(r'\(([A-Z])\)', target)
        if not match or match[1] not in options:
            raise ValueError('Unknown multiple-choice target')
        answer = match[1]
    else:
        labels = ['True', 'False'] if task == 'boolean_expressions' else (['yes', 'no'] if task == 'sports_understanding' else ['Yes', 'No'])
        options = {label: label for label in labels}
        if target not in options:
            raise ValueError('Unknown binary target')
        answer = target
    return {'id': f'bbh/{task}/{index}', 'group': task,
            'source': {'revision': REVISION, 'path': f'bbh/{task}.json', 'index': index},
            'request': {'model': 'jev-1.13.0', 'state': prompt, 'questions': {
                'answer': {'type': 'choice', 'instructions': 'Answer the question in the state. Select the correct option.', 'criteria': options}}},
            'expected': {'answer': answer}}


def main():
    dest = ROOT / 'evals/public-bbh'; dest.mkdir(parents=True, exist_ok=True)
    splits = {'test': [], 'dev': []}; sources = []
    canaries = set()
    for task in TASKS:
        path = f'bbh/{task}.json'
        with urllib.request.urlopen(BASE + path, timeout=60) as response:
            raw = response.read()
        data = json.loads(raw); examples = data['examples']; canaries.add(data['canary'])
        # Hash ranking is independent of Python's RNG implementation and answer labels.
        order = sorted(range(len(examples)), key=lambda i: hashlib.sha256(f'{SEED}/{task}/{i}'.encode()).digest())
        if len(order) < 40: raise ValueError('Insufficient examples')
        for split, indices in [('test', order[:30]), ('dev', order[30:40])]:
            splits[split].extend(adapt(task, i, examples[i]) for i in indices)
        sources.append({'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'population': len(examples)})
    manifest = {'source': 'https://github.com/suzgunmirac/BIG-Bench-Hard', 'revision': REVISION,
                'seed': SEED, 'sampling': 'SHA256(seed/task/index) ascending; first 30 test, next 10 dev per task',
                'canaries': sorted(canaries), 'sources': sources, 'splits': {}}
    for split, cases in splits.items():
        # Interleave tasks so time and warm-cache effects are not confounded with task order.
        cases.sort(key=lambda c: hashlib.sha256(f'{SEED}/order/{c["id"]}'.encode()).digest())
        raw = (json.dumps(cases, ensure_ascii=False, indent=2) + '\n').encode()
        (dest / f'{split}.json').write_bytes(raw)
        manifest['splits'][split] = {'cases': len(cases), 'sha256': hashlib.sha256(raw).hexdigest()}
    with urllib.request.urlopen(BASE + 'LICENSE', timeout=60) as response:
        (dest / 'LICENSE').write_bytes(response.read())
    (dest / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest['splits'], indent=2))

if __name__ == '__main__': main()
