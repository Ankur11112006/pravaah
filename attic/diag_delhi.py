import sys, numpy as np, rasterio
sys.path.insert(0,".")
from pravaah import config, hazard
ev = config.DELHI
dem, tr, crs = hazard.terrain(ev, "data/delhi_dem.tif")
perm, new = hazard.observed(ev, dem.shape, tr, crs,
                            "data/delhi_flood_mask.tif", "data/delhi_base_vv.tif")
PX = hazard.PX_KM2
print(f"AOI cells {dem.size:,}   elevation p1 {np.nanpercentile(dem,1):.1f} "
      f"p50 {np.nanpercentile(dem,50):.1f} p65 {np.nanpercentile(dem,65):.1f} "
      f"p99 {np.nanpercentile(dem,99):.1f} m")
print(f"seed (permanent water) cells: {perm.sum():,} = {perm.sum()*PX:.1f} km2")
print(f"  their elevation: min {dem[perm].min():.1f} med {np.median(dem[perm]):.1f} "
      f"max {dem[perm].max():.1f} m")
print(f"targets: baseline {perm.sum()*PX:.1f} km2, flood {(perm|new).sum()*PX:.1f} km2\n")
print(f"  {'level m':>9}{'connected km2':>16}{'below-level km2':>18}")
for L in np.arange(198, 214, 0.5):
    below = (dem < L) & np.isfinite(dem)
    print(f"  {L:9.2f}{hazard.flood_at(dem, perm, L).sum()*PX:16.2f}{below.sum()*PX:18.1f}")
