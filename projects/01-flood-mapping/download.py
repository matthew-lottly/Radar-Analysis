"""Download all Spain hand-labeled radar chips; verify published GCS MD5."""
import base64, concurrent.futures, hashlib, json, time, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent
BASE = 'https://storage.googleapis.com/'
def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read()
        except Exception:
            if attempt == 2: raise
            time.sleep(2)
def listing(prefix):
    items, token = [], ''
    while True:
        query = urllib.parse.urlencode(dict(prefix=prefix, maxResults=1000, pageToken=token))
        page = json.loads(get(BASE + 'storage/v1/b/sen1floods11/o?' + query))
        items.extend(page.get('items', []))
        token = page.get('nextPageToken', '')
        if not token: return items
def main():
    data = ROOT / 'data'; data.mkdir(exist_ok=True)
    if (ROOT/'manifest.json').exists():
        manifest=json.loads((ROOT/'manifest.json').read_text())
        def replay(item):
            target=data/item['file']
            content=target.read_bytes() if target.exists() else get(item['url'])
            assert hashlib.sha256(content).hexdigest()==item['sha256'], target
            assert base64.b64encode(hashlib.md5(content).digest()).decode()==item['md5'], target
            target.write_bytes(content)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(replay,manifest))
        print('Verified pinned downloads:',len(manifest),flush=True)
        return
    objects=[]
    for layer in ['S1Hand', 'LabelHand', 'JRCWaterHand']:
        objects += listing('v1.1/data/flood_events/HandLabeled/' + layer + '/Spain_')
    assert any('/LabelHand/' in x['name'] for x in objects), 'Missing reference labels'
    def download(obj):
        target=data / Path(obj['name']).name
        url=BASE+'sen1floods11/'+obj['name']+'?generation='+obj['generation']
        content=target.read_bytes() if target.exists() else get(url)
        assert base64.b64encode(hashlib.md5(content).digest()).decode()==obj['md5Hash'], target
        target.write_bytes(content)
        return dict(file=target.name, url=url, bytes=len(content), md5=obj['md5Hash'], sha256=hashlib.sha256(content).hexdigest())
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        manifest=sorted(pool.map(download,objects),key=lambda x:x['file'])
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    metadata=get(BASE+'sen1floods11/v1.1/Sen1Floods11_Metadata.geojson')
    (data/'event_metadata.geojson').write_bytes(metadata)
    print('Verified downloads:',len(manifest),flush=True)
if __name__=='__main__': main()
