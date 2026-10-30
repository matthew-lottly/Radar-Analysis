"""Displacement graph reconstruction, HAC trends, and LOS projection conventions."""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import lsqr

def reconstruct(reference,secondary,displacement):
    """Invert d_secondary-d_reference, keeping only the largest connected component.

    Returns dates, cumulative displacement, and graph diagnostics. Disconnected
    components are never concatenated. No statistical variance is invented for edges.
    """
    ref=np.asarray(reference,dtype='datetime64[D]');sec=np.asarray(secondary,dtype='datetime64[D]');d=np.asarray(displacement,float)
    if not(len(ref)==len(sec)==len(d)) or len(d)==0:raise ValueError('Empty or mismatched edge arrays')
    if np.any(sec<=ref) or not np.isfinite(d).all():raise ValueError('Invalid dates/values')
    dates=np.unique(np.r_[ref,sec]);ri=np.searchsorted(dates,ref);si=np.searchsorted(dates,sec)
    adj=coo_matrix((np.ones(2*len(d)),(np.r_[ri,si],np.r_[si,ri])),shape=(len(dates),len(dates))).tocsr()
    n,labels=connected_components(adj,directed=False)
    keep=np.flatnonzero(labels==np.argmax(np.bincount(labels)))
    edges=np.isin(ri,keep)&np.isin(si,keep);r=np.searchsorted(keep,ri[edges]);s=np.searchsorted(keep,si[edges]);v=d[edges]
    rows=np.arange(len(v));G=coo_matrix((np.r_[-np.ones(len(v)),np.ones(len(v))],(np.r_[rows,rows],np.r_[r,s])),shape=(len(v),len(keep))).tocsr()
    solved=lsqr(G[:,1:],v,atol=1e-12,btol=1e-12);x=np.r_[0.,solved[0]]
    residual=G@x-v
    if solved[1] not in [0,1,2]:raise ValueError('Graph solver did not converge')
    return dates[keep],x,dict(components=int(n),retained_dates=len(keep),discarded_dates=len(dates)-len(keep),edges=len(v),cycle_rmse_m=float(np.sqrt(np.mean(residual**2))),redundant_edges=int(len(v)-(len(keep)-1)))

def design(t,steps=()):
    return np.column_stack([np.ones(len(t)),t,np.sin(2*np.pi*t),np.cos(2*np.pi*t),np.sin(4*np.pi*t),np.cos(4*np.pi*t)]+[(t>=s).astype(float) for s in steps])

def fit_trend(dates,values,steps=(),lag=6):
    dates=np.asarray(dates,dtype='datetime64[D]');y=np.asarray(values,float)
    if len(y)<24 or not np.isfinite(y).all():raise ValueError('Need >=24 finite observations')
    order=np.argsort(dates);dates=dates[order];y=y[order]
    if len(np.unique(dates))!=len(dates):raise ValueError('Duplicate observation date')
    t=(dates-dates[0]).astype(float)/365.25
    if t[-1]<3:raise ValueError('Need >=3 years for a trend')
    st=[float((np.datetime64(s,'D')-dates[0]).astype(float)/365.25) for s in steps]
    st=sorted(set(s for s in st if .5<s<t[-1]-.5))
    X=design(t,st)
    if np.linalg.matrix_rank(X)<X.shape[1]:raise ValueError('Rank-deficient trend model')
    beta=np.linalg.lstsq(X,y,rcond=None)[0];res=y-X@beta;n,p=X.shape
    bread=np.linalg.inv(X.T@X);z=X*res[:,None];meat=z.T@z
    for k in range(1,min(lag,n-1)+1):
        cross=z[k:].T@z[:-k];meat+=(1-k/(lag+1))*(cross+cross.T)
    cov=bread@meat@bread*n/(n-p)
    se=float(np.sqrt(max(0,cov[1,1])))
    return dict(slope=float(beta[1]),se_hac=se,rmse=float(np.sqrt(np.mean(res**2))),n=n,start=str(dates[0]),end=str(dates[-1]),lag=lag,steps_fitted=len(st)),X@beta,res

def los_vector(incidence_deg,heading_deg):
    """Ground-to-satellite ENU, right-looking orbit; heading clockwise from north.

    Positive LOS is toward satellite. For ascending heading ~-13°, eastward
    motion produces negative LOS. Scenarios are NOT measured look vectors.
    """
    i=np.deg2rad(incidence_deg);h=np.deg2rad(heading_deg)
    return np.array([-np.sin(i)*np.cos(h),np.sin(i)*np.sin(h),np.cos(i)])
