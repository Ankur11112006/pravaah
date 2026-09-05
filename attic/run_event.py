"""Whole chain for one flood event: SAR pair -> flood mask -> HAND -> buildings -> verdict."""
import csv, gzip, json, math, os, sys, urllib.parse, urllib.request
import numpy as np, rasterio, geopandas as gpd, pandas as pd
import numpy as _np; _np.in1d = _np.isin
from pysheds.grid import Grid
from rasterio.merge import merge
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import from_bounds, transform as wtransform
from shapely.geometry import shape as shp, box
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                  CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff")

EV = dict(
    delhi = dict(aoi=(77.10,28.50,77.40,28.80), route=(77.00,28.30,77.60,29.00),
                 flood="2023-07-16", base="2023-06-22", orbit=27, dem=["N28_00_E077"]),
)[sys.argv[1]]
TAG = sys.argv[1]

def post(u,b):
    r=urllib.request.Request(u,json.dumps(b).encode(),{"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(r,timeout=120))
def sign(h):
    p=urllib.parse.urlparse(h);a=p.netloc.split(".")[0];c=p.path.lstrip("/").split("/")[0]
    t=json.load(urllib.request.urlopen(
      f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{a}/{c}",timeout=60))["token"]
    return f"{h}?{t}"
def auc(s,y):
    o=np.argsort(s,kind="mergesort");y=y[o];r=np.arange(1,len(y)+1,dtype="float64");n=y.sum()
    return (r[y==1].sum()-n*(n+1)/2)/(n*(len(y)-n))

# ---- 1. SAR pair ----
for lbl,day in (("base",EV["base"]),("flood",EV["flood"])):
    out=f"data/{TAG}_{lbl}_vv.tif"
    if os.path.exists(out): print(f"{lbl}: cached"); continue
    fs=[f for f in post("https://planetarycomputer.microsoft.com/api/stac/v1/search",
        {"collections":["sentinel-1-rtc"],"bbox":list(EV["aoi"]),
         "datetime":f"{day}T00:00:00Z/{day}T23:59:59Z","limit":10})["features"]
        if f["properties"].get("sat:relative_orbit")==EV["orbit"]]
    mos=None
    for f in fs:
        with rasterio.open(sign(f["assets"]["vv"]["href"])) as s:
            b=transform_bounds("EPSG:4326",s.crs,*EV["aoi"])
            w=from_bounds(*b,s.transform).round_offsets().round_lengths()
            a=s.read(1,window=w,boundless=True,fill_value=np.nan)
            prof=s.profile|{"height":a.shape[0],"width":a.shape[1],"transform":s.window_transform(w),
                            "count":1,"dtype":"float32","compress":"deflate","nodata":None}
        mos=a if mos is None else np.where(np.isnan(mos),a,mos)
    with rasterio.open(out,"w",**prof) as d: d.write(mos.astype("float32"),1)
    print(f"{lbl} {day}: {mos.shape} valid {np.isfinite(mos).mean():.0%}")

# ---- 2. flood mask ----
def db(p):
    with rasterio.open(p) as s: a=s.read(1).astype("float32"); pr=s.profile
    a[a<=0]=np.nan; return 10*np.log10(a), pr
base,pr = db(f"data/{TAG}_base_vv.tif"); flood,_ = db(f"data/{TAG}_flood_vv.tif")
perm = base < -15
new  = (flood < -15) & ~perm & ((flood-base) < -3)
print(f"\npermanent water {perm.sum()*1e-4:6.1f} km2 | NEW FLOOD {new.sum()*1e-4:6.1f} km2 "
      f"({new.mean():.1%} of AOI)")
pr.update(dtype="uint8",count=1,compress="deflate",nodata=None)
with rasterio.open(f"data/{TAG}_flood_mask.tif","w",**pr) as d: d.write(new.astype("uint8"),1)

# ---- 3. HAND ----
srcs=[rasterio.open(f"data/Copernicus_DSM_COG_10_{t}_00_DEM.tif") for t in EV["dem"]]
mos,tr=merge(srcs,bounds=EV["route"])
dp=srcs[0].profile|{"height":mos.shape[1],"width":mos.shape[2],"transform":tr,"compress":"deflate"}
with rasterio.open(f"data/{TAG}_dem.tif","w",**dp) as d: d.write(mos[0],1)
g=Grid.from_raster(f"data/{TAG}_dem.tif"); dem=g.read_raster(f"data/{TAG}_dem.tif")
fdir=g.flowdir(g.resolve_flats(g.fill_depressions(g.fill_pits(dem))))
acc=g.accumulation(fdir)
hand=np.asarray(g.compute_hand(fdir,dem,acc>5000),dtype="float32")
with rasterio.open(f"data/{TAG}_hand.tif","w",**(dp|{"dtype":"float32","nodata":np.nan})) as d:
    d.write(hand,1)
print(f"HAND: p50={np.nanpercentile(hand,50):.1f} p90={np.nanpercentile(hand,90):.1f} m")

# ---- 4. cell-level verdict ----
with rasterio.open(f"data/{TAG}_dem.tif") as d:
    w=from_bounds(*EV["aoi"],d.transform).round_offsets().round_lengths()
    e=d.read(1,window=w).astype("float32"); gt=wtransform(w,d.transform); gc=d.crs
h=hand[int(w.row_off):int(w.row_off)+int(w.height), int(w.col_off):int(w.col_off)+int(w.width)]
frac=np.zeros(e.shape,"float32")
with rasterio.open(f"data/{TAG}_flood_mask.tif") as f:
    reproject(f.read(1).astype("float32"),frac,src_transform=f.transform,src_crs=f.crs,
              dst_transform=gt,dst_crs=gc,resampling=Resampling.average)
ok=np.isfinite(e)&(e>0)&np.isfinite(h); y=(frac[ok]>=0.5).astype(int)
ae,ah=auc(-e[ok],y),auc(-h[ok],y)
print(f"\ncells={ok.sum():,} flooded={y.sum():,} ({y.mean():.2%})")
print(f"  elevation AUC {ae:.3f}   HAND AUC {ah:.3f}   -> "
      f"{'HAND wins' if ah>ae+.005 else ('tie' if abs(ah-ae)<=.005 else 'ELEVATION WINS')}")
