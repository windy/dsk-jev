"""Report exact paired disagreements and task accuracy from a completed run."""
import argparse
import json
import math
from pathlib import Path


def paired_counts(rows):
    pairs = {}
    for row in rows:
        pair = pairs.setdefault(row['id'], {})
        if row['provider'] in pair: raise ValueError('Duplicate provider/case')
        if row['questions'] != 1: raise ValueError('This analysis requires one question per case')
        pair[row['provider']] = row['status'] == 200 and len(row['checks']) == 1 and row['checks'][0]['pass']
    counts = {'both_correct': 0, 'deepseek_only': 0, 'jev_only': 0, 'both_wrong': 0}
    for pair in pairs.values():
        if set(pair) != {'jev', 'deepseek'}: raise ValueError('Incomplete paired run')
        j, d = pair['jev'], pair['deepseek']
        key = 'both_correct' if j and d else ('deepseek_only' if d else ('jev_only' if j else 'both_wrong'))
        counts[key] += 1
    b, c = counts['deepseek_only'], counts['jev_only']; n = b + c
    counts['mcnemar_exact_two_sided_p'] = min(1., 2 * sum(math.comb(n, k) for k in range(min(b, c)+1)) / 2**n) if n else 1.
    return counts


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('prefix'); args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'reports'
    rows = json.loads((root / f'{args.prefix}-results.json').read_text())
    summary = json.loads((root / f'{args.prefix}-summary.json').read_text())
    details = {'overall': paired_counts(rows), 'by_task': {}}
    lines = ['# Public BBH subset: paired accuracy breakdown', '',
             '300 fixed questions, 10 selected tasks × 30, zero-shot choice adaptation. This is not the full BBH benchmark or an official Jev evaluation. See [dataset and frozen protocol](../evals/public-bbh/README.md).', '',
             '| Task | Jev | dsk-jev | Difference (percentage points) |', '|---|---:|---:|---:|']
    for group in sorted({r['group'] for r in rows}):
        subset = [r for r in rows if r['group'] == group]
        details['by_task'][group] = paired_counts(subset)
        j = summary['jev']['by_group'][group]; d = summary['deepseek']['by_group'][group]
        lines.append(f"| {group} | {j['correct_judgments']}/{j['judgments']} | {d['correct_judgments']}/{d['judgments']} | {(d['effective_accuracy']-j['effective_accuracy'])*100:+.1f} |")
    p = details['overall']
    lines += ['', f"Paired outcomes: both correct {p['both_correct']}; only dsk-jev correct {p['deepseek_only']}; only Jev correct {p['jev_only']}; both wrong {p['both_wrong']}.", '',
              f"Exploratory exact two-sided McNemar p={p['mcnemar_exact_two_sided_p']:.4g}. This paired test conditions on discordant outcomes and treats cases as independent; templated questions within a task may be correlated. It does not establish production superiority, training-data independence or account for selection of tasks. Per-task p-values in JSON are exploratory and unadjusted for multiple comparisons.", '',
              f'[Latency, cost and methodology]({args.prefix}.md) · [Raw results]({args.prefix}-results.json) · [Usage summary]({args.prefix}-summary.json)', '']
    (root / f'{args.prefix}-analysis.json').write_text(json.dumps(details, indent=2)+'\n')
    (root / f'{args.prefix}-analysis.md').write_text('\n'.join(lines))
    print('\n'.join(lines))

if __name__ == '__main__': main()
