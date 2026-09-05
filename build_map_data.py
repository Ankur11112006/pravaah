"""Pack everything the control-room map needs into one compact JSON, per event.

Three districts, and time means three different things across them. The page has
to say which one it is showing rather than drawing one convention under another
district's name:

  patna     a water level fitted to the observed satellite extent, hourly. The
            flood layer is terrain below a level, so it moves continuously with
            the slider and the roads follow from their own bed elevation.
  mahanadi  C-Flood publishes the depth field itself, eight frames three hours
            apart. Nothing is fitted and nothing is inferred from terrain: each
            frame is drawn as it was published.
  delhi     one observed snapshot, and no time dimension exists. The slider is
            withheld rather than animated from a number nobody measured.

This script used to refuse to run for the last two, which is why the control
room drew Patna's roads under every district's numbers. Refusing to invent a
level was right; refusing to draw the district at all was not.

    .venv/Scripts/python.exe build_map_data.py patna
"""
import base64, json, os, pickle, sys
import numpy as np
import rasterio
from rasterio.windows import from_bounds

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
from pravaah import config, timeline

name = sys.argv[1] if len(sys.argv) > 1 else "patna"
ev = config.EVENTS[name]
MODE = "level" if ev.hazard == "stage" else "frames"
STEP = 3                      # grid decimation, 30 m DEM -> ~90 m on screen
DSCALE = 0.05                 # depth quantisation, 5 cm per count, 0 = dry
EDGE_BUDGET = 12000           # roads a canvas can redraw at 60 fps
KEEP = {"motorway", "trunk", "primary", "secondary", "tertiary",
        "motorway_link", "trunk_link", "primary_link", "secondary_link",
        "tertiary_link"}

G = pickle.load(open(f"data/{name}_graph.pkl", "rb"))
print(f"{name}: {MODE} mode, {G.number_of_edges():,} road edges in the graph")


