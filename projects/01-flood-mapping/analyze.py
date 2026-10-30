"""Label-blind VH Otsu baseline and spatially explicit reference evaluation."""
import csv, gzip, hashlib, json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import shapes
from pyproj import Geod
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'outputs'

def otsu(x):
    """256-bin Otsu over physically screened finite radar observations only."""
    h,e=np.histogram(x,bins=256,range=(-50,10)); p=h/h.sum(); c=(e[:-1]+e[1:])/2
    w=np.cumsum(p); m=np.cumsum(p*c)
    score=(m[-1]*w-m)**2/np.maximum(w*(1-w),1e-15)
    return float(c[np.argmax(score)])

def counts(pred,truth,valid):
    p=pred[valid]; y=truth[valid]==1
    return np.array([np.sum(p&y),np.sum(p&~y),np.sum(~p&y),np.sum(~p&~y)],dtype=np.int64)

def metrics(c):
    tp,fp,fn,tn=map(float,c)
    def div(a,b): return a/b if b else None
    return dict(TP=int(tp),FP=int(fp),FN=int(fn),TN=int(tn),precision=div(tp,tp+fp),recall=div(tp,tp+fn),F1=div(2*tp,2*tp+fp+fn),IoU=div(tp,tp+fp+fn),accuracy=div(tp+tn,tp+fp+fn+tn),specificity=div(tn,tn+fp),reference_water_fraction=div(tp+fn,tp+fp+fn+tn))

def pixel_areas(ds):
    assert ds.crs.to_epsg()==4326 and ds.transform.b==ds.transform.d==0
    g=Geod(ellps='WGS84'); t=ds.transform
    return np.array([abs(g.polygon_area_perimeter([t.c,t.c+t.a,t.c+t.a,t.c],[t.f+r*t.e,t.f+r*t.e,t.f+(r+1)*t.e,t.f+(r+1)*t.e])[0]) for r in range(ds.height)])[:,None]*np.ones((1,ds.width))

def write_raster(path,a,profile):
    profile=profile.copy(); profile.update(count=1,dtype='uint8',nodata=255,compress='deflate')
    with rasterio.open(path,'w',**profile) as ds: ds.write(a.astype('uint8'),1)

