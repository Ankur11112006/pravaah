"""Pack the officer dashboard's data: map, allocation, alerts, provenance."""
import io, json, os, sys, datetime as dt
import numpy as np, pandas as pd, rasterio
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import config

EV = sys.argv[1] if len(sys.argv) > 1 else "patna"
PEAK = sys.argv[2] if len(sys.argv) > 2 else config.EVENTS[EV].sar_flood

d = json.load(open(f"out/{EV}_map_data.json"))

# ---- exposure by reporting unit ----
ex = pd.read_csv(f"out/{EV}_exposure.csv").sort_values("people", ascending=False)
assign = {a["place"]: a for a in json.load(open(f"out/{EV}_assign.json"))}
d["units"] = [dict(place=r["place"], km2=round(r.km2, 1), people=int(r.people),
                   buildings=int(r.buildings), med=round(r.med_depth, 2),
                   mx=round(r.max_depth, 2),
                   shelter=assign.get(r["place"], {}).get("shelter", ""),
                   assigned=assign.get(r["place"], {}).get("people", 0))
              for _, r in ex.iterrows()]

# ---- shelters, with how full the plan makes them ----
alloc = json.load(open(f"out/{EV}_allocation.json"))
d["alloc"] = [dict(name=k, n=v) for k, v in
              sorted(alloc.items(), key=lambda x: -x[1])]

# ---- the trigger arithmetic, recomputed here so the page can move the slider ----
d["actions"] = [dict(name=n, cost=c, loss=l) for n, c, l in
                [("Check and open shelters", 2, 100),
                 ("Pre-position boats and crews", 12, 100),
                 ("Move livestock to high ground", 20, 100),
                 ("Full evacuation of the ward", 55, 100)]]

# ---- the messages that would actually go out ----
sms = io.open(f"out/{EV}_sms.txt", encoding="utf-8").read().split("\n\n")
d["sms"] = [s for s in sms if s.strip()]
cap = io.open(f"out/{EV}_cap12.xml", encoding="utf-8").read()
d["cap"] = cap[:1800] + ("\n..." if len(cap) > 1800 else "")

# ---- what the plan cannot do, stated on the page rather than buried ----
from pravaah import timeline as _tl_r
dl, DL_UNIT, DL_HOURS = _tl_r.read_deadlines(f"out/{EV}_deadlines.json")
d["gaps"] = dict(
    no_route=sum(v["people"] for v in dl.values() if v["car_cutoff"] == float("-inf")),
    bridge=sum(v["people"] for v in dl.values()
               if v["car_cutoff"] != float("-inf") and v["bridge_dependent"]),
    total=sum(v["people"] for v in dl.values()),
    capacity=sum(v for v in alloc.values()),
)

# ---- provenance: every source, when it was captured, and whether it is assumed ----
ev = config.EVENTS[EV]
d["sources"] = [
    dict(what="River discharge", src="GloFAS via Open-Meteo", when="daily, " + PEAK,
         status="live"),
    dict(what="Flood extent used to calibrate", src="Sentinel-1 RTC",
         when=f"{ev.sar_base} and {ev.sar_flood}", status="observed"),
    dict(what="Terrain", src="Copernicus GLO-30", when="2021 release", status="static"),
    dict(what="Buildings", src="Microsoft Global ML Buildings", when="2023",
         status="static"),
    dict(what="Population", src="GHS-POP 2020, 100 m", when="2020",
         status="modelled, 30-50% local error"),
    dict(what="Roads", src="OpenStreetMap", when="fetched 30 Aug 2026", status="live"),
    dict(what="Shelter capacity", src="measured roof area / 3.5 m2 per person, "
                                      "NDMA Minimum Standards of Relief 2(c)",
         when="OSM campus boundaries, MS footprints", status="measured"),
    dict(what="Live river level and CWC forecast",
         src="CWC Flood Forecasting System, ffs.india-water.gov.in",
         when="354 stations, live", status="open, no login"),
    dict(what="Officer-grade inundation raster", src="C-Flood / NDEM",
         when="viewer is public, raster download not yet wired",
         status="not yet wired"),
]
# Independent ground truth, so the page can be checked against something that
# was not used to build it. Bihar Inter Agency Group / Sphere India, Joint Rapid
# Needs Assessment, Bihar urban floods 2019.
import numpy as _np
with rasterio.open(f"out/depth/{EV}_{PEAK}.tif") as _s: _d = _s.read(1)
with rasterio.open(f"out/{EV}_permanent.tif") as _s: _c = _s.read(1).astype(bool)
_v = _d[(_d > 0) & ~_c]
d["check"] = [
    dict(claim="Typical water depth in flooded Patna slums",
         theirs="3 feet (0.91 m)", ours=f"{_np.median(_v):.2f} m median"),
    dict(claim="Families affected in Patna slums",
         theirs="16,825 families in 40 slums", ours=f"{d['gaps']['total']:,} people modelled"),
    dict(claim="Evacuated across Bihar", theirs="1.25 lakh",
         ours=f"{d['gaps']['capacity']:,} placed in this district"),
    dict(claim="Worst-hit localities named on the ground",
         theirs="Rajendra Nagar, Kankarbagh, Boring Road, Pataliputra Colony",
         ours="NOT in our flood map: these are pluvial, kilometres from the Ganga"),
]
d["check_src"] = ("Bihar Inter Agency Group and Sphere India, Joint Rapid Needs "
                  "Assessment, Bihar urban floods 2019, as of 14 October 2019")

d["meta"] = dict(event=EV, peak=PEAK,
                 built=dt.datetime.now().strftime("%d %b %Y %H:%M"))

json.dump(d, open("out/dash_data.json", "w"), separators=(",", ":"))
print(f"out/dash_data.json  {os.path.getsize('out/dash_data.json')/1e6:.2f} MB")
print(f"  units {len(d['units'])} | shelters used {len(d['alloc'])} | "
      f"sms {len(d['sms'])} | sources {len(d['sources'])}")
print(f"  gaps: {d['gaps']['no_route']:,} no route, {d['gaps']['bridge']:,} "
      f"bridge-dependent, {d['gaps']['capacity']:,} placed of {d['gaps']['total']:,}")