# ----------------------------------------------------------------- the grid
def block_max(a, k):
    """Reduce by k with a maximum, not by throwing away k-1 pixels in k.

    Point sampling a depth field loses thin features: the Yamuna through Delhi
    is two or three 30 m pixels wide, and taking every third pixel dropped most
    of a 12 km2 flood off the map. A maximum keeps the channel and errs towards
    showing water rather than hiding it, which is the right way to be wrong on a
    flood map.
    """
    h, w = a.shape
    h2, w2 = h // k * k, w // k * k
    return a[:h2, :w2].reshape(h2 // k, k, w2 // k, k).max(axis=(1, 3))


def window_read(path, band=1):
    """Read a raster clipped to the AOI, reduced, as float32."""
    with rasterio.open(path) as s:
        w = from_bounds(*ev.aoi, s.transform).round_offsets().round_lengths()
        a = s.read(band, window=w).astype("float32")
    return block_max(np.where(np.isfinite(a), a, 0.0), STEP)


if MODE == "level":
    # Elevation, so the flood layer moves with the slider instead of being a
    # stack of pre-rendered images. Connectivity is precomputed at the peak: a
    # cell shown is one that is both connected to the river then and below the
    # level now. Without that, every ditch in the district fills at once.
    from scipy.ndimage import label as cclabel
    from rasterio.warp import reproject, Resampling
    from rasterio.windows import transform as wtransform

    rows = np.load(f"out/{name}_stage.npy", allow_pickle=True)
    hrs, lv = timeline.hourly_levels(rows)
    peak = float(lv.max())

    with rasterio.open(ev.dem) as s_:
        win = from_bounds(*ev.aoi, s_.transform).round_offsets().round_lengths()
        dem_full = s_.read(1, window=win).astype("float32")
        dem_tr = wtransform(win, s_.transform)
    dem_s = dem_full[::STEP, ::STEP]

    base_path = f"data/{name}_base" + ("line_vv.tif" if name == "patna" else "_vv.tif")
    with rasterio.open(base_path) as s_:
        b = s_.read(1).astype("float32")
        b[b <= 0] = np.nan
        seed = np.zeros(dem_full.shape, "float32")
        reproject((10 * np.log10(b) < -15).astype("float32"), seed,
                  src_transform=s_.transform, src_crs=s_.crs,
                  dst_transform=dem_tr, dst_crs="EPSG:4326",
                  resampling=Resampling.average)
    seed = seed[::STEP, ::STEP] >= 0.5

    below = (dem_s < peak) & np.isfinite(dem_s)
    lab, _ = cclabel(below, np.ones((3, 3)))
    conn = np.isin(lab, np.unique(lab[seed & (lab > 0)])) & below

    GBASE, GSCALE = 39.0, 0.1
    q = np.clip((dem_s - GBASE) / GSCALE, 0, 254).astype("uint8")
    q[~np.isfinite(dem_s)] = 255
    q[~conn] = 255                        # 255 = never floods, do not paint
    grid = dict(kind="ground", w=int(q.shape[1]), h=int(q.shape[0]),
                base=GBASE, scale=GSCALE,
                data=base64.b64encode(q.tobytes()).decode())
    times = [h.isoformat() for h in hrs]
    levels = [round(float(x), 3) for x in lv]
    peak_depth = np.where(conn, peak - dem_s, 0.0)
    print(f"  elevation grid {dem_s.shape}, {conn.mean():.1%} floodable, "
          f"peak level {peak:.2f} m")

else:
    # The depth field as published, one grid per frame. No terrain arithmetic
    # happens here at all, which is the whole point of a C-Flood event.
    if name == "mahanadi":
        fr = np.load(f"out/{name}_frames.npy", allow_pickle=True)
        frames = [(f"{r[0]}T{int(r[1]):02d}:00", r[2]) for r in fr]
    else:
        frames = [(ev.sar_flood, f"out/depth/{name}_{ev.sar_flood}.tif")]

    grids, shape = [], None
    for label, path in frames:
        d = window_read(path)
        d = np.where(np.isfinite(d), d, 0.0)
        if shape is None:
            shape = d.shape
        elif d.shape != shape:
            sys.exit(f"frame {label} is {d.shape}, the first was {shape}: the "
                     f"frames are not on one grid, so they cannot be animated")
        grids.append(np.clip(d / DSCALE, 0, 254).astype("uint8"))

    stack = np.stack(grids)
    grid = dict(kind="depth", w=int(shape[1]), h=int(shape[0]),
                base=0.0, scale=DSCALE,
                frames=[base64.b64encode(g.tobytes()).decode() for g in grids])
    times = [label for label, _ in frames]
    levels = None
    peak_depth = stack.max(axis=0).astype("float32") * DSCALE
    print(f"  depth grid {shape}, {len(frames)} frame(s), "
          f"peak {peak_depth.max():.2f} m, {(peak_depth > 0.05).mean():.1%} wet")


def depth_at(lon, lat, arr=None):
    """Peak depth at a point, from the grid, for filtering only."""
    a = peak_depth if arr is None else arr
    w, s, e, n = ev.aoi
    c = int((lon - w) / (e - w) * a.shape[1])
    r = int((n - lat) / (n - s) * a.shape[0])
    if 0 <= r < a.shape[0] and 0 <= c < a.shape[1]:
        return float(a[r, c])
    return 0.0


# ------------------------------------------------------------------- roads
# Rank, then trim. Delhi's graph has 222,000 edges and every tertiary lane in
# the city qualifies as "major", which is 37,000 polylines the canvas has to
# redraw on every slider tick. A road that floods is never dropped, whatever its
# class: those are the ones the officer is looking for.
RANK = {"motorway": 0, "trunk": 0, "motorway_link": 0, "trunk_link": 0,
        "primary": 1, "primary_link": 1, "secondary": 2, "secondary_link": 2,
        "tertiary": 3, "tertiary_link": 3}
tiers = {}
for u, v, d in G.edges(data=True):
    if MODE == "level":
        floods = np.isfinite(d["bed"]) and (float(max(levels)) - d["bed"]) >= 0.30
        bed = round(float(d["bed"]), 2) if np.isfinite(d["bed"]) else None
    else:
        mid = d["geom"][len(d["geom"]) // 2]
        floods = depth_at(mid[0], mid[1]) >= 0.30
        # A published depth field already knows how deep this road is. Carrying
        # a bed elevation next to it would invite the page to subtract one from
        # the other, which is exactly the arithmetic that does not apply here.
        bed = None
    if not (floods or d["hw"] in KEEP):
        continue
    tier = -1 if floods else RANK.get(d["hw"], 4)
    tiers.setdefault(tier, []).append(
        [d["geom"], bed, 1 if d.get("structure") == "bridge" else 0, d["name"][:30]])

edges, dropped = [], []
for tier in sorted(tiers):
    if tier >= 0 and len(edges) + len(tiers[tier]) > EDGE_BUDGET:
        dropped.append(tier)
        continue
    edges += tiers[tier]
CLASS = {-1: "flooded", 0: "motorway/trunk", 1: "primary", 2: "secondary",
         3: "tertiary", 4: "other"}
print(f"  edges kept: {len(edges):,}"
      + (f"  (dropped whole classes: "
         f"{', '.join(CLASS[t] for t in dropped)}, over the {EDGE_BUDGET:,} budget)"
         if dropped else ""))

# ------------------------------------------------------------ pickup points
dl, DL_UNIT, DL_HOURS = timeline.read_deadlines(f"out/{name}_deadlines.json")
xy = {}
for u, v, d in G.edges(data=True):
    xy.setdefault(u, (d["lon"], d["lat"]))
    xy.setdefault(v, (d["lon"], d["lat"]))
people = [[round(xy[int(k)][0], 5), round(xy[int(k)][1], 5), v["people"],
           1 if v["bridge_dependent"] else 0,
           None if v["car_cutoff"] == float("-inf") else round(v["car_cutoff"], 2),
           None if v.get("ground") is None else round(v["ground"], 2)]
          for k, v in dl.items() if int(k) in xy]
print(f"  pickup points: {len(people):,}  people {sum(p[2] for p in people):,}")

# ---------------------------------------------------------------- shelters
# The same shelters the router routes to and the allocator fills, read from the
# measured file. The map used to carry its own guessed capacity table, so a
# judge clicking a school saw 500 places while the plan behind it had 288.
import csv as _csv
peak_path = (f"out/depth/{name}_{ev.sar_flood}.tif" if MODE == "level"
             else max(frames, key=lambda f: os.path.getsize(f[1]))[1])
with rasterio.open(peak_path) as s:
    dep, inv, shp = s.read(1), ~s.transform, s.shape
shelters = []
with open(f"data/{name}_shelters_measured.csv", encoding="utf-8") as _f:
    for _r in _csv.DictReader(_f):
        lon, lat = float(_r["lon"]), float(_r["lat"])
        c, r = inv * (lon, lat)
        r, c = int(r), int(c)
        wet = 0 <= r < shp[0] and 0 <= c < shp[1] and dep[r, c] > config.WET_M
        shelters.append([round(lon, 5), round(lat, 5), int(_r["cap"]),
                         1 if wet else 0, (_r["name"] or _r["kind"])[:34]])
print(f"  shelters: {len(shelters)} "
      f"({sum(1 for s_ in shelters if s_[3])} under water)")

# ------------------------------------------------------------------ output
out = dict(aoi=ev.aoi, mode=MODE, hazard=ev.hazard, grid=grid, edges=edges,
           people=people, shelters=shelters, hours=times, levels=levels,
           cutoff_unit=DL_UNIT,
           modes=[[m[0] if m[0] != float("inf") else 999, m[1]]
                  for m in config.MODES])
if MODE == "level":
    out["days"] = [[r[0], float(r[1]), float(r[2]), float(r[3])] for r in rows]

path = f"out/{name}_map_data.json"
json.dump(out, open(path, "w"), separators=(",", ":"))
print(f"  wrote {path}  {os.path.getsize(path) / 1e6:.2f} MB")
