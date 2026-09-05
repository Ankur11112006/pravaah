"""DEM A/B: does the verdict survive a change of elevation source?
FABDEM (the spec's first choice) needs a Bristol licence acceptance, so this
substitutes the free DEMs that are reachable without one."""
import json, urllib.parse, urllib.request
import numpy as np, rasterio
import numpy as _np; _np.in1d = _np.isin
from pysheds.grid import Grid
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds
import os
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR")

AOI = (84.90, 25.45, 85.35, 25.75)
DEMS = {"Copernicus GLO-30": None, "NASADEM": "nasadem", "ALOS AW3D30": "alos-dem"}

def auc(s, y):
    o = np.argsort(s, kind="mergesort"); y = y[o]
    r = np.arange(1, len(y)+1, dtype="float64"); npos = y.sum()
    return (r[y==1].sum() - npos*(npos+1)/2)/(npos*(len(y)-npos))

def sign(h):
    p = urllib.parse.urlparse(h); a = p.netloc.split(".")[0]; c = p.path.lstrip("/").split("/")[0]
    t = json.load(urllib.request.urlopen(
        f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{a}/{c}", timeout=60))["token"]
    return f"{h}?{t}"

# reference grid = the Copernicus routing window already on disk
with rasterio.open("data/dem_route.tif") as r:
    REF_T, REF_CRS, REF_SHAPE = r.transform, r.crs, r.shape
    ref_elev = r.read(1)
    win = from_bounds(*AOI, REF_T).round_offsets().round_lengths()
r0, c0 = int(win.row_off), int(win.col_off)
r1, c1 = r0+int(win.height), c0+int(win.width)
sub = (slice(r0, r1), slice(c0, c1))

with rasterio.open("data/flood_mask.tif") as f:
    frac = np.zeros((r1-r0, c1-c0), "float32")
    reproject(f.read(1).astype("float32"), frac, src_transform=f.transform, src_crs=f.crs,
              dst_transform=rasterio.windows.transform(win, REF_T), dst_crs=REF_CRS,
              resampling=Resampling.average)
truth = frac >= 0.5

def fetch(coll):
    res = urllib.request.Request("https://planetarycomputer.microsoft.com/api/stac/v1/search",
        json.dumps({"collections":[coll], "bbox":[84.5,25.1,85.8,26.1], "limit":20}).encode(),
        {"Content-Type":"application/json"})
    feats = json.load(urllib.request.urlopen(res, timeout=90))["features"]
    out = np.full(REF_SHAPE, np.nan, "float32")
    for ft in feats:
        key = next(k for k in ("elevation","data") if k in ft["assets"])
        with rasterio.open(sign(ft["assets"][key]["href"])) as s:
            tmp = np.full(REF_SHAPE, np.nan, "float32")
            reproject(s.read(1).astype("float32"), tmp, src_transform=s.transform, src_crs=s.crs,
                      dst_transform=REF_T, dst_crs=REF_CRS, resampling=Resampling.bilinear,
                      src_nodata=s.nodata, dst_nodata=np.nan)
        out = np.where(np.isfinite(out), out, tmp)
    return out

print(f"  {'DEM':<20}{'elev AUC':>10}{'HAND AUC':>10}{'verdict':>26}")
print("  " + "-"*66)
for name, coll in DEMS.items():
    full = ref_elev if coll is None else fetch(coll)
    prof = dict(driver="GTiff", height=full.shape[0], width=full.shape[1], count=1,
                dtype="float32", crs=REF_CRS, transform=REF_T, nodata=np.nan)
    tmpf = f"tmp/dem_{(coll or 'cop')}.tif"
    with rasterio.open(tmpf, "w", **prof) as d: d.write(np.nan_to_num(full, nan=0.0), 1)

    g = Grid.from_raster(tmpf); dem = g.read_raster(tmpf)
    fdir = g.flowdir(g.resolve_flats(g.fill_depressions(g.fill_pits(dem))))
    acc = g.accumulation(fdir)
    hand = np.asarray(g.compute_hand(fdir, dem, acc > 5000), dtype="float32")[sub]

    e = full[sub]
    ok = np.isfinite(e) & (e > 0) & np.isfinite(hand)
    y = truth[ok].astype(int)
    ae, ah = auc(-e[ok], y), auc(-hand[ok], y)
    v = "HAND wins" if ah > ae + 0.005 else ("tie" if abs(ah-ae) <= 0.005 else "elevation wins")
    print(f"  {name:<20}{ae:10.3f}{ah:10.3f}{v:>26}")
