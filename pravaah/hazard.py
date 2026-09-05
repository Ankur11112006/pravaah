"""Hazard layer: river discharge -> water level -> depth, per timestep.

The terrain is NOT used to predict where water goes; that failed the
falsification test. It is used to fill a water surface whose LEVEL is fitted to
observed satellite extent at known discharge. Two observations give the line,
GloFAS gives the time series, and the time dimension falls out."""
import json, urllib.parse, urllib.request
import numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds, transform as wtransform
from scipy.ndimage import label

PX_KM2 = 900/1e6

def discharge(lat, lon, start, end):
    """GloFAS daily river discharge. Free, no key, historical and forecast."""
    q = urllib.parse.urlencode(dict(latitude=lat, longitude=lon, start_date=start,
                                    end_date=end, daily="river_discharge"))
    with urllib.request.urlopen(
            "https://flood-api.open-meteo.com/v1/flood?" + q, timeout=90) as r:
        d = json.load(r)["daily"]
    return dict(zip(d["time"], d["river_discharge"]))

def terrain(ev, dem_path):
    with rasterio.open(dem_path) as d:
        w = from_bounds(*ev.aoi, d.transform).round_offsets().round_lengths()
        dem = d.read(1, window=w).astype("float32")
        return dem, wtransform(w, d.transform), d.crs

def _regrid(path, shape, tr, crs, fn=lambda a: a):
    with rasterio.open(path) as s:
        o = np.zeros(shape, "float32")
        reproject(fn(s.read(1).astype("float32")), o, src_transform=s.transform,
                  src_crs=s.crs, dst_transform=tr, dst_crs=crs,
                  resampling=Resampling.average)
    return o

def observed(ev, shape, tr, crs, mask_path, base_path):
    from .config import WATER_DB
    new = _regrid(mask_path, shape, tr, crs) >= .5
    def water(a):
        a = a.copy(); a[a <= 0] = np.nan
        return (10*np.log10(a) < WATER_DB).astype("float32")
    perm = _regrid(base_path, shape, tr, crs, water) >= .5
    return perm, new

def flood_at(dem, seed, level):
    """Everything below `level` that is hydraulically connected to the channel."""
    below = (dem < level) & np.isfinite(dem)
    lab, _ = label(below, np.ones((3, 3)))
    keep = np.unique(lab[seed & (lab > 0)])
    return np.isin(lab, keep) & below

def calibrate(dem, seed, targets_km2, step=0.05):
    """Fit the water level that reproduces each observed extent. Two points give
    a stage-discharge line; we refuse to extrapolate far outside them."""
    lo, hi = np.nanpercentile(dem, 1), np.nanpercentile(dem, 65)
    levels = np.arange(lo, hi, step)
    areas = np.array([flood_at(dem, seed, l).sum()*PX_KM2 for l in levels])
    out = {}
    for key, target in targets_km2.items():
        i = int(np.argmin(np.abs(areas - target)))
        err = abs(float(areas[i]) - float(target)) / max(float(target), 1e-9)
        out[key] = dict(level=float(levels[i]), model_km2=float(areas[i]),
                        target_km2=float(target), rel_err=err)
    return out

def check_fit(cal, tol=0.15):
    """Refuse a calibration that does not reproduce what was observed.

    Without this the search silently returns its closest guess, which for a
    narrow river can be the same level for both dates and a modelled extent
    fifty times too small. A confident wrong number is worse than none, so
    this raises instead of letting the rest of the pipeline run."""
    bad = {k: v for k, v in cal.items() if v["rel_err"] > tol}
    if not bad:
        return
    msg = ["CALIBRATION REJECTED: no water level reproduces the observed extent",
           f"within {tol:.0%} on:"]
    for k, v in bad.items():
        msg.append(f"    {k}: fitted {v['level']:.2f} m gives {v['model_km2']:.1f} km2, "
                   f"observed {v['target_km2']:.1f} km2 ({v['rel_err']:.0%} off)")
    msg += ["  Nothing downstream would be meaningful, so this stops here.",
            "  Likely causes: the AOI is too small for the level search, the",
            "  permanent-water seed is empty, or the flood is not river-driven."]
    raise SystemExit("\n".join(msg))


