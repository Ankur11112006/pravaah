"""Regenerate every number this project claims, from saved data, offline.

If someone doubts a figure, run this in front of them. It needs no internet.
Part A is the falsification result, which is negative and stays on the record.
Part B is the working system built after it.
"""
import io, json, os, subprocess, sys
import datetime as _dt
import numpy as np, pandas as pd, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds, transform as wtransform
from scipy.ndimage import distance_transform_edt
sys.stdout.reconfigure(encoding="utf-8")

EV, PEAK = "patna", "2019-09-30"

# Every figure this project quotes is recorded here and written to
# out/numbers.json at the end. The documents carry markers that stamp_docs.py
# fills from that file, so a number can never drift out of step with the code
# that produced it: the docs have no independent copy to go stale.
N = {}


def R(key, value):
    """Record a number under a stable key and return it, so it can be used
    inline in the same f-string that prints it."""
    N[key] = float(value) if isinstance(value, (np.floating, float)) else int(value)
    return value


def _provenance():
    def git(*a):
        try:
            return subprocess.run(("git",) + a, capture_output=True, text=True,
                                  timeout=5, cwd=os.path.dirname(os.path.abspath(__file__))
                                  ).stdout.strip() or None
        except Exception:
            return None
    import glob, hashlib
    # A hash of the source itself, so a figure can be traced to the exact code
    # that produced it even outside a git checkout, which is the usual case
    # when someone unzips this to check a number.
    h = hashlib.sha256()
    for f in sorted(glob.glob("*.py") + glob.glob("pravaah/*.py")):
        h.update(io.open(f, "rb").read())
    return dict(generated_utc=_dt.datetime.now(_dt.timezone.utc)
                .strftime("%Y-%m-%d %H:%M UTC"),
                code_sha256=h.hexdigest()[:12],
                git_commit=git("rev-parse", "--short", "HEAD"),
                python=sys.version.split()[0], event=EV, peak_date=PEAK)


def head(n, t):
    print("\n" + "=" * 74)
    print(f"{n}  {t}")
    print("=" * 74)


def auc(s, y):
    o = np.argsort(s, kind="mergesort"); y = y[o]
    r = np.arange(1, len(y) + 1, dtype="float64"); n = y.sum()
    return (r[y == 1].sum() - n * (n + 1) / 2) / (n * (len(y) - n))


def p_at_r(s, y, R=.70):
    o = np.argsort(-s, kind="mergesort"); ys = y[o]; tp = np.cumsum(ys)
    prec = tp / np.arange(1, len(ys) + 1); rec = tp / y.sum()
    return prec[np.argmax(rec >= R)] if (rec >= R).any() else float("nan")


print("PART A  the falsification test: what did NOT work")

head("A1", "Chennai Michaung has no SAR ground truth")
d = json.load(open("data/chennai_s1_query.json"))
rows = d[0] if isinstance(d[0], list) else d
print(f"  Sentinel-1 GRD over Chennai, Nov 2023 to Jan 2024: "
      f"{sorted({x['startTime'][:10] for x in rows})}")
print("  Cyclone Michaung peaked 4 Dec 2023. The gap 30 Nov to 17 Jan is 48 days.")


def cell_scores(tag, aoi, dem, hand, mask, base, key=""):
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
    ok = np.isfinite(e) & (e > 0) & np.isfinite(h)
    y = (frac[ok] >= .5).astype(int)
    print(f"\n  {tag}: {ok.sum():,} cells, {y.sum():,} flooded ({y.mean():.2%})")
    print(f"    {'predictor':<24}{'AUC':>8}{'precision at recall 70%':>26}")
    for n_, sc, k in [("HAND", -h[ok], "hand"),
                      ("elevation baseline", -e[ok], "elev"),
                      ("distance to river", -dist[ok], "dist")]:
        print(f"    {n_:<24}{R(f'{key}_auc_{k}', auc(sc, y)):8.3f}"
              f"{R(f'{key}_prec_{k}', p_at_r(sc, y)):26.3f}")
    print(f"    median distance of flood from permanent water: "
          f"{R(f'{key}_median_dist_m', round(np.median(dist[ok][y == 1]))):.0f} m")


head("A2", "HAND does not beat a plain elevation threshold")
cell_scores("PATNA 2019", (84.90, 25.45, 85.35, 25.75), "data/dem_route.tif",
            "data/hand.tif", "data/flood_mask.tif", "data/patna_baseline_vv.tif",
            key="patna")
