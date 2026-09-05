"""HAND (Height Above Nearest Drainage) for the Patna AOI, from Copernicus GLO-30.
Routing runs on a window wider than the AOI so the drainage network is not truncated."""
import numpy as np, rasterio, time
from rasterio.merge import merge
from rasterio.windows import from_bounds
np_patch = None
import numpy as _np
_np.in1d = _np.isin          # pysheds predates numpy 2
from pysheds.grid import Grid

ROUTE = (84.60, 25.20, 85.70, 26.00)   # wider than AOI so flow accumulates properly
t0 = time.time()

srcs = [rasterio.open(f"data/Copernicus_DSM_COG_10_N25_00_E{t}_00_DEM.tif") for t in ("084","085")]
mos, tr = merge(srcs, bounds=ROUTE)
prof = srcs[0].profile | {"height": mos.shape[1], "width": mos.shape[2],
                          "transform": tr, "compress": "deflate"}
with rasterio.open("data/dem_route.tif", "w", **prof) as d: d.write(mos[0], 1)
print(f"  zeros in window: {(mos[0]==0).sum():,} of {mos[0].size:,}")
print(f"DEM window {mos.shape[1:]}  elev {np.nanmin(mos):.0f}-{np.nanmax(mos):.0f} m  [{time.time()-t0:.0f}s]")

grid = Grid.from_raster("data/dem_route.tif")
dem  = grid.read_raster("data/dem_route.tif")
print("conditioning...", end="", flush=True)
d = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem)))
print(f" done [{time.time()-t0:.0f}s]")
fdir = grid.flowdir(d);            print(f"flowdir [{time.time()-t0:.0f}s]")
acc  = grid.accumulation(fdir);    print(f"accum   [{time.time()-t0:.0f}s]  max={acc.max():,.0f} cells")

for thr in (1000, 5000, 20000, 50000):
    net = acc > thr
    print(f"  acc>{thr:>6}: {net.sum():>9,} channel cells  ({net.mean():.2%} of window)")

THR = 5000     # ~4.5 km2 contributing area at 30 m
hand = grid.compute_hand(fdir, dem, acc > THR)
h = np.asarray(hand, dtype="float32")
print(f"HAND    [{time.time()-t0:.0f}s]  valid {np.isfinite(h).mean():.1%}  "
      f"p50={np.nanpercentile(h,50):.1f} p90={np.nanpercentile(h,90):.1f} max={np.nanmax(h):.0f} m")

with rasterio.open("data/hand.tif", "w", **(prof | {"dtype":"float32","nodata":np.nan})) as dst:
    dst.write(h, 1)
print("wrote data/hand.tif")
