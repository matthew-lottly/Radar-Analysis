"""A calibrated dual-polarization baseline with a geographic holdout and gap."""
import json,csv
import numpy as np
import rasterio
from scipy.ndimage import median_filter
from analyze import ROOT,OUT,counts,metrics,write_raster
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap,BoundaryNorm
from matplotlib.patches import Patch

def main():
    chips=[]
    for p in sorted((ROOT/'data').glob('*_S1Hand.tif')):
        with rasterio.open(p) as d:
            chips.append((p,(d.bounds.left+d.bounds.right)/2,d.bounds))
    # Split based on geography alone, before inspecting labels for this model.
    cutoff=float(np.quantile([c[1] for c in chips],.6)); gap=.01
    assignments=[]; training=[]; testing=[]
    for p,lon,b in chips:
        group='calibration' if b.right<cutoff-gap else 'test' if b.left>cutoff+gap else 'buffer_excluded'
        assignments.append(dict(chip=p.stem.replace('_S1Hand',''),split=group))
        if group=='calibration': training.append(p)
        elif group=='test': testing.append(p)
    assert len(training)>=5 and len(testing)>=5
    def load(p):
        chip=p.stem.replace('_S1Hand','')
        with rasterio.open(p) as d,rasterio.open(ROOT/'data'/f'{chip}_LabelHand.tif') as l:
            radar=d.read(); ref=l.read(1); valid=(d.read_masks()>0).all(axis=0)&np.isfinite(radar).all(axis=0)&(radar>-50).all(axis=0)&(radar<10).all(axis=0)
            # Fill invalids with bright dry value before filtering, retain validity mask.
            smooth=median_filter(np.where(valid,radar,10.),size=(1,3,3),mode='nearest')
            return chip,smooth,ref,valid,d.profile,list(d.bounds)
    # Exhaustive fixed grid; scoring only calibration labels. Fit VH AND VV cutoffs.
    vv_grid=np.arange(-25,-7.9,.5); vh_grid=np.arange(-32,-11.9,.5)
    tp=np.zeros((len(vv_grid),len(vh_grid)),dtype=np.int64); fp=tp.copy(); positives=0
    for p in training:
        _,rad,y,rv,_,_=load(p); valid=rv&(y>=0)
        # Fixed stride for calibration speed; all valid test pixels evaluated.
        valid[1::2,:]=False; valid[:,1::2]=False
        vv,vh=rad[:,valid]; y=y[valid]; positives+=int((y==1).sum())
        for i,tv in enumerate(vv_grid):
            for j,th in enumerate(vh_grid):
                pred=(vv<tv)&(vh<th); tp[i,j]+=np.sum(pred&(y==1)); fp[i,j]+=np.sum(pred&(y==0))
    score=2*tp/np.maximum(tp+fp+positives,1); ix=np.unravel_index(np.argmax(score),score.shape)
    tv=float(vv_grid[ix[0]]); th=float(vh_grid[ix[1]])
    records=[]; conf=[]; baseline_conf=[]; ex=[]
    dest=OUT/'holdout'; dest.mkdir(exist_ok=True)
    for p in testing:
        chip,rad,y,rv,profile,b=load(p); valid=rv&(y>=0); pred=(rad[0]<tv)&(rad[1]<th)
        c=counts(pred,y,valid); conf.append(c); records.append(dict(chip=chip,**metrics(c)))
        with rasterio.open(OUT/'rasters'/f'{chip}_water.tif') as baseline:
            baseline_conf.append(counts(baseline.read(1)==1,y,valid))
        err=np.full(y.shape,255,dtype='uint8');err[valid]=0;err[valid&pred&(y==1)]=1;err[valid&pred&(y==0)]=2;err[valid&~pred&(y==1)]=3
        write_raster(dest/f'{chip}_water.tif',np.where(rv,pred,255),profile)
        write_raster(dest/f'{chip}_error.tif',err,profile)
        ex.append((chip,rad[1],y,np.where(rv,pred,255),err,b))
    pooled=metrics(np.sum(conf,axis=0)); rng=np.random.default_rng(20261029); a=np.array(conf)
    draws=[metrics(a[rng.integers(len(a),size=len(a))].sum(axis=0)) for _ in range(2000)]
    ci={k:np.percentile([d[k] for d in draws if d[k] is not None],[2.5,97.5]).tolist() for k in ['precision','recall','F1','IoU']}
    result=dict(method='3x3 median VV AND VH threshold, calibrated on western chips only',longitude_cutoff=cutoff,gap_degrees=gap,calibration_chips=len(training),test_chips=len(testing),buffer_chips=len(chips)-len(training)-len(testing),VV_threshold_db=tv,VH_threshold_db=th,calibration_sample_F1=float(score[ix]),test_metrics=pooled,otsu_same_test_domain=metrics(np.sum(baseline_conf,axis=0)),tile_bootstrap_95_percent=ci,assignments=assignments)
    (dest/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    with (dest/'per_chip.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0])); w.writeheader();w.writerows(records)
    # First geographically sorted holdout chip chosen without accuracy selection.
    ex.sort(key=lambda e:e[5][0]); chip,vh,y,pred,err,b=ex[0]; extent=[b[0],b[2],b[1],b[3]]
    fig,axs=plt.subplots(1,4,figsize=(18,5),layout='constrained'); fig.suptitle('Geographic holdout | '+chip+'\nCalibrated on western chips • tested on separated eastern chips',fontsize=17)
    wc=ListedColormap(['#d6dce3','#087fa5']);wc.set_bad('#fafafa'); ec=ListedColormap(['#d6dce3','#087fa5','#e29724','#c43d60']);ec.set_bad('#fafafa')
    axs[0].imshow(vh,extent=extent,cmap='gray',vmin=-30,vmax=-5);axs[0].set_title('Median-filtered VH (dB)')
    for ax,arr,title in [(axs[1],y,'Reference water'),(axs[2],pred,'Held-out prediction')]:
        ax.imshow(np.ma.masked_where((arr<0)|(arr==255),arr),extent=extent,cmap=wc,vmin=0,vmax=1);ax.set_title(title)
    axs[3].imshow(np.ma.masked_equal(err,255),extent=extent,cmap=ec,norm=BoundaryNorm([-.5,.5,1.5,2.5,3.5],4));axs[3].set_title('Held-out spatial errors')
    for ax in axs:ax.set_xlabel('Longitude (°E)');ax.set_ylabel('Latitude (°N)');ax.tick_params(labelsize=8)
    fig.legend(handles=[Patch(color=c,label=t) for c,t in zip(ec.colors,['Correct dry','Correct water','False water','Missed water'])],loc='outside lower center',ncol=4)
    fig.savefig(dest/'heldout_mapping.png',dpi=200);plt.close(fig)
    report=f'''# Geographic holdout assessment

A second baseline improves on label-blind Otsu by calibrating a dual-polarization rule on western chips and assessing it on separated eastern chips. **The Otsu shortcomings were already observed before developing this model**, so this is a transparent development holdout, not a preregistered external validation or an untouched final test set.

Split depends only on longitude: the 60th percentile of chip center longitudes defines the cutoff ({cutoff:.6f}°); training chips must lie wholly west of cutoff −0.01°, and test chips wholly east of cutoff +0.01°. Chips crossing the buffer are excluded. This prevents direct spatial overlap across calibration/test domains, although regional dependence remains.

- Calibration chips: {len(training)}
- Test chips: {len(testing)}
- Buffer exclusions: {len(chips)-len(training)-len(testing)}
- Fitted VV threshold: {tv:.1f} dB; VH threshold: {th:.1f} dB

A fixed 3×3 median filter is applied independently to VV and VH. Water requires both smoothed channels below their cutoffs. Grid search maximizes F1 on a fixed every-other-row/column calibration sample. Grid: VV −25 to −8 dB and VH −32 to −12 dB, both at 0.5 dB steps. No test labels are passed to the calibration routine. No further model selection or tuning follows these test results.

| Held-out metric | Estimate | Tile-bootstrap 95% interval |
|---|---:|---:|
'''
    for k in ci:report+=f'| {k} | {pooled[k]:.3f} | {ci[k][0]:.3f}–{ci[k][1]:.3f} |\n'
    report+='\nOtsu evaluated on these same test chips: F1 = '+format(result['otsu_same_test_domain']['F1'],'.3f')+', IoU = '+format(result['otsu_same_test_domain']['IoU'],'.3f')+'. This controls the comparison domain; the all-chip Otsu summary covers a different footprint.\n'
    report+='\n![Held-out maps and errors](outputs/holdout/heldout_mapping.png)\n\nThe illustrated chip is the westernmost test chip, selected without its accuracy. Full assignments and metrics are in `outputs/holdout/metrics.json`; test predictions and error GeoTIFFs are in the same folder. Metrics apply to surface water, not independently validated new flooding. Calibration F1 is an in-sample fit score, not reported as test accuracy.\n'
    (ROOT/'HOLDOUT.md').write_text(report)
    print(json.dumps({k:v for k,v in result.items() if k!='assignments'},indent=2))
if __name__=='__main__':main()
