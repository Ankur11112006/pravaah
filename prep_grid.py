"""Put DEM, ground truth and permanent water on one 30 m UTM45N grid nested in the SAR grid."""
import numpy as np, rasterio
from rasterio.warp import reproject, Resampling

with rasterio.open("D:/claude/pravaah/data/s1_vv_flood.tif") as s:
    sar_prof, sar_tr, sar_crs = s.profile, s.transform, s.crs

F = 3                                   # 10 m SAR -> 30 m analysis grid
H, W = sar_prof["height"]//F, sar_prof["width"]//F
dst_tr = sar_tr * rasterio.Affine.scale(F)
print(f"analysis grid: {H} x {W} @ 30 m, {sar_crs}")

# box spans 84.90-85.35 E, so it straddles two 1-degree DEM tiles
from rasterio.merge import merge
srcs = [rasterio.open(f"D:/claude/pravaah/data/Copernicus_DSM_COG_10_N25_00_E{e}_00_DEM.tif")
        for e in ("084", "085")]
mosaic, mos_tr = merge(srcs)
dem = np.full((H, W), np.nan, "float32")          # nan, so any gap is loud
reproject(mosaic[0], dem, src_transform=mos_tr, src_crs=srcs[0].crs,
          dst_transform=dst_tr, dst_crs=sar_crs, resampling=Resampling.bilinear,
          src_nodata=srcs[0].nodata, dst_nodata=np.nan)
assert np.isfinite(dem).all(), f"DEM gap: {np.isnan(dem).sum()} cells uncovered"
print(f"  DEM  min {np.nanmin(dem):.1f} m  max {np.nanmax(dem):.1f} m  median {np.nanmedian(dem):.1f} m")

out = {}
for name in ("truth_flood", "permanent_water"):
    with rasterio.open(f"D:/claude/pravaah/data/{name}.tif") as s:
        a = s.read(1).astype("float32")
    frac = a[:H*F, :W*F].reshape(H, F, W, F).mean(axis=(1, 3))
    out[name] = (frac > 0.5).astype("uint8")
    print(f"  {name}: {out[name].sum()*900/1e6:.1f} km2 on 30 m grid")

prof = {**sar_prof, "crs": sar_crs, "transform": dst_tr, "width": W, "height": H,
        "dtype": "float32", "count": 1, "compress": "deflate", "nodata": None}
with rasterio.open("D:/claude/pravaah/data/dem30.tif", "w", **prof) as d:
    d.write(dem, 1)
prof8 = {**prof, "dtype": "uint8"}
for name, arr in out.items():
    with rasterio.open(f"D:/claude/pravaah/data/{name}30.tif", "w", **prof8) as d:
        d.write(arr, 1)
print("  -> dem30.tif, truth_flood30.tif, permanent_water30.tif")
