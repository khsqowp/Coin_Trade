import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stress

class StressTests(unittest.TestCase):
    def test_cost(self): self.assertEqual(stress.cost_x2([.02],.003),[.017])
    def test_delay(self): self.assertEqual(stress.delayed_entries([2,8]),[3,9])
    def test_bears(self): self.assertEqual(stress.bear_year_check({2018:0,2022:-.1}),{2018:True,2022:False})
    def test_missing_bear(self): self.assertIsNone(stress.bear_year_check({})[2018])
    def test_unused(self): self.assertEqual(stress.unused_symbol_group({'A':1},['A','B']),{'A':1,'B':None})
    def test_concentration(self): self.assertAlmostEqual(stress.yearly_concentration({20240101:1,20250101:3})[2025],.75)
    def test_flatness(self): self.assertEqual(stress.flatness([.6,.5,.1],1),(2,3,False))
    def test_flatness_empty(self): self.assertEqual(stress.flatness([],1),(0,0,None))

if __name__=='__main__':unittest.main()