def stage_line(cal, q, log_space=True):
    """Stage as a function of discharge, through the two calibration points.

    A real rating curve is a power law, Q = a(h-h0)^b with b around 1.5 to 2.5,
    so stage grows roughly as Q^0.4 to Q^0.67, not linearly. Two points cannot
    fit three parameters, but fitting in log(Q) instead of Q gives the same exact
    pass through both observations while bending the right way outside them: a
    straight line in Q keeps climbing at the same rate for ever, which is wrong
    at high flow, where a wide floodplain absorbs discharge with little rise.

    Returns (a, b, (qlo, qhi), log_space). Level is a*ln(Q)+b when log_space,
    else a*Q+b. The range is returned so callers can mark extrapolation."""
    ks = list(cal)
    assert len(ks) == 2, "two calibration points expected"
    q1, l1 = q[ks[0]], cal[ks[0]]["level"]
    q2, l2 = q[ks[1]], cal[ks[1]]["level"]
    if log_space and q1 > 0 and q2 > 0:
        x1, x2 = np.log(q1), np.log(q2)
    else:
        log_space = False
        x1, x2 = q1, q2
    a = (l2 - l1) / (x2 - x1)
    return a, l1 - a * x1, (min(q1, q2), max(q1, q2)), log_space


def level_at(a, b, Q, log_space=True):
    """Apply the stage relation to a discharge."""
    return a * (np.log(Q) if log_space and Q > 0 else Q) + b


def osm_water(shape, tr, path):
    """OSM's own mapped water bodies, burned onto the caller's grid.

    A C-Flood event has no radar baseline to say what was already river, so
    without this the Mahanadi channel entered its own flood as land: the mask
    printed "0 km2 from the low-flow run" and nothing was excluded. OSM maps the
    delta's channels, and a river somebody has drawn is better evidence than a
    model run we do not have."""
    import json, os
    if not os.path.exists(path):
        return np.zeros(shape, bool)
    from rasterio.features import rasterize
    from shapely.geometry import Polygon, mapping
    polys = []
    for e in json.load(open(path, encoding="utf-8"))["elements"]:
        g = e.get("geometry") or []
        if len(g) < 4:
            continue
        ring = [(p["lon"], p["lat"]) for p in g]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        try:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if not poly.is_empty:
                polys.append(mapping(poly))
        except Exception:
            continue
    if not polys:
        return np.zeros(shape, bool)
    return rasterize(polys, out_shape=shape, transform=tr,
                     fill=0, default_value=1, dtype="uint8").astype(bool)


def buildings_path(ev_name, aoi, folder="data"):
    """The footprint file that actually covers this AOI, and which one it is.

    Microsoft's Global ML Buildings is the default source, but its coverage ends
    at longitude 86.247 in the Mahanadi delta, leaving 51% of that AOI's
    population with no footprint at all and every official cyclone shelter there
    unmeasurable. Google Open Buildings v3 covers the same ground. Rather than
    hardcode one per event, take whichever spans the AOI, prefer Microsoft when
    both do, and say out loud which was used: a silent switch between sources is
    how a number changes for a reason nobody can find later."""
    import os
    import geopandas as gpd
    cands = [(f"{folder}/{ev_name}_buildings.gpkg", "Microsoft Global ML Buildings"),
             (f"{folder}/{ev_name}_buildings_google.gpkg", "Google Open Buildings v3")]
    tried = []
    for path, label in cands:
        if not os.path.exists(path):
            continue
        b = gpd.read_file(path)
        bb = b.total_bounds
        gap = max(bb[0] - aoi[0], aoi[2] - bb[2], bb[1] - aoi[1], aoi[3] - bb[3])
        tried.append((path, label, len(b), gap))
        if gap <= 0.02:                                   # about 2 km
            print(f"  buildings: {label}, {len(b):,} footprints covering the AOI")
            return path
    if not tried:
        raise SystemExit(f"no building footprints for {ev_name}; run "
                         f"fetch_buildings.py {ev_name}")
    msg = [f"NO BUILDING FILE COVERS THE {ev_name.upper()} AOI {aoi}:"]
    for path, label, n, gap in tried:
        msg.append(f"    {path}  {label}, {n:,} footprints, "
                   f"short by {gap:.3f} degrees")
    msg.append("  Refusing to measure roofs against a file with a hole in it.")
    msg.append(f"  Try: fetch_google_buildings.py {ev_name}")
    raise SystemExit(chr(10).join(msg))


