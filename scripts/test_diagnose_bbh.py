import copy
import unittest
from diagnose_bbh import decode, variants

class DiagnosticTest(unittest.TestCase):
    def test_controlled_changes(self):
        case = {'request': {'state': 'Question', 'questions': {'answer': {'criteria': {'A': 'one', 'B': 'two'}}}}}
        baseline = {'model': 'deepseek-flash', 'messages': [{'role': 'system', 'content': 'original'}, {'role': 'user', 'content': '"Question"'}], 'thinking': {'type': 'disabled'}, 'tool_choice': {'type': 'function', 'function': {'name': 'submit_decisions'}}, 'max_tokens': 210, 'tools': [{'schema': 'unchanged'}]}
        old = copy.deepcopy(baseline); arms = variants(case, baseline)
        self.assertEqual(baseline, old)
        changed = copy.deepcopy(arms['neutral_tool']); changed['messages'][0]['content'] = 'original'
        self.assertEqual(changed, baseline)
        direct_low = copy.deepcopy(arms['direct_low']); direct_low.pop('reasoning_effort'); direct_low.update(thinking={'type': 'disabled'}, max_tokens=128)
        self.assertEqual(direct_low, arms['direct_off'])
        self.assertEqual(arms['neutral_tool_low']['tools'], baseline['tools'])
        self.assertEqual(arms['neutral_tool_low']['tool_choice'], 'auto')
        auto = copy.deepcopy(arms['neutral_tool_auto_off']); auto['tool_choice'] = baseline['tool_choice']; auto['max_tokens'] = baseline['max_tokens']
        self.assertEqual(auto, arms['neutral_tool'])
        long_off = copy.deepcopy(arms['direct_off_long']); long_off['max_tokens'] = 128
        self.assertEqual(long_off, arms['direct_off'])
        bl = copy.deepcopy(arms['baseline_tool_low']); bl.pop('reasoning_effort'); bl.update(thinking={'type': 'disabled'}, max_tokens=baseline['max_tokens'], tool_choice=baseline['tool_choice'])
        self.assertEqual(bl, baseline)

    def test_strict_grading(self):
        labels = {'A': 'one', 'B': 'two'}
        response = {'choices': [{'finish_reason': 'stop', 'message': {'content': ' B\n'}}]}
        self.assertEqual(decode('direct_off', response, labels), 'B')
        response['choices'][0]['message']['content'] = 'Answer: B'
        with self.assertRaises(ValueError): decode('direct_off', response, labels)
        response = {'choices': [{'finish_reason': 'tool_calls', 'message': {'tool_calls': [{'type': 'function', 'function': {'name': 'submit_decisions', 'arguments': '{"answers":{"q0":{"A":0.2,"B":0.8}}}'}}]}}]}
        self.assertEqual(decode('baseline_tool', response, labels), 'B')
        response['choices'][0]['message']['tool_calls'][0]['function']['arguments'] = '{"answers":{"q0":{"A":1,"B":1}}}'
        with self.assertRaises(ValueError): decode('baseline_tool', response, labels)
        response['choices'][0]['finish_reason'] = 'length'
        with self.assertRaises(ValueError): decode('baseline_tool', response, labels)

if __name__ == '__main__': unittest.main()
