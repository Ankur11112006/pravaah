"""The full plan for one event: who is wet, when their route dies, where they go."""
import os, sys, json, pickle, numpy as np, rasterio, datetime as dt
from scipy.spatial import cKDTree
from rasterio.warp import reproject, Resampling
sys.path.insert(0, ".")
from pravaah import config, timeline, hazard

ev = config.EVENTS[sys.argv[1] if len(sys.argv) > 1 else "patna"]
# argv[2], when given, is always a depth RASTER PATH, for every hazard mode.
# It used to be a date for a stage event and a path for the others, so passing
# the path uniformly from run.py silently made the date "out/depth/....tif".
ARG = sys.argv[2] if len(sys.argv) > 2 else None
PEAK = ev.sar_flood
if ARG:
    import re as _re
    _m = _re.search(r"_(\d{4}-\d{2}-\d{2})", os.path.basename(ARG))
    if _m:
        PEAK = _m.group(1)

# Three hazard modes, two ways of asking "when does this road close".
#   stage    a fitted water level over time  -> compare against each road's bed
#   cflood   published depth frames          -> the frame a road first goes under
#   observed one depth snapshot, no time     -> the same, with a single frame
# The last one is not a special case, it is the frame path with len(frames)==1:
# route EXISTENCE at the observed depth is knowable even when a deadline is not.
BY_FRAME = ev.hazard in ("cflood", "observed")

G = pickle.load(open(f"data/{ev.name}_graph.pkl", "rb"))
if ev.hazard == "cflood":
    FRAMES = np.load(f"out/{ev.name}_frames.npy", allow_pickle=True)
    DEPTH_PATH = ARG or str(max(FRAMES, key=lambda r: float(r[3]))[2])
    hrs, lv = None, None
elif ev.hazard == "observed":
    DEPTH_PATH = ARG or f"out/depth/{ev.name}_{PEAK}.tif"
    FRAMES = np.array([[PEAK, 0, DEPTH_PATH, 0.0]], dtype=object)
    hrs, lv = None, None
else:
    stage_file = f"out/{ev.name}_stage.npy"
    rows = np.load(stage_file, allow_pickle=True)
    hrs, lv = timeline.hourly_levels(rows)
    DEPTH_PATH = ARG or f"out/depth/{ev.name}_{PEAK}.tif"

# A stage file can outlive the decision to stop fitting a stage. Delhi's was
# written before check_fit rejected its calibration, and it sat on disk for days
# holding a water level of 203.53 m that the project had already refused to
# believe. Planning on it would have produced a confident wrong answer of exactly
# the kind the rest of this system stops.
if BY_FRAME and os.path.exists(f"out/{ev.name}_stage.npy"):
    print(f"  note: out/{ev.name}_stage.npy exists but {ev.name} is a "
          f"'{ev.hazard}' event, so it is IGNORED, not read.")

with rasterio.open(DEPTH_PATH) as s:
    dep, tr, inv, shape = s.read(1), s.transform, ~s.transform, s.shape
pop = np.zeros(shape, "float32")
pop = hazard.population(pop.shape, tr, "EPSG:4326", ev.aoi)

xy = {}
for u, v, d in G.edges(data=True):
    xy.setdefault(u,(d["lon"],d["lat"])); xy.setdefault(v,(d["lon"],d["lat"]))
nid = list(xy); tree = cKDTree(np.array([xy[n] for n in nid]))

with rasterio.open(f"out/{ev.name}_permanent.tif") as _p: channel = _p.read(1).astype(bool)
wet = (dep > config.WET_M) & ~channel   # one threshold, from config, like every other stage
rr, cc = np.nonzero(wet & (pop > 0))
xs, ys = tr * (cc+.5, rr+.5)
_, k = tree.query(np.c_[xs, ys])
# people are aggregated to the nearest road node, but their GROUND elevation must
# stay their own. A road is usually the higher ground; using it would report the
# population as dry while their houses are under water.
with rasterio.open(ev.dem) as _d:
    _inv = ~_d.transform; _e = _d.read(1); _H, _W = _d.shape
def _gnd(x, y):
    c, r = _inv * (x, y); r, c = int(r), int(c)
    if 0 <= r < _H and 0 <= c < _W and np.isfinite(_e[r, c]) and _e[r, c] > 0:
        return float(_e[r, c])
    return None
demand, elev_w = {}, {}
for i, p, x, y in zip(k, pop[rr, cc], xs, ys):
    n = nid[i]; demand[n] = demand.get(n, 0) + float(p)
    g = _gnd(x, y)
    if g is not None:
        a, b = elev_w.get(n, (0.0, 0.0)); elev_w[n] = (a + g*float(p), b + float(p))
ground = {n: (a/b if b > 0 else None) for n, (a, b) in elev_w.items()}
demand = {n:int(round(p)) for n,p in demand.items() if p >= 1}

