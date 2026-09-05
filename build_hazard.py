"""Produce the hazard layer for one event.

Two modes, chosen in config because they are a property of the river, not a
preference:

  stage     Fit a water level to the extent Sentinel-1 observed at known GloFAS
            discharge, then drive that level with the discharge series. Gives a
            depth raster per day and therefore a time dimension.

  observed  No level reproduces the observed extent, so take depth from the
            extent itself. One snapshot. Everything downstream that needs time
            is skipped rather than faked.
"""
import os, sys
import numpy as np, rasterio
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import config, hazard

ev = config.EVENTS[sys.argv[1] if len(sys.argv) > 1 else "patna"]
dem_p = ev.dem
mask_p = ev.sar_mask or None
base_p = ev.sar_baseline or None
end = ev.end_date or None
PX = hazard.PX_KM2

if ev.hazard == "cflood":
    # C-Flood publishes the depth field directly. Nothing is fitted here: we
    # clip its frames to the AOI and write them out on our own 30 m grid.
    import numpy as _np, rasterio as _rio
    from rasterio.warp import reproject as _rp, Resampling as _Rs
    from rasterio.windows import from_bounds as _fb, transform as _wt
    from pravaah import cflood

    with _rio.open(dem_p) as d:
        w = _fb(*ev.aoi, d.transform).round_offsets().round_lengths()
        dem = d.read(1, window=w).astype("float32")
        tr, crs = _wt(w, d.transform), d.crs
    prof = dict(driver="GTiff", height=dem.shape[0], width=dem.shape[1], count=1,
                dtype="float32", crs=crs, transform=tr, nodata=_np.nan,
                compress="deflate")

    # Optional run date: `build_hazard.py mahanadi 30_07_2025`. Without it the
    # newest run is used, which on a quiet day contains no flood at all.
    want = sys.argv[2] if len(sys.argv) > 2 else None
    if want:
        caps = cflood.capabilities()
        hit = [(d_, w_, l_) for d_, w_, l_ in cflood.runs(caps)
               if w_ == f"workspace_{want}"]
        if not hit:
            raise SystemExit(f"no C-Flood run published for {want}")
        day, ws, ly = hit[0]
        frames = cflood.frames(ws, ly)
        if not frames:
            raise SystemExit(f"workspace_{want} exists but publishes no frames")
    else:
        day, ws, frames = cflood.latest()
    print(f"{ev.name}: mode=cflood   C-Flood run {day} ({ws})")
    print(f"  frames at {sorted(frames)} hours ahead, 30 m, depth in metres")
    os.makedirs("out/depth", exist_ok=True)
    got, stack = [], None
    for h in sorted(frames):
        # the run date MUST be in the cache key: without it a second run
        # silently reuses the first run's frames and prints identical numbers
        raw = f"tmp/cflood_{ev.name}_{day}_{h}.tif"
        if not os.path.exists(raw):
            n = cflood.fetch(ws, frames[h], raw)
            print(f"    +{h:>2} h  downloaded {n/1e6:.0f} MB")
        out = _np.zeros(dem.shape, "float32")
        with _rio.open(raw) as s_:
            _rp(s_.read(1), out, src_transform=s_.transform, src_crs=s_.crs,
                dst_transform=tr, dst_crs=crs, resampling=_Rs.bilinear)
        # Drop speckle: isolated patches below MIN_PATCH_KM2. They are shallow,
        # mostly just above the wet threshold, and 91% of the ones on high
        # ground are not connected to the flood at all.
        from scipy.ndimage import label as _lb
        wet = out > config.WET_M
        lb, _n = _lb(wet, _np.ones((3, 3)))
        sz = _np.bincount(lb.ravel()); sz[0] = 0
        small = _np.isin(lb, _np.nonzero(sz * PX < config.MIN_PATCH_KM2)[0])
        dropped = float((wet & small).sum() * PX)
        out = _np.where(small, 0.0, out).astype("float32")
        wet = out > config.WET_M
        big = int(_np.argmax(sz)) if sz.max() else 0
        conn = float((lb == big).sum() * PX)

        path = f"out/depth/{ev.name}_{day}_{h:02d}.tif"
        with _rio.open(path, "w", **prof) as o: o.write(out, 1)
        print(f"    +{h:>2} h  {wet.sum()*PX:7.1f} km2 wet, median "
              f"{(_np.median(out[wet]) if wet.any() else 0):.2f} m   "
              f"({conn:.0f} km2 in one connected body, {dropped:.0f} km2 of "
              f"speckle dropped)")
        got.append((day, h, path, float(wet.sum()*PX)))

    # Permanent water = what C-Flood itself shows on a LOW-FLOW day. Two earlier
    # attempts were both wrong: intersecting this run's own frames masks out any
    # sustained flood, and OSM water polygons caught only 8 km2 in a delta. A dry
    # baseline from the same model is the same trick the Patna SAR baseline uses.
    base_day = sys.argv[3] if len(sys.argv) > 3 else None
    if base_day:
        bhit = [(d_, w_, l_) for d_, w_, l_ in cflood.runs()
                if w_ == f"workspace_{base_day}"]
        if not bhit:
            raise SystemExit(f"no C-Flood run published for baseline {base_day}")
        bday, bws, bly = bhit[0]
        bframes = cflood.frames(bws, bly)
        bh = sorted(bframes)[0]
        braw = f"tmp/cflood_{ev.name}_{bday}_{bh}.tif"
        if not os.path.exists(braw):
            cflood.fetch(bws, bframes[bh], braw)
        bout = _np.zeros(dem.shape, "float32")
        with _rio.open(braw) as s_:
            _rp(s_.read(1), bout, src_transform=s_.transform, src_crs=s_.crs,
                dst_transform=tr, dst_crs=crs, resampling=_Rs.bilinear)
        stack = bout > config.WET_M
        print(f"  permanent water from the low-flow run {bday}: "
              f"{stack.sum()*PX:.1f} km2")
    else:
        # No baseline run to compare against, so fall back to the channels OSM
        # has mapped. Without any seed the delta's own river counted as flood.
        stack = hazard.osm_water(dem.shape, tr,
                                 f"data/{ev.name}_osm_water.json")
        if stack.any():
            print(f"  no baseline run given; seeding the channel from OSM water: "
                  f"{stack.sum()*PX:.1f} km2")
        else:
            print("  no baseline run AND no OSM water: the river will be counted "
                  "as flood, and every figure below is an overestimate")
    # Same correction as the radar path: a low-flow model run misses the river
    # it was too dry to wet, and that bed then enters the flood as land under a
    # constant depth. The delta needs this more than Patna did, not less.
    _s0 = stack
    stack = hazard.widen_channel(
        dem, stack, hazard.building_mask(dem.shape, tr,
                                         hazard.buildings_path(ev.name, ev.aoi)))
    print(f"  channel: {_s0.sum()*PX:.0f} km2 from the low-flow run + "
          f"{(stack & ~_s0).sum()*PX:.0f} km2 of flat riverbed it missed")
    with _rio.open(f"out/{ev.name}_permanent.tif", "w",
                   **(prof | {"dtype": "uint8", "nodata": None})) as o:
        o.write(stack.astype("uint8"), 1)

    _np.save(f"out/{ev.name}_frames.npy", _np.array(got, dtype=object),
             allow_pickle=True)
    print(f"  wrote {len(got)} depth frames")
    raise SystemExit(0)

