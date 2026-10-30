"""Integration checks against delivered artifacts; no network required."""
import csv,gzip,hashlib,itertools,json,unittest
from pathlib import Path
import numpy as np
import rasterio
ROOT=Path(__file__).resolve().parents[1]
class OutputTests(unittest.TestCase):
    def test_accounting(self):
        m=json.loads((ROOT/'outputs/metrics.json').read_text())
        with (ROOT/'outputs/per_chip.csv').open() as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),30)
        for k in ['TP','FP','FN','TN']:self.assertEqual(sum(int(r[k]) for r in rows),m['metrics'][k])
        self.assertEqual(sum(m['metrics'][k] for k in ['TP','FP','FN','TN']),sum(int(r['valid_pixels']) for r in rows))
    def test_footprints_do_not_overlap(self):
        f=json.loads((ROOT/'outputs/footprints.json').read_text())
        for a,b in itertools.combinations(f,2):
            x,y=a['bounds'],b['bounds']
            overlap=min(x[2],y[2])-max(x[0],y[0])>1e-10 and min(x[3],y[3])-max(x[1],y[1])>1e-10
            self.assertFalse(overlap,(a['chip'],b['chip']))
    def test_spatial_holdout_separation(self):
        m=json.loads((ROOT/'outputs/holdout/metrics.json').read_text())
        f={r['chip']:r['bounds'] for r in json.loads((ROOT/'outputs/footprints.json').read_text())}
        for a in m['assignments']:
            b=f[a['chip']]
            if a['split']=='calibration':self.assertLess(b[2],m['longitude_cutoff']-m['gap_degrees'])
            elif a['split']=='test':self.assertGreater(b[0],m['longitude_cutoff']+m['gap_degrees'])
    def test_raster_encodings(self):
        for p in (ROOT/'outputs').rglob('*.tif'):
            with rasterio.open(p) as d:
                self.assertEqual(d.crs.to_epsg(),4326);self.assertEqual(d.nodata,255)
                allowed={0,1,2,3,255} if p.stem.endswith('_error') else {0,1,255}
                self.assertTrue(set(np.unique(d.read(1)))<=allowed,p.name)
    def test_manifest_and_local_inputs(self):
        manifest=json.loads((ROOT/'manifest.json').read_text());self.assertEqual(len(manifest),90)
        for item in manifest:
            p=ROOT/'data'/item['file']
            if p.exists():self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),item['sha256'])
    def test_vector_encoding(self):
        with gzip.open(ROOT/'outputs/potential_flood.geojson.gz','rt') as f:obj=json.load(f)
        self.assertEqual(obj['type'],'FeatureCollection');self.assertGreater(len(obj['features']),0)
if __name__=='__main__': unittest.main()