# Destinations are the shelters whose roof area was measured, which is the same
# list the allocator fills. Reading the raw OSM layer here and scoring it against
# a guessed capacity table meant the router and the allocator disagreed about
# which buildings exist: in the Mahanadi delta OSM knows two, and the measured
# list knows twenty-seven because OSDMA publishes the rest.
import csv as _csv
shelters = {}
with open(f"data/{ev.name}_shelters_measured.csv", encoding="utf-8") as _f:
    for _r in _csv.DictReader(_f):
        lon, lat = float(_r["lon"]), float(_r["lat"])
        c, r = inv * (lon, lat); r, c = int(r), int(c)
        if 0 <= r < shape[0] and 0 <= c < shape[1] and dep[r, c] > config.WET_M:
            continue                       # a shelter standing in water is not one
        n = nid[tree.query([lon, lat])[1]]
        shelters[n] = dict(name=_r["name"] or f'{_r["kind"]} at {lat:.4f}N {lon:.4f}E',
                           cap=int(_r["cap"]))
print(f"{ev.name} @ {PEAK}: {sum(demand.values()):,} people at {len(demand)} points, "
      f"{len(shelters)} shelters above water")
if BY_FRAME:
    # Sample every road at every published frame once, then ask each mode when
    # its own depth limit is first crossed. Larger index means "lasts longer",
    # which is exactly what the max-bottleneck search wants, so the same
    # verified routine serves both hazard modes.
    _pts = np.array([[d["lon"], d["lat"]] for _, _, d in G.edges(data=True)])
    _dser = np.zeros((len(FRAMES), len(_pts)), "float32")
    for _fi, _row in enumerate(FRAMES):
        with rasterio.open(str(_row[2])) as _fs:
            _finv, _fa = ~_fs.transform, _fs.read(1)
            _c, _r = _finv * (_pts[:, 0], _pts[:, 1])
            _r, _c = np.floor(_r).astype(int), np.floor(_c).astype(int)
            _ok = ((_r >= 0) & (_r < _fs.height) & (_c >= 0) & (_c < _fs.width))
            _dser[_fi, _ok] = _fa[_r[_ok], _c[_ok]]
    # One past the last frame index, so "never closes" sorts above every frame
    # that exists. Setting it equal to the last index instead made a road that
    # survives indistinguishable from one closing in the final frame, and every
    # mode then reported the same population.
    NEVER = float(len(FRAMES))
    for _lim, _mode in config.MODES:
        if _mode == "boat":
            continue
        _bad = _dser >= _lim
        _die = np.where(_bad.any(0), _bad.argmax(0).astype("float64"), NEVER)
        for _ei, (_u, _v, _d) in enumerate(G.edges(data=True)):
            _d[f"die_{_mode}"] = float(_die[_ei])
    HOURS = [int(r[1]) for r in FRAMES]
    if ev.hazard == "observed":
        print(f"one observed depth snapshot, {DEPTH_PATH.split('/')[-1]}. Route")
        print("  EXISTENCE is computable from it; a closing TIME is not, and none")
        print("  is reported below.")
    else:
        print(f"{len(FRAMES)} C-Flood frames, +{HOURS[0]} to +{HOURS[-1]} hours, "
              f"planning on {DEPTH_PATH.split('/')[-1]}")
        print(f"  a road is closed to a mode at the first frame its depth reaches "
              f"that mode's limit\n")
else:
    _now = lv[[i_ for i_, h_ in enumerate(hrs)
               if h_.date() == dt.date.fromisoformat(PEAK)][0]]
    print(f"water level now {_now:.2f} m, peak in window {lv.max():.2f} m\n")

# One cut-off per mode. In stage mode the number is a water LEVEL in metres; in
# C-Flood mode it is the FRAME at which the route dies. Both mean "the last point
# at which this pickup point can still reach a shelter", both come out of the
# same max-bottleneck routine, and the unit is written into the output so nothing
# downstream has to guess which one it is holding.
UNIT = "frame" if BY_FRAME else "metres"
# the last point that actually exists: the final frame INDEX, or the peak level
LAST = float(len(FRAMES) - 1) if BY_FRAME else float(lv.max())


def cut_for(lim, mode, use_bridges=True):
    if BY_FRAME:
        return timeline.cutoff_levels(G, list(demand), list(shelters), 0.0,
                                      use_bridges=use_bridges, key=f"die_{mode}")
    return timeline.cutoff_levels(G, list(demand), list(shelters), lim,
                                  use_bridges=use_bridges)


# "Dies in the window" was hiding two different situations behind one number.
# A route that closes on Thursday afternoon is a DEADLINE an officer can work to.
# A route that was already impassable when the window opened is not a deadline,
# it is a fact, and the two need separate columns or the plan reads as though
# there is time that does not exist.
FIRST = 0.0 if BY_FRAME else float(lv[0])