def main():
    OUT.mkdir(exist_ok=True)
    for folder in ['rasters','vectors']: (OUT/folder).mkdir(exist_ok=True)
    files=sorted((ROOT/'data').glob('*_S1Hand.tif'))
    assert files, 'Run download.py first'
    records=[]; conf=[]; sensitivity={d:[] for d in [-2,-1,0,1,2]}; features=[]; examples=[]
    footprints=[]
    for path in files:
        chip=path.name.replace('_S1Hand.tif','')
        with rasterio.open(path) as s, rasterio.open(ROOT/'data'/f'{chip}_LabelHand.tif') as l, rasterio.open(ROOT/'data'/f'{chip}_JRCWaterHand.tif') as j:
            assert s.count==2 and l.count==j.count==1
            assert s.crs==l.crs==j.crs and np.allclose(tuple(s.transform),tuple(l.transform),rtol=0,atol=1e-12) and np.allclose(tuple(s.transform),tuple(j.transform),rtol=0,atol=1e-12) and s.shape==l.shape==j.shape, chip
            vv,vh=s.read(); truth=l.read(1); jrc=j.read(1)
            assert set(np.unique(truth))<= {-1,0,1}, (chip,np.unique(truth))
            assert set(np.unique(jrc))<= {-1,0,1}, (chip,np.unique(jrc))
            radar_valid=(s.read_masks()>0).all(axis=0)&np.isfinite(vv)&np.isfinite(vh)&(vh>-50)&(vh<10)&(vv>-50)&(vv<10)
            assert radar_valid.sum()>1000, chip
            threshold=otsu(vh[radar_valid]); pred=vh<threshold
            valid=radar_valid&(truth>=0)
            assert valid.any(), chip
            c=counts(pred,truth,valid); conf.append(c)
            for d in sensitivity: sensitivity[d].append(counts(vh<threshold+d,truth,valid))
            area=pixel_areas(s); potential=pred&radar_valid&(jrc==0)
            r=dict(chip=chip,threshold_db=threshold,valid_pixels=int(valid.sum()),ignored_pixels=int(valid.size-valid.sum()),**metrics(c),mapped_water_km2=float(area[pred&radar_valid].sum()/1e6),reference_domain_predicted_km2=float(area[pred&valid].sum()/1e6),reference_water_km2=float(area[(truth==1)&valid].sum()/1e6),potential_flood_km2=float(area[potential].sum()/1e6),jrc_unknown_pixels=int((jrc<0).sum()))
            records.append(r)
            prediction=np.where(radar_valid,pred,255).astype('uint8')
            flood=np.where(radar_valid&(jrc>=0),potential,255).astype('uint8')
            error=np.full(truth.shape,255,dtype='uint8'); error[valid]=0
            error[valid&pred&(truth==1)]=1; error[valid&pred&(truth==0)]=2; error[valid&~pred&(truth==1)]=3
            for name,a in [('water',prediction),('potential_flood',flood),('error',error)]: write_raster(OUT/'rasters'/f'{chip}_{name}.tif',a,s.profile)
            # Small connected polygons retained; no label-driven cleanup or filtering.
            for geom,value in shapes(flood,mask=flood==1,transform=s.transform):
                features.append(dict(type='Feature',geometry=geom,properties=dict(chip=chip,class_name='potential_flood',method='VH Otsu minus JRC permanent water')))
            b=s.bounds; footprints.append(dict(chip=chip,bounds=list(b)))
            examples.append((r,vh.copy(),truth.copy(),prediction.copy(),error.copy(),list(b)))
    totals=np.sum(conf,axis=0); overall=metrics(totals)
    rng=np.random.default_rng(20261029); a=np.array(conf)
    draws=[metrics(a[rng.integers(0,len(a),len(a))].sum(axis=0)) for _ in range(2000)]
    ci={k:np.percentile([d[k] for d in draws if d[k] is not None],[2.5,97.5]).tolist() for k in ['precision','recall','F1','IoU','accuracy']}
    result=dict(study='Spain Sen1Floods11 event, 2019-09-17',chips=len(files),method='Per-chip VH Otsu, no reference-label fitting',metrics=overall,tile_bootstrap_95_percent=ci,sensitivity={str(d):metrics(np.sum(cs,axis=0)) for d,cs in sensitivity.items()},area_sums_km2={k:sum(r[k] for r in records) for k in ['mapped_water_km2','reference_domain_predicted_km2','reference_water_km2','potential_flood_km2']},checks=dict(alignment='passed',label_codes='passed',radar_masks='passed',geodesic_pixel_areas='passed',confusion_total='passed' if int(totals.sum())==sum(r['valid_pixels'] for r in records) else 'FAILED'))
    (OUT/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    with (OUT/'per_chip.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    with gzip.open(OUT/'potential_flood.geojson.gz','wt') as f:
        json.dump(dict(type='FeatureCollection',features=features),f,separators=(',',':'))
    (OUT/'footprints.json').write_text(json.dumps(footprints,indent=2))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titleweight':'bold','figure.facecolor':'#f3f6fa','axes.facecolor':'#e8edf3'})
    # Select median-IoU chip for illustration, transparently; evaluation includes all chips.
    examples.sort(key=lambda x:x[0]['IoU'] if x[0]['IoU'] is not None else -1)
    r,vh,truth,pred,error,b=examples[len(examples)//2]
    extent=[b[0],b[2],b[1],b[3]]
    fig,axs=plt.subplots(1,4,figsize=(18,5),layout='constrained')
    fig.suptitle('SPAIN | Flood-event radar mapping and observed errors\n17 September 2019 • '+r['chip']+' • median chip IoU example',fontsize=17,color='#132c45')
    im=axs[0].imshow(vh,extent=extent,cmap='gray',vmin=-30,vmax=-5); fig.colorbar(im,ax=axs[0],shrink=.65,label='VH backscatter (dB)')
    axs[0].set_title('Sentinel-1 radar')
    waterc=ListedColormap(['#d6dce3','#087fa5']); waterc.set_bad('#fafafa')
    for ax,arr,title in [(axs[1],truth,'Hand-labeled reference'),(axs[2],pred,'Otsu water detection')]:
        ax.imshow(np.ma.masked_where((arr<0)|(arr==255),arr),extent=extent,cmap=waterc,vmin=0,vmax=1); ax.set_title(title)
    ec=ListedColormap(['#d6dce3','#087fa5','#e29724','#c43d60']); ec.set_bad('#fafafa')
    axs[3].imshow(np.ma.masked_equal(error,255),extent=extent,cmap=ec,norm=BoundaryNorm([-.5,.5,1.5,2.5,3.5],4)); axs[3].set_title('Reference disagreement')
    for ax in axs: ax.set_xlabel('Longitude (°E)'); ax.set_ylabel('Latitude (°N)'); ax.tick_params(labelsize=8)
    fig.legend(handles=[Patch(color=c,label=t) for c,t in zip(ec.colors,['Correct dry','Correct water','False water','Missed water'])],loc='outside lower center',ncol=4,frameon=False)
    fig.savefig(OUT/'mapping_and_errors.png',dpi=200); plt.close(fig)
    fig,axs=plt.subplots(1,3,figsize=(15,5),layout='constrained'); fig.suptitle('Accuracy audit | All Spain hand-labeled chips',fontsize=18,color='#132c45')
    tp,fp,fn,tn=totals; matrix=np.array([[tn,fp],[fn,tp]])
    axs[0].imshow(np.log10(matrix+1),cmap='Blues')
    for i in range(2):
        for j in range(2): axs[0].text(j,i,f'{matrix[i,j]:,}',ha='center',va='center',color='black')
    axs[0].set(xticks=[0,1],xticklabels=['Dry','Water'],yticks=[0,1],yticklabels=['Dry','Water'],xlabel='Prediction',ylabel='Reference',title='Confusion counts (log color)')
    keys=['precision','recall','F1','IoU']; vals=[overall[k] for k in keys]
    axs[1].bar(keys,vals,color=['#087fa5','#2a9c8f','#385c91','#755fa5']); axs[1].set(ylim=(0,1),title='Metrics with tile-bootstrap 95% intervals')
    axs[1].errorbar(range(4),vals,yerr=np.array([[max(0,v-ci[k][0]) for k,v in zip(keys,vals)],[max(0,ci[k][1]-v) for k,v in zip(keys,vals)]]),fmt='none',ecolor='#132c45',capsize=4)
    for k in ['precision','recall','IoU']: axs[2].plot(list(sensitivity),[result['sensitivity'][str(d)][k] for d in sensitivity],marker='o',label=k)
    axs[2].set(xlabel='Offset from Otsu threshold (dB)',ylabel='Score',ylim=(0,1),title='Threshold sensitivity; no retuning'); axs[2].legend()
    fig.savefig(OUT/'accuracy_dashboard.png',dpi=200); plt.close(fig)
    # Geographic coverage map, no external basemap needed.
    fig,ax=plt.subplots(figsize=(9,8),layout='constrained')
    for ex in examples:
        rr,_,_,_,_,bb=ex
        ax.add_patch(plt.Rectangle((bb[0],bb[1]),bb[2]-bb[0],bb[3]-bb[1],facecolor=plt.cm.viridis(rr['IoU'] or 0),edgecolor='white',linewidth=.5))
    ax.autoscale(); ax.set_aspect(1/np.cos(np.deg2rad(np.mean([b[1],b[3]])))); ax.set(xlabel='Longitude (°E)',ylabel='Latitude (°N)',title='Spain study coverage | chip footprints colored by water IoU')
    fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0,1),cmap='viridis'),ax=ax,label='Water IoU'); fig.savefig(OUT/'coverage.png',dpi=200); plt.close(fig)
    report=f'''# Spain flood-event mapping: results

Status: executed exploratory benchmark. **This simple baseline overpredicts water substantially; its mapped area is not a reliable flood-area estimate.** Radar acquisition: **17 September 2019**; optical reference acquisition in event metadata: **18 September 2019**.

## Results

All **{len(files)} available Spain hand-labeled chips** were processed. The primary method is label-blind, per-chip Otsu thresholding of Sentinel-1 VH backscatter. No hand labels or published event threshold are used to set the classifier.

| Metric | Estimate | Tile-bootstrap 95% interval |
|---|---:|---:|
'''
    for k in ['precision','recall','F1','IoU','accuracy']: report+=f"| {k} | {overall[k]:.3f} | {ci[k][0]:.3f}–{ci[k][1]:.3f} |\n"
    report+='\n![Mapping and errors](outputs/mapping_and_errors.png)\n\n![Accuracy audit](outputs/accuracy_dashboard.png)\n\n![Coverage](outputs/coverage.png)\n\n'
    report+='## Area accounting\n\nThese are sums across sampled chip footprints, **not the total flood extent of Spain or the event**. Reference-domain totals exclude ignored labels; full mapping totals include radar-valid pixels with ignored labels.\n\n'
    for k,v in result['area_sums_km2'].items(): report+=f'- {k}: **{v:.3f} km²**\n'
    report+='''
## Interpretation and limits

The validated target is event-time **surface water**, including permanent water. `potential_flood` subtracts the supplied JRC permanent-water mask, but its accuracy is NOT independently established as new flooding: seasonal water, changing shorelines, and JRC omissions can remain. No pre-event Sentinel-1 change-detection claim is made.

The hand labels are an independent annotation source, not field survey truth. The one-day radar/optical timing difference can create real disagreement. Cloud-obscured/ambiguous reference pixels are excluded. Spatial dependence remains between nearby chips; tile bootstrap intervals describe this sampled set, not national or future-event generalization. Overall accuracy can be inflated by the dry majority; prioritize water precision, recall, F1, and IoU.

Dark terrain/shadow, smooth bare soil, radar speckle, wind-roughened water, buildings, and flooded vegetation are expected failure modes. A single threshold cannot resolve them reliably. Maps explicitly show false positives and missed water. No confidence-probability layer is claimed.

Road/building exposure is not calculated in this release because no dated, verified infrastructure inventory has been ingested. No damage claims are supported. Before operational use, add same-orbit pre-event imagery, terrain/shadow masking, independent new-flood reference labels, and a dated infrastructure layer.

## Audit trail

See `outputs/metrics.json`, `outputs/per_chip.csv`, `manifest.json`, `METHODS.md`, and `VALIDATION.md`. The sensitivity figure reports ±1/±2 dB perturbations without choosing a best threshold after looking at reference accuracy. The illustrative chip is selected by median IoU; all chips contribute to reported results.
'''
    report+='\n## Calibrated model with geographic holdout\n\nSee [HOLDOUT.md](HOLDOUT.md) for a separate calibration/test experiment with a spatial buffer and explicit development-history disclosure.\n'
    (ROOT/'RESULTS.md').write_text(report)
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