def named_places(path):
    """OSM place points that can actually be used as a reporting unit label.

    A point with no name cannot be told to anyone: Delhi had 17 of them, and the
    nearest-point assignment gave the largest flooded unit in the city the name
    "?", which then went out in an SMS. An unnamed point is dropped rather than
    labelled, so its cells fall to the nearest place that does have a name."""
    import json
    els = json.load(open(path, encoding="utf-8"))["elements"]
    out = []
    for e in els:
        t = e.get("tags", {})
        nm = (t.get("name") or t.get("name:en") or t.get("official_name") or "").strip()
        if nm and "lon" in e and "lat" in e:
            out.append((e["lon"], e["lat"], nm))
    dropped = len(els) - len(out)
    if dropped:
        print(f"  {dropped} OSM place points have no usable name and are dropped; "
              f"their cells go to the nearest named place")
    if not out:
        raise SystemExit(f"no named place points in {path}; every reporting unit "
                         f"would be anonymous")
    return out


def widen_channel(dem, perm, buildings=None):
    """Add the parts of the river the radar missed, using the DEM's own flatness.

    Copernicus GLO-30 flattens inland water to a single elevation, so a patch of
    river reads as a perfect plateau. The SAR permanent-water mask misses the
    sandbars and side channels that were dry on the baseline date, and every one
    of those then enters the flood as land under a constant depth: at Patna one
    "ward" came out with a median and a maximum both exactly 8.70 m, which is
    the water surface minus a flat bed, not a flood.

    A flat patch alone is not proof, so only patches CONNECTED to known permanent
    water count, and a patch with building footprints on it is kept as land: the
    Ganga diara are inhabited sandbars, and a roof is better evidence of ground
    than a DEM is of water.

    Returns the widened permanent mask."""
    from scipy.ndimage import (minimum_filter, maximum_filter, binary_dilation,
                               label as _label)
    flat = (maximum_filter(dem, 3) - minimum_filter(dem, 3)) == 0
    lab, _ = _label(flat | perm, np.ones((3, 3)))
    keep = np.unique(lab[perm & (lab > 0)])
    channel = np.isin(lab, keep) & flat
    if buildings is not None and buildings.any():
        channel &= ~binary_dilation(buildings, np.ones((5, 5)))  # ~60 m of a roof
    return perm | channel


def building_mask(shape, tr, path):
    """Building footprint centroids burned onto the caller's grid."""
    import os
    if not os.path.exists(path):
        return np.zeros(shape, bool)
    import geopandas as gpd, warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")     # centroid of a geographic CRS, close enough
        c = gpd.read_file(path).geometry.centroid
    col, row = (~tr) * (c.x.values, c.y.values)
    row, col = np.floor(row).astype(int), np.floor(col).astype(int)
    ok = (row >= 0) & (row < shape[0]) & (col >= 0) & (col < shape[1])
    m = np.zeros(shape, bool)
    m[row[ok], col[ok]] = True
    return m


def fwdet_depth(dem, wet, permanent):
    """Depth from an observed extent alone, when no water level can be fitted.

    The flood edge against dry land is the water surface; propagate that
    elevation inward and subtract the ground. Used where the stage model is
    rejected, for instance an embanked river whose area-level curve is a cliff
    rather than a curve. It gives one snapshot and NO time dimension, and the
    caller is expected to say so."""
    from scipy.ndimage import distance_transform_edt, binary_erosion, uniform_filter
    water = wet | permanent
    edge = water & ~binary_erosion(water, np.ones((3, 3)))
    _, idx = distance_transform_edt(~edge, return_indices=True)
    wse = uniform_filter(dem[idx[0], idx[1]], size=9)
    d = np.where(wet & ~permanent, wse - dem, 0.0).astype("float32")
    d[d < 0] = 0.0
    return d