dem, tr, crs = hazard.terrain(ev, dem_p)
perm, new = hazard.observed(ev, dem.shape, tr, crs, mask_p, base_p)
PX = hazard.PX_KM2
prof = dict(driver="GTiff", height=dem.shape[0], width=dem.shape[1], count=1,
            dtype="float32", crs=crs, transform=tr, nodata=np.nan, compress="deflate")

# The river channel is not a flood. Nobody lives in it, and counting it inflates
# exposure with a constant depth wherever the DEM reads the water surface.
# The radar misses the parts that were dry sandbar on the baseline date, so the
# DEM's own water-flattening is used to find the rest, sparing anywhere with
# buildings on it because the diara are inhabited.
# Two masks, because they answer two different questions and conflating them
# corrupts the fit. `perm` is what the radar actually saw as water on the
# baseline date: it seeds the level search and sets the area targets, so it must
# stay exactly as observed. `channel` additionally swallows the flat sandbars the
# radar missed, and is used only downstream to decide what is river rather than
# flooded land. Widening `perm` instead moved the calibration targets by 26 km2
# and pushed the fitted level up 20 cm, which is a fabricated flood.
channel = hazard.widen_channel(
    dem, perm, hazard.building_mask(dem.shape, tr,
                                    hazard.buildings_path(ev.name, ev.aoi)))
