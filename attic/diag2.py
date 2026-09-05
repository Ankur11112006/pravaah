import sys, numpy as np
sys.path.insert(0,".")
from scipy.ndimage import label
from pravaah import config, hazard
ev=config.DELHI
dem,tr,crs=hazard.terrain(ev,"data/delhi_dem.tif")
perm,new=hazard.observed(ev,dem.shape,tr,crs,"data/delhi_flood_mask.tif","data/delhi_base_vv.tif")
PX=hazard.PX_KM2
lab,n=label(perm,np.ones((3,3)))
sz=np.bincount(lab.ravel()); sz[0]=0
print(f"permanent-water mask: {n} separate blobs, {perm.sum()*PX:.1f} km2 total")
big=int(np.argmax(sz))
river=lab==big
print(f"  largest blob = {sz[big]*PX:.2f} km2, elevation "
      f"{dem[river].min():.1f} to {dem[river].max():.1f} m (med {np.median(dem[river]):.1f})")
print(f"  the other {n-1} blobs hold {(perm.sum()-sz[big])*PX:.1f} km2 and reach "
      f"{dem[perm & ~river].max():.1f} m -> not river, SAR-dark city surfaces")
print()
print(f"  {'level':>8}{'seed=all':>12}{'seed=river only':>18}")
for L in np.arange(203.8,205.2,0.1):
    print(f"  {L:8.2f}{hazard.flood_at(dem,perm,L).sum()*PX:12.2f}"
          f"{hazard.flood_at(dem,river,L).sum()*PX:18.2f}")
