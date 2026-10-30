import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from analyze import counts,metrics,otsu
class AccuracyTests(unittest.TestCase):
    def test_confusion_and_ignored_pixels(self):
        truth=np.array([1,1,0,0,-1]); pred=np.array([1,0,1,0,1],dtype=bool)
        c=counts(pred,truth,truth>=0)
        np.testing.assert_array_equal(c,[1,1,1,1])
        m=metrics(c)
        self.assertEqual(m['precision'],.5); self.assertEqual(m['recall'],.5)
        self.assertEqual(m['F1'],.5); self.assertAlmostEqual(m['IoU'],1/3)
    def test_undefined_water_metrics(self):
        m=metrics([0,0,0,20]); self.assertIsNone(m['IoU']); self.assertIsNone(m['precision'])
        self.assertEqual(m['accuracy'],1)
    def test_bimodal_threshold(self):
        x=np.r_[np.full(1000,-30.),np.full(1000,-10.)]
        t=otsu(x); self.assertTrue(-30<t<-10)
        self.assertEqual(int((x<t).sum()),1000)
if __name__=='__main__': unittest.main()
