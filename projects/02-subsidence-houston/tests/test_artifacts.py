import hashlib,json,unittest
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
class ArtifactTests(unittest.TestCase):
    def test_frozen_input_checksums(self):
        for p,h in json.loads((ROOT/'inputs_snapshot_sha256.json').read_text()).items():self.assertEqual(hashlib.sha256((ROOT/p).read_bytes()).hexdigest(),h,p)
    def test_cached_raw_source_checksums(self):
        for source in json.loads((ROOT/'source_manifest.json').read_text()):
            p=ROOT/'data'/source['file']
            if p.exists():self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),source['sha256'],p.name)
    def test_sample_and_exclusion_accounting(self):
        m=json.loads((ROOT/'outputs/metrics.json').read_text());rates=pd.read_csv(ROOT/'outputs/opera_rates.csv')
        self.assertEqual(m['requested_sites'],m['radar_sites']+len(m['excluded_sites']));self.assertEqual(len(rates),m['radar_sites']);self.assertTrue((rates.epochs>=24).all());self.assertTrue((rates.pixel_offset_m<22).all())
    def test_no_accuracy_claim(self):
        m=json.loads((ROOT/'outputs/metrics.json').read_text());self.assertTrue(m['checks']['independent_accuracy'].startswith('NOT ESTABLISHED'))
    def test_reference_station_not_in_diagnostic(self):
        d=pd.read_csv(ROOT/'outputs/gnss_comparison_diagnostic.csv');self.assertNotIn('ALEF',d.site.tolist());self.assertEqual(len(d),7);self.assertTrue((d.matched_months>=24).all())
    def test_unique_source_edges_and_finite_retained(self):
        d=pd.read_csv(ROOT/'inputs/opera_observations.csv');good=d[d.is_masked.eq(False)&d.los_m.notna()];self.assertTrue(np.isfinite(good.los_m).all());self.assertFalse(good.duplicated(['site','reference_date','date']).any())
    def test_point_output_no_inferred_surface(self):
        j=json.loads((ROOT/'outputs/sampled_displacement.geojson').read_text());self.assertEqual(len(j['features']),15);self.assertTrue(all(f['geometry']['type']=='Point' for f in j['features']))
if __name__=='__main__':unittest.main()