print("ROUTE SURVIVAL, by mode")
print(f"  {'mode':<7}{'survives':>11}{'closes in window':>18}"
      f"{'already gone':>14}{'no route ever':>15}")
res = {}
for lim, mode in config.MODES:
    if mode == "boat":
        continue
    cut = cut_for(lim, mode)
    res[mode] = cut
    never = sum(demand[n] for n, c in cut.items() if c == float("-inf"))
    gone = sum(demand[n] for n, c in cut.items()
               if float("-inf") < c < FIRST)
    closes = sum(demand[n] for n, c in cut.items() if FIRST <= c <= LAST)
    lives = sum(demand[n] for n, c in cut.items() if c > LAST)
    print(f"  {mode:<7}{lives:>11,}{closes:>18,}{gone:>14,}{never:>15,}")
    assert never + gone + closes + lives == sum(demand.values()),         f"{mode}: the four columns do not add up to everyone"

print()
_span = ("the one observed snapshot" if ev.hazard == "observed" else
         "the published frames" if BY_FRAME else
         f"the modelled window, {FIRST:.2f} to {LAST:.2f} m")
if all(c > LAST for c in res["car"].values() if c > float("-inf")):
    print(f"No pickup point loses its car route inside {_span}.")
else:
    print(f"Some car routes close inside {_span}; the table below gives the ones")
    print("nearest the threshold, which are the ones a decision actually turns on.")

nb = cut_for(config.MODES[0][0], "car", use_bridges=False)
onbr = sum(demand[n] for n in demand
           if res["car"][n] > float("-inf") and nb[n] == float("-inf"))
tot = sum(demand[n] for n, c in res["car"].items() if c > float("-inf"))
print()
print(f"BRIDGE DEPENDENCY: {onbr:,} of {tot:,} people with a car route reach their")
print(f"  shelter ONLY across a bridge. Terrain cannot tell us whether those bridges")
print(f"  are open, so this is the number an officer has to resolve by sending someone.")

print()
# Nearest the threshold, in either direction. Sorting by the raw margin put the
# worst-off points at the top under a heading that said "closest to losing",
# which is the opposite of what it claimed to show.
print("NEAREST THE THRESHOLD (the points a decision actually turns on):")
edge = sorted(((abs(c - LAST), c, n) for n, c in res["car"].items()
               if c > float("-inf")))
if not edge:
    print("  no pickup point has a car route at all.")
for _, c, n in edge[:8]:
    if BY_FRAME:
        if ev.hazard == "observed":
            # one snapshot: a route is open or it is not, and there is no "when"
            print(f"  {demand[n]:>6,} people   "
                  f"{'open at the observed depth' if c > LAST else 'CUT OFF':<28}"
                  f"(no time dimension for this event)")
        else:
            when = (f"closes at +{HOURS[int(c)]:>2} h" if c <= LAST
                    else "open through the whole run")
            print(f"  {demand[n]:>6,} people   {when:<28}"
                  f"frame {min(int(c), len(FRAMES)):>1} of {len(FRAMES)}")
    else:
        print(f"  {demand[n]:>6,} people   cut-off {c:6.2f} m   "
              f"margin {c - LAST:+5.2f} m   "
              f"{'SURVIVES' if c > LAST else 'CUT OFF'}")

stranded = [(n, demand[n]) for n, c in res["car"].items() if c == float("-inf")]
print()
print(f"NO ROUTE AT ALL: {sum(p for _, p in stranded):,} people at {len(stranded)} points.")
print(f"  Not a routing failure to hide. These need boats or air, and the plan says so.")

# The per-mode split, computed here where the per-mode cut-offs already exist.
# Only car_cutoff is stored per point, so without this the API could serve one
# mode and the screen would have to invent the other two.
survival = {}
for _lim, _mode in config.MODES:
    if _mode == "boat":
        continue
    _c = res[_mode]
    survival[_mode] = dict(
        survives=sum(demand[k] for k, v in _c.items() if v > LAST),
        closes=sum(demand[k] for k, v in _c.items() if FIRST <= v <= LAST),
        gone=sum(demand[k] for k, v in _c.items()
                 if float("-inf") < v < FIRST),
        never=sum(demand[k] for k, v in _c.items() if v == float("-inf")))
    assert sum(survival[_mode].values()) == sum(demand.values()),         f"{_mode}: the four columns do not add up to everyone"

json.dump(dict(unit=UNIT, first=FIRST, last=LAST, survival=survival,
               hours=(HOURS if BY_FRAME else None),
               points={str(n): dict(people=demand[n], car_cutoff=res["car"][n],
                                    ground=ground.get(n),
                                    bridge_dependent=bool(
                                        res["car"][n] > float("-inf")
                                        and nb[n] == float("-inf")))
                       for n in demand}),
          open(f"out/{ev.name}_deadlines.json", "w"), indent=1)
print()
print(f"wrote out/{ev.name}_deadlines.json  (car_cutoff is in {UNIT})")
