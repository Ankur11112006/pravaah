"""Does Google's inundation history beat what we already had?

Google's floods team published, CC-BY-4.0, how often each 128 m pixel was wet
between 1999 and 2020 from GLAD/Landsat, as three nested risk polygons. That is
a susceptibility layer built from 21 years of optical imagery, not from one SAR
pass, so it should not share the urban blindness that sank our SAR ground truth.

This runs it through the same falsification harness as HAND, elevation and
distance-to-river, against the same Sentinel-1 truth, on both events.
"""
import glob, json, sys
import numpy as np, rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds, transform as wtransform
from scipy.ndimage import distance_transform_edt
from shapely.geometry import shape, box
sys.stdout.reconfigure(encoding="utf-8")

RISK = {"Low_risk": 1, "Medium_risk": 2, "High_risk": 3}   # nested, wet >=0.5/1/5%


def auc(s, y):
    o = np.argsort(s, kind="mergesort"); y = y[o]
    r = np.arange(1, len(y) + 1, dtype="float64"); n = y.sum()
    return (r[y == 1].sum() - n * (n + 1) / 2) / (n * (len(y) - n))


def p_at_r(s, y, R=.70):
    o = np.argsort(-s, kind="mergesort"); ys = y[o]; tp = np.cumsum(ys)
    prec = tp / np.arange(1, len(ys) + 1); rec = tp / y.sum()
    return prec[np.argmax(rec >= R)] if (rec >= R).any() else float("nan")


def google_layer(aoi, shape_, tr):
    """Burn the three nested risk polygons into an ordinal 0-3 raster."""
    aoi_box = box(*aoi)
    out = np.zeros(shape_, "uint8")
    used = 0
    for path in sorted(glob.glob("data/inund/*.geojson")):
        d = json.load(open(path))
        shapes = []
        for f in d["features"]:
            lvl = RISK.get(f["properties"].get("name"))
            if lvl is None:
                continue
            g = shape(f["geometry"])
            if not g.intersects(aoi_box):
                continue
            shapes.append((g.intersection(aoi_box), lvl))
        if not shapes:
            continue
        used += 1
        # burn low first so high overwrites it; the layers are nested
        for lvl in (1, 2, 3):
            sel = [(g, lvl) for g, l in shapes if l == lvl]
            if sel:
                rasterize(sel, out=out, transform=tr, merge_alg=rasterio.enums.MergeAlg.replace)
    return out, used


def run(tag, aoi, dem, hand, mask, base):
    with rasterio.open(dem) as s:
        w = from_bounds(*aoi, s.transform).round_offsets().round_lengths()
        e = s.read(1, window=w).astype("float32")
        tr, crs = wtransform(w, s.transform), s.crs
    with rasterio.open(hand) as s:
        h = s.read(1, window=w)

    def rg(a, src):
        o = np.zeros(e.shape, "float32")
        reproject(a, o, src_transform=src.transform, src_crs=src.crs,
                  dst_transform=tr, dst_crs=crs, resampling=Resampling.average)
        return o
    with rasterio.open(mask) as f:
        frac = rg(f.read(1).astype("float32"), f)
    with rasterio.open(base) as s:
        b = s.read(1).astype("float32"); b[b <= 0] = np.nan
        perm = rg((10 * np.log10(b) < -15).astype("float32"), s) >= .5
    dist = distance_transform_edt(~perm) * 30.0

    gih, ntiles = google_layer(aoi, e.shape, tr)
    ok = np.isfinite(e) & (e > 0) & np.isfinite(h)
    y = (frac[ok] >= .5).astype(int)

    print(f"\n{tag}: {ok.sum():,} cells, {y.sum():,} flooded ({y.mean():.2%})")
    print(f"  {(gih[ok] > 0).mean():.1%} of the AOI was wet at least 0.5% of the time "
          f"in 1999-2020 ({ntiles} tile(s))")
    print(f"  {'predictor':<34}{'AUC':>8}{'prec @ recall 70%':>20}")
    print("  " + "-" * 62)
    g = gih[ok].astype("float32")
    dn = -dist[ok]
    # a rank-average of the two best independent signals: how often it has been
    # wet, and how close the river is. Rank-average needs no fitting, so it
    # cannot quietly overfit the very truth it is being scored against.
    def rank(x):
        r = np.empty(len(x)); r[np.argsort(x, kind="mergesort")] = np.arange(len(x))
        return r / len(x)
    combo = rank(g) + rank(dn)
    rows = [("HAND", -h[ok]), ("elevation baseline", -e[ok]),
            ("distance to river", dn),
            ("Google inundation history", g),
            ("Google IH + distance, rank-avg", combo)]
    best = None
    for n_, sc in rows:
        a, p = auc(sc, y), p_at_r(sc, y)
        star = ""
        if best is None or a > best[1]:
            best = (n_, a)
        print(f"  {n_:<34}{a:8.3f}{p:20.3f}{star}")
    print(f"  best: {best[0]} at {best[1]:.3f}")
    return best


print("Google inundation history vs the predictors we already tested")
print("source: gs://flood-forecasting/inundation_history, CC-BY-4.0, GLAD 1999-2020")
run("PATNA 2019", (84.90, 25.45, 85.35, 25.75), "data/dem_route.tif",
    "data/hand.tif", "data/flood_mask.tif", "data/patna_baseline_vv.tif")
run("DELHI 2023", (77.10, 28.50, 77.40, 28.80), "data/delhi_dem.tif",
    "data/delhi_hand.tif", "data/delhi_flood_mask.tif", "data/delhi_base_vv.tif")
print("\n  target was precision above 0.50 at recall above 0.70.")
