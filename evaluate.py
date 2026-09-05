"""The falsification test. Does HAND beat a plain elevation threshold?
Run at two units: per building (as the spec says) and per 30 m ground cell."""
import numpy as np, pandas as pd, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds

AOI = (84.90, 25.45, 85.35, 25.75)

def auc(score, y):
    """Rank-based ROC AUC. score = higher means more likely flooded."""
    o = np.argsort(score, kind="mergesort"); y = y[o]
    r = np.arange(1, len(y)+1, dtype="float64")
    npos, nneg = y.sum(), len(y)-y.sum()
    return (r[y==1].sum() - npos*(npos+1)/2) / (npos*nneg)

def sweep(score, y):
    """Best achievable F1 over all thresholds, plus precision at recall>=0.70."""
    o = np.argsort(-score, kind="mergesort"); ys = y[o]
    tp = np.cumsum(ys); fp = np.cumsum(1-ys); npos = y.sum()
    prec = tp/(tp+fp); rec = tp/npos
    f1 = np.where(prec+rec > 0, 2*prec*rec/np.maximum(prec+rec, 1e-12), 0)
    i = int(np.argmax(f1))
    j = np.argmax(rec >= 0.70) if (rec >= 0.70).any() else -1
    return dict(auc=auc(score, y), bestF1=f1[i], P_at_bestF1=prec[i], R_at_bestF1=rec[i],
                thr=score[o][i], flagged_frac=(i+1)/len(y),
                P_at_R70=(prec[j] if j >= 0 else np.nan))

def report(title, y, feats):
    print(f"\n{'='*74}\n{title}\n  n={len(y):,}  flooded={int(y.sum()):,} ({y.mean():.3%})\n{'-'*74}")
    print(f"  {'predictor':<22}{'AUC':>7}{'bestF1':>9}{'prec':>8}{'recall':>8}{'P@R=70%':>10}")
    for name, s in feats:
        m = sweep(s, y)
        print(f"  {name:<22}{m['auc']:7.3f}{m['bestF1']:9.3f}{m['P_at_bestF1']:8.3f}"
              f"{m['R_at_bestF1']:8.3f}{m['P_at_R70']:10.3f}")
    print(f"  {'random':<22}{0.5:7.3f}{'':9}{'':8}{'':8}{y.mean():10.3f}")

# ---------- unit 1: buildings ----------
df = pd.read_csv("data/buildings_table.csv")
report("UNIT 1 - PER BUILDING (as the spec specifies)",
       df.flooded.values.astype(int),
       [("HAND (lower=wetter)", -df.hand.values), ("elevation baseline", -df.elev.values)])

# ---------- unit 2: 30 m ground cells ----------
with rasterio.open("data/hand.tif") as h:
    win = from_bounds(*AOI, h.transform).round_offsets().round_lengths()
    hand = h.read(1, window=win); tr = h.window_transform(win); crs = h.crs
with rasterio.open("data/dem_route.tif") as e:
    elev = e.read(1, window=win)
with rasterio.open("data/flood_mask.tif") as f:
    frac = np.zeros(hand.shape, "float32")
    reproject(f.read(1).astype("float32"), frac, src_transform=f.transform, src_crs=f.crs,
              dst_transform=tr, dst_crs=crs, resampling=Resampling.average)

ok = np.isfinite(hand) & np.isfinite(elev) & (elev > 0)
y = (frac[ok] >= 0.5).astype(int)
report("UNIT 2 - PER 30 m GROUND CELL (open-water extent)",
       y, [("HAND (lower=wetter)", -hand[ok]), ("elevation baseline", -elev[ok])])

# the literal baseline from the spec, adapted: Patna sits at ~50 m, not 5 m
print(f"\n  spec's literal 'below 5 m elevation' rule at Patna flags "
      f"{(elev[ok] < 5).mean():.2%} of cells -> unusable, threshold is coastal.")
print(f"  elevation percentiles here: "
      f"{np.round(np.percentile(elev[ok], [1,5,25,50,75,99]),1)}")
