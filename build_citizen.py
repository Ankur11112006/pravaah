"""Pack the citizen view's data: one card per reporting unit.

Everything a person in that unit needs and nothing they do not: how deep the
water gets where they are, which shelter the plan assigned them, how far it is,
which roads stop carrying what, and the plain-language instruction. Also, and
this is the part that matters, whether the plan can actually reach them.
"""
import datetime as dt, json, math, os, pickle, sys
import numpy as np, pandas as pd, rasterio
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import config, timeline

EV = sys.argv[1] if len(sys.argv) > 1 else "patna"
ev = config.EVENTS[EV]
PEAK = sys.argv[2] if len(sys.argv) > 2 else ev.sar_flood

ex = pd.read_csv(f"out/{EV}_exposure.csv")
assign = json.load(open(f"out/{EV}_place_shelter.json"))
from pravaah import timeline as _tl_r
deadl, DEADL_UNIT, DEADL_HOURS = _tl_r.read_deadlines(f"out/{EV}_deadlines.json")
places = {p["tags"].get("name"): (p["lat"], p["lon"])
          for p in json.load(open(f"data/{EV}_osm_places.json", encoding="utf-8"))["elements"]
          if p.get("tags", {}).get("name")}
shelters = pd.read_csv(f"data/{EV}_shelters_measured.csv")
G = pickle.load(open(f"data/{EV}_graph.pkl", "rb"))

# roads that stop carrying cars, with the hour they change, per the stage series
roads = []
if ev.hazard == "stage" and os.path.exists(f"out/{EV}_stage.npy"):
    rows = np.load(f"out/{EV}_stage.npy", allow_pickle=True)
    hrs, lv = timeline.hourly_levels(rows)
    for _, _, d in G.edges(data=True):
        if not d.get("name") or d.get("structure") == "bridge":
            continue
        t = timeline.edge_timeline(d["bed"], hrs, lv, config.MODES, config.ORDER,
                                   d.get("structure", ""))
        if not t or t["worst"] == "car" or not t["events"]:
            continue
        when, frm, to, dirn = t["events"][0]
        roads.append(dict(name=d["name"][:44], lat=d["lat"], lon=d["lon"],
                          worst=t["worst"], depth=round(t["max_depth"], 2),
                          when=when.strftime("%a %d %b %H:%M"), frm=frm, to=to))
seen, uniq = set(), []
for r in sorted(roads, key=lambda r: -r["depth"]):
    if r["name"] in seen:
        continue
    seen.add(r["name"]); uniq.append(r)
roads = uniq[:40]

# per pickup point, is the plan able to reach them at all
by_place = {}
xy = {}
for u, v, d in G.edges(data=True):
    xy.setdefault(u, (d["lon"], d["lat"])); xy.setdefault(v, (d["lon"], d["lat"]))
for k, v in deadl.items():
    n = int(k)
    if n not in xy:
        continue
    lo, la = xy[n]
    best, bd = None, 1e9
    for nm, (pla, plo) in places.items():
        dd = math.hypot(pla - la, plo - lo)
        if dd < bd:
            bd, best = dd, nm
    if best is None:
        continue
    b = by_place.setdefault(best, dict(people=0, stranded=0, bridge=0))
    b["people"] += v["people"]
    if v["car_cutoff"] == float("-inf"):
        b["stranded"] += v["people"]
    elif v["bridge_dependent"]:
        b["bridge"] += v["people"]

units = []
for _, r in ex.sort_values("people", ascending=False).iterrows():
    nm = r["place"]
    a = assign.get(nm, {})
    sh = a.get("shelter", "")
    srow = shelters[shelters.name.fillna("") == sh]
    slat = float(srow.lat.iloc[0]) if len(srow) else None
    slon = float(srow.lon.iloc[0]) if len(srow) else None
    pla, plo = places.get(nm, (None, None))
    km = (round(math.hypot((slat - pla) * 111, (slon - plo) * 111 *
                           math.cos(math.radians(pla))), 1)
          if None not in (slat, slon, pla, plo) else None)
    b = by_place.get(nm, {})
    units.append(dict(
        place=nm, people=int(r.people), buildings=int(r.buildings),
        km2=round(r.km2, 1), med=round(r.med_depth, 2), mx=round(r.max_depth, 2),
        lat=pla, lon=plo, shelter=sh, slat=slat, slon=slon, km=km,
        stranded=int(b.get("stranded", 0)), bridge=int(b.get("bridge", 0))))

out = dict(event=EV, peak=PEAK, units=units, roads=roads,
           built=dt.datetime.now().strftime("%d %b %Y %H:%M"),
           modes=[[m[0] if m[0] != float("inf") else 999, m[1]] for m in config.MODES])
json.dump(out, open(f"out/{EV}_citizen_data.json", "w"), separators=(",", ":"))
print(f"out/{EV}_citizen_data.json  "
      f"{os.path.getsize(f'out/{EV}_citizen_data.json')/1e3:.0f} kB")
print(f"  {len(units)} units, {len(roads)} named roads that change mode, "
      f"{sum(u['stranded'] for u in units):,} people the plan cannot reach")
