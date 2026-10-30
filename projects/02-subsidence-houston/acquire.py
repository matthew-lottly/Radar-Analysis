"""Acquire public ASF OPERA point observations, archived UNR GNSS, and EIA plants."""
from pathlib import Path
import concurrent.futures, hashlib, io, json, time
import pandas as pd
import requests
ROOT=Path(__file__).resolve().parent
API='https://d2qmcvu7qty7vn.cloudfront.net'
S3='https://opera-pst-rs-pop1.s3.us-west-2.amazonaws.com/products/DISP_S1/GNSS_Calval_archive/F08882/'
POWER='https://services2.arcgis.com/FiaPA4ga0iQKduv3/ArcGIS/rest/services/Power_Plants_in_the_US/FeatureServer/0'
BBOX=[-96,29.45,-95.3,30.15]
GNSS=['ALEF','ADKS','AULT','CFHS','CFJV','CMFB','CSTE','DMFB']
def main():
    data=ROOT/'data';data.mkdir(exist_ok=True);manifest=[]
    def fetch(name,url,body=None,params=None):
        target=data/name
        if target.exists(): content=target.read_bytes();status=200
        else:
            r=requests.post(url,json=body,timeout=180) if body is not None else requests.get(url,params=params,timeout=60)
            r.raise_for_status();content=r.content;status=r.status_code;target.write_bytes(content)
        manifest.append(dict(file=name,url=url,request=body or params,bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),status=status))
        return content
    fetch('steps.txt','https://geodesy.unr.edu/NGLStationPages/steps.txt')
    stations=pd.read_csv(io.BytesIO(fetch('station_catalog.csv',S3+'GNSS_record/F08882.csv')))
    params=dict(where='1=1',geometry=','.join(map(str,BBOX)),geometryType='esriGeometryEnvelope',inSR=4326,spatialRel='esriSpatialRelIntersects',outFields='*',outSR=4326,f='geojson')
    power=json.loads(fetch('power_plants.geojson',POWER+'/query',params=params));assert 'features' in power and not power.get('exceededTransferLimit',False)
    # Deterministic infrastructure sample: eight largest by stated Total_MW, before radar retrieval.
    chosen=sorted(power['features'],key=lambda f:(-f['properties']['Total_MW'],f['properties']['Plant_Code']))[:8]
    sites=[]
    for site in GNSS:
        row=stations.set_index('site').loc[site]
        sites.append(dict(id=site,name=site,kind='GNSS',lon=float(row.lon),lat=float(row.lat)))
    for f in chosen:
        p=f['properties'];lon,lat=f['geometry']['coordinates']
        sites.append(dict(id='EIA_'+str(p['Plant_Code']),name=p['Plant_Name'],kind='power_plant',lon=lon,lat=lat,capacity_mw=p['Total_MW'],inventory_period=p['Period']))
    (ROOT/'inputs/sites.json').write_text(json.dumps(sites,indent=2)+'\n')
    (ROOT/'inputs/power_plants.geojson').write_text(json.dumps(power,separators=(',',':')))
    for name,url,where in [
        ('counties.geojson','https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query',"STATE='48'"),
        ('primary_roads.geojson','https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/2/query','1=1')]:
        context_params=dict(params);context_params['where']=where;context_params['maxAllowableOffset']=.0005
        context=json.loads(fetch(name,url,params=context_params))
        assert 'features' in context and not context.get('exceededTransferLimit',False)
        (ROOT/'inputs'/name).write_text(json.dumps(context,separators=(',',':')))

    errors=[]
    def radar(site):
        body=dict(wkt=f"POINT ({site['lon']} {site['lat']})",bucket='asf-cumulus-prod-opera-products',polarization='VV',flightDirection='ASCENDING',frameId='08882')
        try:
            obs=json.loads(fetch(site['id']+'_opera.json',API+'/timeseries',body=body))
            assert isinstance(obs,dict) and len(obs)>10
            print(site['id'],'radar products',len(obs),flush=True)
        except Exception as e:
            errors.append(dict(site=site['id'],source='OPERA',reason=str(e)));print(site['id'],str(e),flush=True)
    def gnss(site):
        try:
            text=fetch(site+'.tenv3',S3+'GNSS-UNR/'+site+'.tenv3').decode()
            assert text.startswith('site'),text[:200]
            print(site,'GNSS downloaded',flush=True)
        except Exception as e:errors.append(dict(site=site,source='GNSS',reason=str(e)))
    with concurrent.futures.ThreadPoolExecutor(3) as p:list(p.map(radar,sites))
    with concurrent.futures.ThreadPoolExecutor(4) as p:list(p.map(gnss,GNSS))
    (ROOT/'source_manifest.json').write_text(json.dumps(sorted(manifest,key=lambda x:x['file']),indent=2)+'\n')
    (ROOT/'inputs/acquisition_errors.json').write_text(json.dumps(errors,indent=2)+'\n')
    print('Finished; errors:',errors,flush=True)
if __name__=='__main__':main()
