"""Freeze analysis-ready observations, preserving source identifiers and masks."""
from pathlib import Path
import hashlib, io, json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
START='2019-01-01';END='2024-12-31'
def main():
    sites=json.loads((ROOT/'inputs/sites.json').read_text());radar=[];monthly=[];qc=[]
    for site in sites:
        p=ROOT/'data'/(site['id']+'_opera.json')
        if not p.exists():continue
        obj=json.loads(p.read_text())
        for name,v in obj.items():
            if not name.endswith('.nc'):continue # API includes summary rows; never treat as epochs.
            if not v.get('reference_datetime') or not v.get('secondary_datetime'):continue
            value=v.get('short_wavelength_displacement')
            radar.append(dict(site=site['id'],source_file=name,reference_date=v['reference_datetime'][:10],date=v['secondary_datetime'][:10],los_m=value,x_utm15=v['x'],y_utm15=v['y'],is_masked=v['is_masked']))
        if site['kind']!='GNSS':continue
        p=ROOT/'data'/(site['id']+'.tenv3')
        if not p.exists():continue
        df=pd.read_csv(p,sep=r'\s+')
        # Reconstruct full coordinates from integer origins and fractional components.
        df['date']=pd.Timestamp('1858-11-17')+pd.to_timedelta(df['__MJD'],unit='D')
        df['east_m']=df['_e0(m)']+df['__east(m)'];df['north_m']=df['____n0(m)']+df['_north(m)'];df['up_m']=df['u0(m)']+df['____up(m)']
        df=df[(df.date>=START)&(df.date<=END)].copy()
        valid=np.isfinite(df[['east_m','north_m','up_m','sig_e(m)','sig_n(m)','sig_u(m)']]).all(axis=1)&(df['sig_u(m)']>0)&(df['sig_u(m)']<=.03)&(df['sig_e(m)']>0)&(df['sig_n(m)']>0)
        rejected=int((~valid).sum());df=df[valid].drop_duplicates('date')
        for month,g in df.groupby(df.date.dt.to_period('M')):
            if len(g)<15:continue
            monthly.append(dict(site=site['id'],date=str(month.start_time.date()),days=len(g),east_m=float(g.east_m.median()),north_m=float(g.north_m.median()),up_m=float(g.up_m.median())))
        qc.append(dict(site=site['id'],accepted_days=len(df),rejected_days=rejected,first=str(df.date.min().date()),last=str(df.date.max().date()),gnss_lat=float(df['_latitude(deg)'].median()),gnss_lon=float(df['_longitude(deg)'].median()),reference_longitudes=int(df.reflon.nunique())))
    pd.DataFrame(radar).to_csv(ROOT/'inputs/opera_observations.csv',index=False,float_format='%.10g')
    pd.DataFrame(monthly).to_csv(ROOT/'inputs/gnss_monthly.csv',index=False,float_format='%.12g')
    (ROOT/'inputs/gnss_qc.json').write_text(json.dumps(qc,indent=2)+'\n')
    # Keep known equipment/seismic steps as fit parameters, not hand-edited displacements.
    src=ROOT/'data/steps.txt'
    step_records=[]
    if src.exists():
        for line in src.read_text().splitlines():
            fields=line.split()
            if len(fields)<3 or fields[0] not in {s['id'] for s in sites}:continue
            try:date=pd.to_datetime(fields[1],format='%y%b%d').strftime('%Y-%m-%d')
            except ValueError:continue
            if START<date<END:step_records.append(dict(site=fields[0],date=date,type=fields[2],description=' '.join(fields[3:])))
    (ROOT/'inputs/gnss_steps.json').write_text(json.dumps(step_records,indent=2)+'\n')
    print('Radar records',len(radar),'GNSS monthly records',len(monthly),'step records',len(step_records))
if __name__=='__main__':main()
