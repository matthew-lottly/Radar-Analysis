import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from core import reconstruct,fit_trend,los_vector
class ScientificCoreTests(unittest.TestCase):
    def test_reference_changes_chain(self):
        dates,x,q=reconstruct(['2020-01-01','2020-02-01'],['2020-02-01','2020-03-01'],[.01,-.03])
        np.testing.assert_allclose(x,[0,.01,-.02],atol=1e-10);self.assertEqual(q['components'],1)
    def test_disconnected_components_are_not_joined(self):
        dates,x,q=reconstruct(['2020-01-01','2020-02-01','2022-01-01'],['2020-02-01','2020-03-01','2022-02-01'],[1,2,100])
        self.assertEqual(q['components'],2);self.assertEqual(q['discarded_dates'],2);np.testing.assert_allclose(x,[0,1,3])
    def test_inconsistent_cycle_is_detected(self):
        _,_,q=reconstruct(['2020-01-01','2020-02-01','2020-01-01'],['2020-02-01','2020-03-01','2020-03-01'],[1,1,5])
        self.assertEqual(q['redundant_edges'],1);self.assertGreater(q['cycle_rmse_m'],.5)
    def test_empty_graph_rejected(self):
        with self.assertRaises(ValueError):reconstruct([],[],[])
    def test_reversed_dates_rejected(self):
        with self.assertRaises(ValueError):reconstruct(['2020-02-01'],['2020-01-01'],[1])
    def test_annual_and_step_trend_recovery(self):
        dates=np.arange(np.datetime64('2017-01-01'),np.datetime64('2025-01-01'),np.timedelta64(30,'D'));t=(dates-dates[0]).astype(float)/365.25
        step='2020-01-01';y=4.2*t+7*np.sin(2*np.pi*t)+3*np.cos(4*np.pi*t)+20*(dates>=np.datetime64(step))
        r,_,_=fit_trend(dates,y,steps=[step]);self.assertAlmostEqual(r['slope'],4.2,places=9);self.assertEqual(r['steps_fitted'],1)
    def test_duplicate_dates_rejected(self):
        dates=np.array(['2020-01-01']*30,dtype='datetime64[D]')
        with self.assertRaises(ValueError):fit_trend(dates,np.zeros(30))
    def test_insufficient_time_support_rejected(self):
        dates=np.datetime64('2020-01-01')+np.arange(30)
        with self.assertRaises(ValueError):fit_trend(dates,np.arange(30))
    def test_los_sign_and_unit_norm(self):
        look=los_vector(35,-13);self.assertAlmostEqual(np.linalg.norm(look),1);self.assertLess(look[0],0);self.assertGreater(look[2],0)
        np.testing.assert_allclose(los_vector(0,0),[0,0,1],atol=1e-15)
if __name__=='__main__':unittest.main()