with rasterio.open(f"out/{ev.name}_permanent.tif", "w",
                   **(prof | {"dtype": "uint8", "nodata": None})) as o:
    o.write(channel.astype("uint8"), 1)
print(f"{ev.name}: mode={ev.hazard}")
print(f"  observed water  {ev.sar_base} {perm.sum()*PX:.1f} km2 | "
      f"{ev.sar_flood} {(perm | new).sum()*PX:.1f} km2")
print(f"  channel for exposure: {perm.sum()*PX:.0f} km2 seen by radar + "
      f"{(channel & ~perm).sum()*PX:.0f} km2 of flat riverbed it missed "
      f"= {channel.sum()*PX:.0f} km2 -> out/{ev.name}_permanent.tif")
print(f"  the level search still uses the {perm.sum()*PX:.0f} km2 the radar saw, "
      f"not the widened mask")

if ev.hazard == "observed":
    d = hazard.fwdet_depth(dem, new, perm)
    path = f"out/depth/{ev.name}_{ev.sar_flood}.tif"
    with rasterio.open(path, "w", **prof) as o:
        o.write(d, 1)
    v = d[new & ~perm]
    print(f"\n  NO TIME DIMENSION. This event has one depth snapshot, taken from"
          f"\n  the satellite extent of {ev.sar_flood}. Road closure times and the"
          f"\n  last feasible evacuation start cannot be computed for it.")
    print(f"  flooded land {len(v)*PX:.1f} km2   depth median {np.median(v):.2f} m, "
          f"p90 {np.percentile(v, 90):.2f} m")
    print(f"  wrote {path}")
    raise SystemExit(0)

# ---- stage mode ----
targets = {ev.sar_base: perm.sum()*PX, ev.sar_flood: (perm | new).sum()*PX}
cal = hazard.calibrate(dem, perm, targets)
for d_, c in cal.items():
    print(f"  fit {d_}: level {c['level']:.2f} m -> {c['model_km2']:.1f} km2 "
          f"(target {c['target_km2']:.1f}, error {c['model_km2']-c['target_km2']:+.1f}, "
          f"{c['rel_err']:.0%})")
hazard.check_fit(cal)

q = hazard.discharge(*ev.gauge, min(cal), end)
a, b, (qlo, qhi), logsp = hazard.stage_line(cal, q)
form = f"{a:.4f} * ln(Q) + {b:.2f}" if logsp else f"{a:.3e} * Q + {b:.2f}"
print(f"  stage-discharge: level = {form}")
print(f"    fitted in log(Q) space, a rating curve is a power law not a line")
print(f"    calibrated between {qlo:,.0f} and {qhi:,.0f} m3/s")

print(f"\n  {'date':<12}{'Q m3/s':>10}{'level m':>9}{'flooded km2':>13}{'':>14}")
rows = []
for date in sorted(q):
    Q = q[date]
    if Q is None:
        continue
    lvl = hazard.level_at(a, b, Q, logsp)
    fl = hazard.flood_at(dem, perm, lvl)
    with rasterio.open(f"out/depth/{ev.name}_{date}.tif", "w", **prof) as o:
        o.write(np.where(fl, lvl - dem, 0).astype("float32"), 1)
    ex = "" if qlo <= Q <= qhi else "  extrapolated"
    print(f"  {date:<12}{Q:10,.0f}{lvl:9.2f}{fl.sum()*PX:13.1f}{ex:>14}")
    rows.append((date, Q, lvl, fl.sum()*PX))
np.save(f"out/{ev.name}_stage.npy", np.array(rows, dtype=object), allow_pickle=True)
print(f"\nwrote {len(rows)} depth rasters to out/depth/")