def population(shape, tr, crs, aoi, folder="data"):
    """GHS-POP on the caller's grid, picking the right global tile from the AOI.

    The tiles are 10 degrees. Hardcoding one silently returns zeros for any AOI
    outside it, which is exactly how Delhi came back with nobody living in it.
    """
    import glob, os
    w, s, e, n = aoi
    need = set()
    for lon in (w, e):
        for lat in (s, n):
            need.add((int((90 - lat) // 10) + 1, int((lon + 180) // 10) + 1))
    out = np.zeros(shape, "float32")
    for row, col in sorted(need):
        pat = os.path.join(folder, f"GHS_POP_*_R{row}_C{col}.tif")
        hit = glob.glob(pat)
        if not hit:
            raise SystemExit(
                f"POPULATION TILE MISSING for R{row}_C{col}, which covers this AOI.\n"
                f"  expected something matching {pat}\n"
                f"  get it from the GHSL R2023A 4326_3ss tile set, or exposure will\n"
                f"  silently report nobody living here.")
        with rasterio.open(hit[0]) as s_:
            part = np.zeros(shape, "float32")
            reproject(s_.read(1).astype("float32"), part, src_transform=s_.transform,
                      src_crs=s_.crs, dst_transform=tr, dst_crs=crs,
                      resampling=Resampling.average)
        out = np.maximum(out, part)
    return out * (900 / 10000)          # 100 m counts -> per 30 m cell


def sanity_check_gauge(q_series, ref_2yr, name=""):
    """Is the discharge we pulled even the right river?

    Gauge coordinates get typed by hand and HydroBASINS has an outlet on every
    drain, so a point a few hundred metres off returns a tributary. Delhi's
    hand-picked point gave 22 m3/s for the Yamuna in flood while Google's
    main-stem 2-year return period there is 1,989. Compare the two and refuse
    an order-of-magnitude mismatch instead of modelling a ditch."""
    vals = [v for v in q_series.values() if v]
    if not vals or not ref_2yr:
        return
    peak = max(vals)
    if peak < ref_2yr / 10 or peak > ref_2yr * 10:
        raise SystemExit(
            f"GAUGE MISMATCH{' for ' + name if name else ''}: the discharge series "
            f"peaks at {peak:,.0f} m3/s, but the nearest main stem has a 2-year "
            f"return period of {ref_2yr:,.0f} m3/s.\n"
            f"  That is not the same river. Move the gauge point in config onto "
            f"the main channel.")


def main_stem_gauge(lat, lon, radius_km=25, cache="data/_gauge_cache.json"):
    """The Google Flood Hub outlet for the MAIN RIVER near a point, with its
    return periods.

    HydroBASINS puts an outlet on every small catchment, so the nearest one is
    usually a drain: at Patna it gave the Ganga a 200-year flood of 148 m3/s.
    Pick the largest within the radius instead. Source is
    gs://flood-forecasting, CC-BY-4.0."""
    import json as _json, os
    key = f"{lat:.4f},{lon:.4f},{radius_km}"
    if os.path.exists(cache):
        c = _json.load(open(cache))
        if key in c:
            return c[key]
    import zarr, fsspec
    B = ("https://storage.googleapis.com/flood-forecasting/hydrologic_predictions"
         "/model_id_8583a5c2_v0")
    op = lambda p: zarr.open(fsspec.get_mapper(f"{B}/{p}"), mode="r")
    loc = op("hybas_outlet_locations_UNOFFICIAL.zarr")
    la, lo, gid = loc["latitude"][:], loc["longitude"][:], loc["gauge_id"][:]
    rp = op("return_periods.zarr")
    idx = {g: i for i, g in enumerate(rp["gauge_id"][:])}
    periods = sorted(int(k.split("_")[-1]) for k in rp.array_keys()
                     if k.startswith("return_period_"))
    two = rp["return_period_2"][:]
    d = np.hypot(la - lat, lo - lon) * 111.0
    cand = [(i, idx[gid[i]]) for i in np.nonzero(d < radius_km)[0] if gid[i] in idx]
    if not cand:
        raise SystemExit(f"no Google outlet with return periods within "
                         f"{radius_km} km of {lat},{lon}")
    k, j = max(cand, key=lambda c: two[c[1]])
    out = dict(gauge_id=str(gid[k]), lat=float(la[k]), lon=float(lo[k]),
               km_away=float(d[k]),
               rp={str(p): float(rp[f"return_period_{p}"][j]) for p in periods})
    c = _json.load(open(cache)) if os.path.exists(cache) else {}
    c[key] = out
    _json.dump(c, open(cache, "w"), indent=1)
    return out


def ensemble(lat, lon, days=30):
    """GloFAS 50-member ensemble discharge forecast. Free, no key."""
    q = urllib.parse.urlencode(dict(
        latitude=lat, longitude=lon, forecast_days=days, ensemble="true",
        daily="river_discharge"))
    with urllib.request.urlopen(
            "https://flood-api.open-meteo.com/v1/flood?" + q, timeout=90) as r:
        d = json.load(r)["daily"]
    members = [k for k in d if k.startswith("river_discharge_member")]
    arr = np.array([[d[m][i] for m in members] for i in range(len(d["time"]))],
                   dtype="float64")
    return d["time"], arr          # (days, members)