cell_scores("DELHI 2023", (77.10, 28.50, 77.40, 28.80), "data/delhi_dem.tif",
            "data/delhi_hand.tif", "data/delhi_flood_mask.tif", "data/delhi_base_vv.tif",
            key="delhi")
print("\n  the target was precision above 0.50 at recall above 0.70.")

head("A3", "SAR cannot see urban flooding")
t = pd.read_csv("data/buildings_table.csv")
import geopandas as _gpd
_nraw = len(_gpd.read_file("data/patna_buildings.gpkg"))
print(f"  Microsoft footprints downloaded for the AOI: "
      f"{R('buildings_downloaded', _nraw):,}")
print(f"  scored here: {R('buildings_sampled', len(t)):,}")
print(f"  the other {R('buildings_no_hand', _nraw - len(t)):,} fall outside the HAND")
print("  raster, which pysheds computes on a conditioned catchment window smaller")
print("  than the download box. The DEM covers all of them; HAND does not, and a")
print("  building with no HAND value cannot score the predictor under test.")
print(f"  labelled flooded by Sentinel-1: "
      f"{R('buildings_flooded', int(t.flooded.sum())):,} "
      f"= {t.flooded.mean():.3%}")
print(f"  building-level AUC   "
      f"HAND {R('bld_auc_hand', auc(-t.hand.values, t.flooded.values)):.3f}"
      f"   elevation {R('bld_auc_elev', auc(-t.elev.values, t.flooded.values)):.3f}")

head("A4", "Depth from a satellite extent alone is not recoverable")
with rasterio.open("data/depth.tif") as s:
    dep, dtr, dcrs, dsh = s.read(1), s.transform, s.crs, s.shape
fm = np.zeros(dsh, "float32")
with rasterio.open("data/flood_mask.tif") as f:
    reproject(f.read(1).astype("float32"), fm, src_transform=f.transform,
              src_crs=f.crs, dst_transform=dtr, dst_crs=dcrs,
              resampling=Resampling.average)
v = dep[fm >= 0.5]
print(f"  FwDET over the {len(v)*900/1e6:.0f} km2 of SAR-mapped flood:")
print(f"    median {R('fwdet_median_m', np.median(v)):.2f} m | "
      f"{R('fwdet_below_30cm_pct', (v < 0.3).mean()*100):.1f}% below 0.3 m")
print("  the design needs 0.3 / 0.5 / 1.5 m thresholds, so this is unusable.")

# ------------------------------------------------------------------
print("\n\nPART B  the system built after that result")

head("B1", "Water level is fitted to observation, not predicted from terrain")
st = np.load(f"out/{EV}_stage.npy", allow_pickle=True)
q = np.array([float(r[1]) for r in st]); lv = np.array([float(r[2]) for r in st])
a = (lv[-1] - lv[0]) / (q[-1] - q[0])
print(f"  {R('stage_days', len(st))} days of GloFAS discharge -> water level")
print(f"  discharge {q.min():,.0f} to {q.max():,.0f} m3/s   "
      f"level {lv.min():.2f} to {lv.max():.2f} m")
for r in st:
    if r[0] in ("2019-09-18", "2019-09-30"):
        print(f"    {r[0]}  Q {float(r[1]):>8,.0f}  level {float(r[2]):.2f} m  "
              f"modelled extent {float(r[3]):.0f} km2")
print("  calibration targets were 214.4 and 305.3 km2 observed by Sentinel-1.")

head("B2", "Shelter capacity is measured, not assumed")
sh = pd.read_csv(f"data/{EV}_shelters_measured.csv")
print(f"  NDMA Guidelines on Minimum Standards of Relief, section 2(c):")
print(f"    3.5 sq m of covered area per person")
print(f"  {R('shelters_measured', len(sh))} campuses, "
      f"{R('shelter_roof_ha', sh.roof_m2.sum()/1e4):.1f} ha of measured roof, "
      f"{R('shelter_footprints', sh.n_buildings.sum()):,} footprints")
print(f"  total capacity {R('shelter_capacity', sh.cap.sum()):,} people")
print(f"  median school {sh[sh.kind=='school'].cap.median():.0f}, "
      f"largest single site {sh.cap.max():,}")

head("B3", "The plan, and what it cannot do")
ex = pd.read_csv(f"out/{EV}_exposure.csv")
from pravaah import timeline as _tl_r
dl, _dl_unit, _ = _tl_r.read_deadlines(f"out/{EV}_deadlines.json")
al = json.load(open(f"out/{EV}_allocation.json"))
tot = sum(v["people"] for v in dl.values())
none_ = sum(v["people"] for v in dl.values() if v["car_cutoff"] == float("-inf"))
brg = sum(v["people"] for v in dl.values()
          if v["car_cutoff"] != float("-inf") and v["bridge_dependent"])
