import unittest
from decimal import Decimal
from accounting import estimate,costs
class AccountingTest(unittest.TestCase):
 def test_cache_and_output(self):
  e=dict(input_tokens=1000000,cached_tokens=800000,output_tokens=100000)
  self.assertEqual(estimate(e,'deepseek_peak'),Decimal('.1848'))
  self.assertEqual(estimate(e,'deepseek_offpeak'),Decimal('.0924'))
  self.assertEqual(estimate(e,'jev'),Decimal('.042'))
 def test_unknown_and_retries(self):
  e=dict(input_tokens=100,cached_tokens=50,output_tokens=10)
  self.assertEqual(Decimal(costs([e]*4,'deepseek_peak')['total_estimated_usd']),estimate(e,'deepseek_peak')*4)
  self.assertIsNone(costs([e,{}],'deepseek_peak')['total_estimated_usd'])
  self.assertEqual(costs([e,{}],'deepseek_peak')['unknown_cost_attempts'],1)
  self.assertIsNone(estimate(dict(input_tokens=100,output_tokens=10),'deepseek_peak'))
if __name__=='__main__':unittest.main()
