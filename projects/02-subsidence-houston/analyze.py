"""Executed point-sampled OPERA/GNSS audit. No full-band/vertical accuracy claim."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from pyproj import Transformer,Geod
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from core import reconstruct,fit_trend,los_vector
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'outputs'
START=np.datetime64('2019-01-01');END=np.datetime64('2024-12-31');REF='ALEF'
def savefig(fig,name):
    fig.savefig(OUT/name,dpi=160,facecolor=fig.get_facecolor());plt.close(fig)
    # Lossless PNG optimization; no scientific arrays are modified.
    from PIL import Image
    p=OUT/name
    with Image.open(p) as im:im.save(p,optimize=True)
def run():
    OUT.mkdir(exist_ok=True);sites=json.loads((ROOT/'inputs/sites.json').read_text());lookup={s['id']:s for s in sites}
    obs=pd.read_csv(ROOT/'inputs/opera_observations.csv');gnss=pd.read_csv(ROOT/'inputs/gnss_monthly.csv');steps=json.loads((ROOT/'inputs/gnss_steps.json').read_text());gnssqc=json.loads((ROOT/'inputs/gnss_qc.json').read_text())
    xy=Transformer.from_crs(4326,32615,always_xy=True);geo=Geod(ellps='WGS84')
    records=[];series=[];graphs={};rseries={};gseries={};gfits={};checks=[];excluded=[]
    for site,grp in obs.groupby('site'):
        s=lookup[site];value=pd.to_numeric(grp.los_m,errors='coerce');valid=value.notna()&np.isfinite(value)&grp.is_masked.eq(False)
        good=grp[valid].sort_values('source_file').drop_duplicates(['reference_date','date'],keep='last')
        px,py=xy.transform(s['lon'],s['lat']);dist=np.hypot(good.x_utm15-px,good.y_utm15-py)
        assert dist.max()<22,'Query to source pixel center exceeds 30m-cell half diagonal'
        dates,displacement,graph=reconstruct(good.reference_date,good.date,good.los_m)
        take=(dates>=START)&(dates<=END);d=dates[take];y=displacement[take]*1000
        try:
            m,pred,res=fit_trend(d,y,lag=6)
        except ValueError as e:
            excluded.append(dict(site=site,reason=str(e),valid_epochs=len(d)));continue
        m['se_hac_lag3']=fit_trend(d,y,lag=3)[0]['se_hac'];m['se_hac_lag12']=fit_trend(d,y,lag=12)[0]['se_hac']
        early=d<np.datetime64('2022-01-01');late=~early
        # Exactly 3+ years may be unavailable due acquisition cadence; this check reports insufficient rather than shortening gate.
        halves=[]
        for mask in [early,late]:
            try:halves.append(fit_trend(d[mask],y[mask],lag=6)[0]['slope'])
            except ValueError:halves.append(None)
        span=float((d[-1]-d[0]).astype(float)/365.25)
        rec=dict(site=site,name=s['name'],kind=s['kind'],lon=s['lon'],lat=s['lat'],los_rate_mm_yr=m['slope'],los_rate_se_hac_mm_yr=m['se_hac'],los_residual_rmse_mm=m['rmse'],epochs=m['n'],start=m['start'],end=m['end'],masked_or_missing=int((~valid).sum()),pixel_offset_m=float(dist.max()),three_year_early_mm_yr=halves[0],three_year_late_mm_yr=halves[1],se_lag3=m['se_hac_lag3'],se_lag12=m['se_hac_lag12'])
        records.append(rec);graphs[site]=graph;rseries[site]=(d,y,pred)
        for date,v,fit in zip(d,y,pred):series.append(dict(site=site,date=str(date),los_displacement_mm=float(v-y[0]),model_mm=float(fit-pred[0])))
    radar=pd.DataFrame(records).sort_values('site');radar.to_csv(OUT/'opera_rates.csv',index=False,float_format='%.8g');pd.DataFrame(series).to_csv(OUT/'opera_timeseries.csv',index=False,float_format='%.8g')
    gnss_records=[];monthly_records=[]
    for site,grp in gnss.groupby('site'):
        stepdates=sorted(set(s['date'] for s in steps if s['site']==site))
        # A monthly median spanning an instrument step mixes the two offsets.
        stepmonths={s[:7] for s in stepdates};grp=grp[~grp.date.str[:7].isin(stepmonths)].sort_values('date').copy()
        dates=grp.date.to_numpy(dtype='datetime64[D]');rstart=np.datetime64(radar.set_index('site').loc[site,'start']);rend=np.datetime64(radar.set_index('site').loc[site,'end']);take=(dates>=rstart)&(dates<=rend);grp=grp[take];dates=dates[take]
        m={};fits=[]
        for channel in ['east','north','up']:
            y=grp[channel+'_m'].to_numpy()*1000;y-=y[0]
            result,pred,res=fit_trend(dates,y,steps=stepdates,lag=6);m[channel]=result;fits.append((y,pred))
        r=dict(site=site,months=len(grp),month_coverage=float(len(grp)/72),excluded_step_months=len(stepmonths),east_rate_mm_yr=m['east']['slope'],north_rate_mm_yr=m['north']['slope'],up_rate_mm_yr=m['up']['slope'],up_rate_se_hac_mm_yr=m['up']['se_hac'],steps_fitted=m['up']['steps_fitted'],start=m['up']['start'],end=m['up']['end'])
        gnss_records.append(r);gfits[site]=m;gseries[site]=(dates,np.column_stack([x[0] for x in fits]))
        for i,date in enumerate(dates):monthly_records.append(dict(site=site,date=str(date),east_mm=fits[0][0][i],north_mm=fits[1][0][i],up_mm=fits[2][0][i]))
    grates=pd.DataFrame(gnss_records).sort_values('site');grates.to_csv(OUT/'gnss_rates.csv',index=False,float_format='%.8g');pd.DataFrame(monthly_records).to_csv(OUT/'gnss_rebased_monthly.csv',index=False,float_format='%.8g')
    # Projection and reference sensitivity. No exact viewing geometry is claimed.
    scenarios=[];nominal=los_vector(35,-13);base=gfits[REF];rr=radar.set_index('site');diag=[]
    for site in sorted(gfits):
        if site==REF:continue
        # Compare identical calendar months: median radar epochs and GNSS daily medians.
        def radar_monthly(which):
            dd,yy,_=rseries[which]
            return pd.Series(yy,index=pd.to_datetime(dd)).groupby(pd.to_datetime(dd).to_period('M')).median()
        dd,ee=gseries[site];dd0,ee0=gseries[REF]
        gs=pd.DataFrame(ee,index=pd.to_datetime(dd).to_period('M'))
        gs0=pd.DataFrame(ee0,index=pd.to_datetime(dd0).to_period('M'))
        rm=radar_monthly(site);rm0=radar_monthly(REF)
        months=gs.index.intersection(gs0.index).intersection(rm.index).intersection(rm0.index).sort_values()
        dates=months.to_timestamp().to_numpy(dtype='datetime64[D]')
        diff=gs.loc[months].to_numpy()-gs0.loc[months].to_numpy()
        stepdates=sorted(set(s['date'] for s in steps if s['site'] in [site,REF]))
        velocity=np.array([fit_trend(dates,diff[:,i],steps=stepdates,lag=6)[0]['slope'] for i in range(3)])
        matched_radar=fit_trend(dates,(rm.loc[months]-rm0.loc[months]).to_numpy(),lag=6)[0]
        predicted=[];hbias=[]
        for inc in [30,35,40,45]:
            for heading in [-18,-13,-8]:
                look=los_vector(inc,heading);los=float(look@velocity);bias=float(look[:2]@velocity[:2]/look[2]);predicted.append(los);hbias.append(bias)
                scenarios.append(dict(site=site,incidence_deg=inc,heading_deg=heading,relative_gnss_los_mm_yr=los,horizontal_vertical_bias_mm_yr=bias))
        radar_relative=matched_radar['slope']
        diagnostic=radar_relative-float(nominal@velocity)
        diag.append(dict(site=site,matched_months=len(months),start=str(dates[0]),end=str(dates[-1]),opera_relative_los_mm_yr=radar_relative,gnss_relative_los_nominal_mm_yr=float(nominal@velocity),gnss_projection_min_mm_yr=min(predicted),gnss_projection_max_mm_yr=max(predicted),conditional_mismatch_mm_yr=diagnostic,horizontal_vertical_bias_min_mm_yr=min(hbias),horizontal_vertical_bias_max_mm_yr=max(hbias)))
    diagnostic=pd.DataFrame(diag);diagnostic.to_csv(OUT/'gnss_comparison_diagnostic.csv',index=False,float_format='%.8g');pd.DataFrame(scenarios).to_csv(OUT/'viewing_sensitivity.csv',index=False,float_format='%.8g')
    features=[]
    for _,r in radar.iterrows():
        prop=r.where(pd.notna(r),None).to_dict();prop['observable']='short-wavelength LOS; positive toward satellite';prop['accuracy_status']='exploratory, not independent full-band validation'
        features.append(dict(type='Feature',geometry=dict(type='Point',coordinates=[r.lon,r.lat]),properties=prop))
    (OUT/'sampled_displacement.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features),allow_nan=False,indent=2)+'\n')
    # Spatial station/cell metadata checks, independent of rate fitting.
    station_offsets={}
    for q in gnssqc:
        s=lookup[q['site']];_,_,distance=geo.inv(s['lon'],s['lat'],q['gnss_lon'],q['gnss_lat']);station_offsets[q['site']]=distance
        assert distance<15,'Rounded station catalog disagrees with archived GNSS coordinates'
        assert q['reference_longitudes']==1,'GNSS reference meridian changed'
    # Infrastructure snapshot is newer than the measurement period; no historical-presence assumption.
    plants=json.loads((ROOT/'inputs/power_plants.geojson').read_text())
    checks=dict(input_observations_finite=True,source_pixel_centers='within 22 m of queries',station_coordinate_offsets_m=station_offsets,graph_diagnostics=graphs,gnss_month_coverage_min=float(grates.month_coverage.min()),calibration_to_gnss='none',independent_accuracy='NOT ESTABLISHED: spatial filtering and precise look-vector mismatch',infrastructure_inventory_periods=sorted(set(str(f['properties']['Period']) for f in plants['features'])))
    metrics=dict(study='Western Houston local-deformation screening',period=['2019-01-01','2024-12-31'],opera_frame='08882',flight_direction='ASCENDING',radar_sites=len(radar),requested_sites=len(sites),excluded_sites=excluded,gnss_stations=len(grates),infrastructure_sample=len(radar[radar.kind=='power_plant']),infrastructure_context_count=len(plants['features']),radar_rate_range_mm_yr=[float(radar.los_rate_mm_yr.min()),float(radar.los_rate_mm_yr.max())],conditional_diagnostic_rmse_mm_yr=float(np.sqrt(np.mean(diagnostic.conditional_mismatch_mm_yr**2))),conditional_diagnostic_bias_mm_yr=float(diagnostic.conditional_mismatch_mm_yr.mean()),conditional_diagnostic_n=len(diagnostic),checks=checks)
    (OUT/'excluded_sites.json').write_text(json.dumps(excluded,indent=2)+'\n')
    (OUT/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'figure.facecolor':'#f1f5f9','axes.facecolor':'#e1e9ee','axes.titleweight':'bold','axes.labelcolor':'#20394c','text.color':'#183247'})
    # Data-point map. No continuous velocity raster is inferred from sparse samples.
    fig,axs=plt.subplots(1,2,figsize=(14,7),layout='constrained');fig.suptitle('WESTERN HOUSTON | Two views of ground motion\n2019–2024 observations • sampled locations, no spatial interpolation',fontsize=18)
    norm=TwoSlopeNorm(vmin=-10,vcenter=0,vmax=10); gnorm=TwoSlopeNorm(vmin=-20,vcenter=0,vmax=5); cmap='RdBu';pcoords=np.array([f['geometry']['coordinates'] for f in plants['features']])
    for ax in axs:
        # Public Census cartographic context; no imagery or inferred deformation surface.
        counties=json.loads((ROOT/'inputs/counties.geojson').read_text())
        for f in counties['features']:
            geom=f['geometry'];polys=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
            for poly in polys:
                for ring in poly:
                    coords=np.asarray(ring);ax.plot(coords[:,0],coords[:,1],color='#91a5b4',lw=.8,ls='--',zorder=1)
        roads=json.loads((ROOT/'inputs/primary_roads.geojson').read_text())
        for f in roads['features']:
            geom=f['geometry'];lines=[geom['coordinates']] if geom['type']=='LineString' else geom['coordinates']
            for line in lines:
                coords=np.asarray(line);ax.plot(coords[:,0],coords[:,1],color='#b6c3ca',lw=.6,zorder=1)
        ax.text(-95.79,29.57,'FORT BEND COUNTY',fontsize=7,color='#617987',ha='center',rotation=15)
        ax.text(-95.58,30.10,'HARRIS COUNTY',fontsize=7,color='#617987',ha='center')
        ax.scatter(pcoords[:,0],pcoords[:,1],s=16,marker='^',color='#8194a3',alpha=.5)
        ax.set(xlim=(-96, -95.3),ylim=(29.45,30.15),xlabel='Longitude (degrees)',ylabel='Latitude (degrees)');ax.set_aspect(1/np.cos(np.deg2rad(29.8)));ax.grid(color='white',linewidth=.7)
        ax.plot([-95.97,-95.763],[29.48,29.48],color='#20394c',lw=3);ax.text(-95.865,29.49,'20 km',ha='center',fontsize=8)
        ax.annotate('N',xy=(-95.97,30.10),xytext=(-95.97,30.02),arrowprops=dict(arrowstyle='->',color='#20394c'),ha='center')
    for kind,marker in [('GNSS','o'),('power_plant','^')]:
        sub=radar[radar.kind==kind];im=axs[0].scatter(sub.lon,sub.lat,c=sub.los_rate_mm_yr,cmap=cmap,norm=norm,s=105,marker=marker,edgecolors='#244256',linewidths=.8,zorder=4)
    gmap=grates.merge(pd.DataFrame(sites),left_on='site',right_on='id');axs[1].scatter(gmap.lon,gmap.lat,c=gmap.up_rate_mm_yr,cmap=cmap,norm=gnorm,s=110,edgecolors='#244256',zorder=4)
    # Label GNSS on separate panel; avoid implying plants have GNSS measurements.
    for i,(_,r) in enumerate(gmap.iterrows()):
        axs[1].annotate(r.site,(r.lon,r.lat),xytext=(6,5 if i%2 else -12),textcoords='offset points',fontsize=8,bbox=dict(facecolor='#f1f5f9',edgecolor='none',alpha=.8,pad=1))
    axs[0].set_title('OPERA local LOS rate\nPositive: toward satellite; broad motion filtered out');axs[1].set_title('GNSS vertical rate\nPositive: uplift; distinct from radar observable')
    fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),ax=axs[0],label='Filtered LOS (mm/year)',shrink=.65,extend='both')
    fig.colorbar(plt.cm.ScalarMappable(norm=gnorm,cmap=cmap),ax=axs[1],label='GNSS vertical (mm/year)',shrink=.65,extend='both')
    fig.legend(handles=[Line2D([0],[0],marker='o',color='none',markerfacecolor='#456b84',label='GNSS sample'),Line2D([0],[0],marker='^',color='none',markerfacecolor='#456b84',label='Selected power plant'),Line2D([0],[0],marker='^',color='none',markerfacecolor='#8194a3',label='EIA inventory context')],loc='outside lower center',ncol=3,frameon=False)
    savefig(fig,'displacement_map.png')
    # Four predetermined alphabetically ordered non-reference GNSS locations.
    chosen=sorted(set(gfits)-{REF})[:4];fig,axs=plt.subplots(2,2,figsize=(13,8),layout='constrained');fig.suptitle('Local radar time series | Independent GNSS context\nReference: ALEF • GNSS projected using an illustrative 35° incidence / −13° heading',fontsize=16)
    for ax,site in zip(axs.flat,chosen):
        d,y,_=rseries[site];dr,yr,_=rseries[REF];common=np.intersect1d(d,dr);a=np.searchsorted(d,common);b=np.searchsorted(dr,common);v=y[a]-yr[b];v-=v[0]
        ax.plot(common,v,'.-',ms=2,lw=.6,color='#087e9d',label='OPERA short-wavelength LOS difference')
        gd,enu=gseries[site];gdr,enur=gseries[REF];gc=np.intersect1d(gd,gdr);ga=np.searchsorted(gd,gc);gb=np.searchsorted(gdr,gc);gv=(enu[ga]-enur[gb])@nominal;gv-=gv[0]
        ax.plot(gc,gv,'.',ms=2,color='#b65a30',label='GNSS ENU→LOS difference (unfiltered)')
        ax.set(title=site,ylabel='Displacement (mm)');ax.grid(color='white');ax.tick_params(axis='x',rotation=25)
    axs.flat[0].legend(fontsize=7);savefig(fig,'timeseries.png')
    fig,axs=plt.subplots(1,2,figsize=(13,6),layout='constrained');fig.suptitle('Validation audit | Compatibility diagnostics, not an accuracy certification',fontsize=16)
    x=diagnostic.gnss_relative_los_nominal_mm_yr.to_numpy();y=diagnostic.opera_relative_los_mm_yr.to_numpy();lo=diagnostic.gnss_projection_min_mm_yr;hi=diagnostic.gnss_projection_max_mm_yr
    axs[0].errorbar(x,y,xerr=[x-lo,hi-x],fmt='o',color='#087e9d',ecolor='#c18b4c',capsize=3)
    low=min(x.min(),y.min())-1;high=max(x.max(),y.max())+1;axs[0].plot([low,high],[low,high],'--',color='#6b7e8c')
    for i,s in enumerate(diagnostic.site):axs[0].annotate(s,(x[i],y[i]),xytext=(5,4),textcoords='offset points',fontsize=8)
    axs[0].set(xlabel='GNSS relative LOS scenario (mm/year)',ylabel='OPERA filtered relative LOS (mm/year)',title='Seven stations relative to ALEF\nBars: look-angle scenarios, not confidence intervals')
    sub=radar[radar.kind=='power_plant'].sort_values('los_rate_mm_yr');names=[lookup[x]['name'][:32] for x in sub.site]
    axs[1].barh(names,sub.los_rate_mm_yr,xerr=1.96*sub.los_rate_se_hac_mm_yr,color='#487e9b',alpha=.9,capsize=3);axs[1].axvline(0,color='#425866',lw=1);axs[1].set(xlabel='Local LOS rate (mm/year)',title='Accepted power-plant samples\nBars: approximate 95% formal HAC intervals')
    for ax in axs:ax.grid(axis='x',color='white');ax.set_axisbelow(True)
    savefig(fig,'validation_and_infrastructure.png')
    # Formal uncertainty sensitivity and geometry interpretation.
    fig,axs=plt.subplots(1,2,figsize=(13,5.5),layout='constrained');fig.suptitle('Uncertainty and radar viewing-direction checks',fontsize=17)
    axs[0].scatter(radar.los_rate_se_hac_mm_yr,radar.se_lag12,s=45,color='#087e9d');mx=max(radar.los_rate_se_hac_mm_yr.max(),radar.se_lag12.max())*1.1;axs[0].plot([0,mx],[0,mx],'--',color='#697f8c');axs[0].set(xlabel='Rate SE, HAC lag 6 (mm/year)',ylabel='Rate SE, HAC lag 12 (mm/year)',title='Residual autocorrelation sensitivity\nFormal errors omit spatial-filter/systematic uncertainty')
    for s,g in pd.DataFrame(scenarios).groupby('site'):
        h=g[g.heading_deg==-13];axs[1].plot(h.incidence_deg,h.horizontal_vertical_bias_mm_yr,marker='o',label=s)
    axs[1].axhline(0,color='#697f8c',lw=1);axs[1].set(xlabel='Assumed incidence angle (degrees)',ylabel='Vertical-only bias from horizontal motion (mm/year)',title='Relative GNSS horizontal-motion leakage\nAscending right-looking geometry scenarios');axs[1].legend(fontsize=7,ncol=2)
    savefig(fig,'uncertainty_and_geometry.png')
    create_report(metrics,radar,grates,diagnostic)
    print(json.dumps({k:v for k,v in metrics.items() if k!='checks'},indent=2))

def create_report(metrics,radar,gnss,diagnostic):
    report='''# Results: western Houston local deformation

**Executed exploratory study, not a validated absolute-subsidence map.** All radar observations are real OPERA DISP-S1 measurements returned by ASF's public point service. The available observable is **short-wavelength line-of-sight (LOS) displacement**, which suppresses spatial wavelengths above approximately 30 km. It cannot recover broad regional subsidence or unique vertical motion.

The study uses 2019–2024 observations at eight GNSS stations and the eight largest EIA power-plant inventory locations in the bounding box, ranked by reported capacity before radar retrieval. Seven power-plant sites passed the minimum data gate; one was excluded for insufficient valid epochs. The 58-plant inventory snapshot is February 2025, so infrastructure presence throughout 2019–2024 is not assumed.

![Sampled maps](outputs/displacement_map.png)

## Observed local radar trends

Positive values indicate movement toward the satellite, not necessarily uplift. Negative values indicate movement away, not necessarily subsidence. Rates include local spatial-filter residuals. The maps plot measured sample locations without interpolation.

| Site | Kind | LOS rate (mm/yr) | Formal HAC SE (mm/yr) | Epochs |
|---|---|---:|---:|---:|
'''
    for _,r in radar.iterrows():report+=f'| {r["name"]} | {r.kind} | {r.los_rate_mm_yr:.2f} | {r.los_rate_se_hac_mm_yr:.2f} | {r.epochs} |\n'
    report+='\n![Time series](outputs/timeseries.png)\n\n## GNSS comparison and error checks\n\n'
    report+=f"The conditional, geometry-scenario comparison at seven GNSS stations relative to ALEF has RMS mismatch **{metrics['conditional_diagnostic_rmse_mm_yr']:.2f} mm/yr** and mean mismatch **{metrics['conditional_diagnostic_bias_mm_yr']:.2f} mm/yr**. **These are compatibility diagnostics, not an independent radar accuracy estimate**: the radar field is spatially filtered, GNSS is not; exact per-pixel look vectors were unavailable. No GNSS correction was fitted to the radar values.\n\n"
    report+='''The diagnostic fits use identical available calendar months for both instruments and both stations; radar epochs are reduced to monthly medians for this comparison. The same reference station appears in each difference, so diagnostic residuals are correlated. GNSS monthly medians require at least 15 accepted daily solutions; daily up uncertainty above 30 mm is excluded. Known step months are omitted and eligible documented steps enter the GNSS trend regression. Reported formal HAC errors quantify fitted residual behavior, not all systematic uncertainty.

![Audit and infrastructure](outputs/validation_and_infrastructure.png)

![Uncertainty and geometry](outputs/uncertainty_and_geometry.png)

## What is supported

- Reproducible, source-identified OPERA point observations and local LOS trend estimates at real infrastructure coordinates.
- Independent GNSS vertical and horizontal trend estimates, with equipment-step and data-coverage checks.
- Explicit reference-date, graph-connectivity, mask, coordinate, projection-sign, and uncertainty-sensitivity checks.

## What remains unvalidated

Absolute subsidence, full-band displacement, a continuous 30 m rate map, pixelwise incidence/heading, and damage or structural condition are not established. The point service does not expose the full recommended-mask rationale, coherence arrays, or physical displacement uncertainty layers. Formal rate intervals must not be used as complete uncertainty bounds.

To complete a full-band subsidence/accuracy study, obtain authenticated full OPERA NetCDF and matching STATIC geometry, apply matching spatial/temporal referencing and filtering to GNSS, and compare projected ENU with the unfiltered LOS field. A second viewing geometry is required for meaningful decomposition unless a documented horizontal-motion assumption is justified. Do not extrapolate these trends into future damage or plant failure.

See [METHODS.md](METHODS.md), [VALIDATION.md](VALIDATION.md), [SOURCES.md](SOURCES.md), and the CSV/GeoJSON/JSON outputs for the complete audit trail.
'''
    (ROOT/'RESULTS.md').write_text(report)
if __name__=='__main__':run()