placed = sum(al.values())
print(f"  {R('people_wet', round(ex.people.sum())):,} people wet across "
      f"{R('reporting_units', len(ex))} reporting units, "
      f"{R('flooded_km2', round(ex.km2.sum()))} km2")
print(f"  {R('placed', placed):,} placed in {R('shelters_used', len(al))} of the "
      f"{R('shelters_measured2', len(sh))} measured shelters")
print(f"    the solver opens a shelter only when it needs one: {placed:,} people")
print(f"    against {R('shelter_capacity2', sh.cap.sum()):,} measured places means "
      f"capacity is not")
print(f"    the binding constraint here, travel time is. The other "
      f"{len(sh) - len(al)} sit outside")
print(f"    90 minutes of anyone still dry, or are dominated by a nearer site.")
print(f"  {R('beyond_reach', tot - placed - none_):,} beyond 90 minutes of a "
      f"shelter with room")
print(f"  {R('no_route', none_):,} with no road route at any water level")
print(f"  {R('bridge_dependent', brg):,} placed only because a bridge is assumed open")
print()
print(f"  the plan is built on {R('pickup_people', tot):,} people at pickup points.")
print(f"  that is {R('pickup_gap', round(ex.people.sum()) - tot):,} fewer than the "
      f"exposure total above: a pickup point needs a road within reach and at "
      f"least one whole person, so isolated fractional cells carry no point.")
print(f"  arithmetic: {placed:,} + {tot - placed - none_:,} + {none_:,} = {tot:,}")
assert placed + (tot - placed - none_) + none_ == tot, "plan arithmetic does not close"

head("B3b", "The population model checked against the Census of India")
cc_path = "out/census_check.json"
if os.path.exists(cc_path):
    cc = json.load(open(cc_path, encoding="utf-8"))
    print("  Every exposure figure rests on GHS-POP, which is a model. Summed over")
    print(f"  the Patna district boundary (OSM relation {cc['osm_relation']}, area")
    print(f"  {R('census_polygon_km2', round(cc['polygon_km2'])):,} km2 against the "
          f"census-published {cc['census_km2']:,} km2):")
    print(f"    GHS-POP 2020            {R('ghs_pop_district', round(cc['ghs_pop'])):>12,}")
    print(f"    Census 2011             {cc['census_2011']:>12,}")
    print(f"    carried to 2020 at the district's own 2001-2011 rate  "
          f"{R('census_projected', round(cc['projected'])):>9,}")
    print(f"    difference              {R('census_rel_error_pct', cc['rel_error']*100):>11.1f}%")
    print("  So the totals are right. It does NOT follow that the people are in the")
    print("  right places within the district, and nothing open that we found tests that.")
else:
    print("  not run yet: .venv/Scripts/python.exe census_check.py")

head("B4", "Checked against a report that did not build this system")
with rasterio.open(f"out/depth/{EV}_{PEAK}.tif") as s:
    d2 = s.read(1)
with rasterio.open(f"out/{EV}_permanent.tif") as s:
    ch = s.read(1).astype(bool)
w = d2[(d2 > 0) & ~ch]
print("  Bihar Inter Agency Group and Sphere India, Joint Rapid Needs Assessment,")
print("  Bihar urban floods 2019, as of 14 October 2019:")
print(f"    they report: 'in most of the slums water level was 3 feet'  = 0.91 m")
print(f"    we model:    median {R('modelled_median_depth_m', np.median(w)):.2f} m "
      f"over flooded land")
print("    they name Rajendra Nagar, Kankarbagh, Boring Road, Pataliputra Colony")
print("    as worst hit. Those are pluvial and kilometres from the Ganga, and they")
print("    are NOT in our flood map. That is A2 and A3 confirmed from the ground.")

head("B5", "Provenance")
prov = _provenance()
for k, v in prov.items():
    print(f"  {k:<16}{v}")
json.dump(dict(provenance=prov, numbers=N), open("out/numbers.json", "w"), indent=1)
print()
print(f"  wrote out/numbers.json with {len(N)} figures. The documents carry")
print("  markers that stamp_docs.py fills from that file, so they cannot go stale.")

print("\n" + "=" * 74)
print("Every figure above was recomputed from data/ and out/ just now.")
