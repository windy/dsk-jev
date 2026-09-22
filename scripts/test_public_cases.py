"""Offline checks for source adaptation, provenance and split separation."""
import hashlib
import json
from pathlib import Path
import unittest
from build_public_cases import adapt
from compare_eval import grade
from analyze_public_eval import paired_counts

ROOT = Path(__file__).resolve().parents[1] / 'evals/public-bbh'

class PublicCasesTest(unittest.TestCase):
    def test_multiple_choice(self):
        e = {'input': 'Which?\nOptions:\n(A) first\n(B) second', 'target': '(B)'}
        case = adapt('date_understanding', 1, e)
        self.assertEqual(case['request']['state'], e['input'])
        self.assertEqual(case['request']['questions']['answer']['criteria'], {'A': 'first', 'B': 'second'})
        self.assertNotIn('expected', case['request'])
        self.assertTrue(grade(case, {'answers': {'answer': {'choice': 'B'}}})[0]['pass'])
        self.assertFalse(grade(case, {'answers': {'answer': {'choice': 'A'}}})[0]['pass'])
        self.assertTrue(grade(case, {})[0]['invalid_answer'])

    def test_binary_and_invalid_labels(self):
        for task, label in [('boolean_expressions', 'False'), ('sports_understanding', 'no'), ('causal_judgement', 'Yes')]:
            c = adapt(task, 0, {'input': 'Question', 'target': label})
            self.assertEqual(c['expected']['answer'], label)
            self.assertIn(label, c['request']['questions']['answer']['criteria'])
        with self.assertRaises(ValueError):
            adapt('date_understanding', 0, {'input': '(A) first', 'target': '(B)'})

    def test_paired_failures_and_disagreements(self):
        rows = []
        for i, (j, d) in enumerate([(True, True), (False, True), (True, False), (False, False)]):
            for provider, passed in [('jev', j), ('deepseek', d)]:
                rows.append({'id': str(i), 'provider': provider, 'questions': 1,
                             'status': 200 if passed else 503,
                             'checks': [{'pass': True}] if passed else []})
        counts = paired_counts(rows)
        for key in ['both_correct', 'deepseek_only', 'jev_only', 'both_wrong']:
            self.assertEqual(counts[key], 1)
        self.assertEqual(counts['mcnemar_exact_two_sided_p'], 1)
        with self.assertRaises(ValueError): paired_counts(rows[:-1])
        with self.assertRaises(ValueError): paired_counts(rows + [rows[0]])
        one_sided = []
        for i in range(4):
            for provider, passed in [('jev', False), ('deepseek', True)]:
                one_sided.append({'id': str(i), 'provider': provider, 'questions': 1, 'status': 200, 'checks': [{'pass': passed}]})
        self.assertEqual(paired_counts(one_sided)['mcnemar_exact_two_sided_p'], 0.125)

    def test_frozen_splits(self):
        manifest = json.loads((ROOT / 'manifest.json').read_text())
        ids = []
        for split, count in [('test', 30), ('dev', 10)]:
            raw = (ROOT / (split + '.json')).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest['splits'][split]['sha256'])
            cases = json.loads(raw)
            self.assertEqual(len(cases), 10 * count)
            split_ids = {c['id'] for c in cases}
            self.assertEqual(len(split_ids), len(cases)); ids.append(split_ids)
            groups = {c['group'] for c in cases}
            self.assertEqual(len(groups), 10)
            for group in groups:
                self.assertEqual(sum(c['group'] == group for c in cases), count)
            for c in cases:
                self.assertEqual(c['source']['revision'], manifest['revision'])
                self.assertEqual(c['request']['model'], 'jev-1.13.0')
                self.assertIn(c['expected']['answer'], c['request']['questions']['answer']['criteria'])
                self.assertEqual(set(c['request']), {'model', 'state', 'questions'})
        self.assertFalse(ids[0] & ids[1])

if __name__ == '__main__': unittest.main()
