"""Step 6: when to act, and what to say.

Trigger rule from decision theory: act when P(event) > cost of acting / loss avoided.
The officer supplies the costs. The threshold falls out. Nobody guesses a number."""
import json, os, pickle, sys, datetime as dt, xml.etree.ElementTree as ET
sys.path.insert(0, ".")
from pravaah import config as _cfg
sys.stdout.reconfigure(encoding="utf-8")
EV = sys.argv[1] if len(sys.argv) > 1 else "patna"
import pandas as pd, numpy as np

# The probability is COMPUTED, not typed: the share of GloFAS's 50-member
# ensemble that exceeds a published return period at the main-stem gauge. Falls
# back to an explicit override only if the live services are unreachable, and
# says which of the two it used.
P_FALLBACK, PLANNING_RP = 0.42, 5

def _live_probability(ev):
    from pravaah import hazard
    g = hazard.main_stem_gauge(*ev.gauge)
    thr = g["rp"][str(PLANNING_RP)]
    _, ens = hazard.ensemble(g["lat"], g["lon"], days=14)
    per_day = (ens >= thr).mean(axis=1)
    i = int(per_day.argmax())
    return float(per_day[i]), thr, int(ens.shape[1]), g["gauge_id"]

try:
    P_EVENT, _THR, _N, _GID = _live_probability(_cfg.EVENTS[EV])
    P_SRC = (f"{P_EVENT*100:.0f}% = share of {_N} GloFAS ensemble members above the "
             f"{PLANNING_RP}-year return period {_THR:,.0f} m3/s at {_GID}")
except Exception as _e:
    P_EVENT, P_SRC = P_FALLBACK, f"fallback constant, live services unreachable ({_e})"
SENDER  = "pravaah@ddma.example.in"

# action -> (cost of doing it, loss avoided if the flood happens). Officer's numbers.
ACTIONS = [
    ("Check and open shelters",        2,   100),
    ("Pre-position boats and crews",  12,   100),
    ("Move livestock to high ground", 20,   100),
    ("Full evacuation of the ward",   55,   100),
]

print(f"forecast probability for this ward: {P_EVENT:.0%}")
print(f"  {P_SRC}")
print()
print(f"  {'action':<32}{'cost':>6}{'loss':>7}{'triggers above':>16}{'now?':>7}")
print("  " + "-"*68)
fire = []
for name, c, l in ACTIONS:
    thr = c/l
    go = P_EVENT > thr
    if go: fire.append(name)
    print(f"  {name:<32}{c:>6}{l:>7}{thr:>15.0%}{'  YES' if go else '   no':>7}")
print()
print(f"  -> at {P_EVENT:.0%} the arithmetic authorises: "
      f"{', '.join(fire) if fire else 'nothing yet'}")
_evac, _c, _l = ACTIONS[-1]
_thr = _c / _l
if P_EVENT > _thr:
    print(f"     that INCLUDES {_evac.lower()}: the threshold is {_thr:.0%} "
          f"and the forecast is {P_EVENT:.0%}.")
    print("     an officer still has to approve it, and the override is "
          "logged with a reason.")
else:
    print(f"     evacuation is NOT authorised: it needs the probability above "
          f"{_thr:.0%}, and it is {P_EVENT:.0%}.")

# ---------- the actual messages ----------
ex = pd.read_csv(f"out/{EV}_exposure.csv").sort_values("people", ascending=False)
pshel = json.load(open(f"out/{EV}_place_shelter.json"))
places = {p["tags"].get("name"): (p["lat"], p["lon"])
          for p in json.load(open(f"data/{EV}_osm_places.json", encoding="utf-8"))["elements"]}
G = pickle.load(open(f"data/{EV}_graph.pkl", "rb"))
import numpy as _np
sys.path.insert(0, ".")
from pravaah import config as _cfg, timeline as _tl
# The graph stores ground elevation, not a mode, so the mode is derived at the
# level we are alerting for. That is the whole point of keeping terrain instead
# of a frozen snapshot: the same graph answers for any hour.
_ev = _cfg.EVENTS[EV]
if _ev.hazard == "stage":
    _rows = _np.load(f"out/{EV}_stage.npy", allow_pickle=True)
    _hrs, _lv = _tl.hourly_levels(_rows)
    LEVEL = float(_lv.max())
    cutnames = sorted({d["name"] for _, _, d in G.edges(data=True)
                       if d["name"] and d.get("structure") != "bridge"
                       and _np.isfinite(d["bed"])
                       and _tl._cls(LEVEL - d["bed"], _cfg.MODES) != "car"})
else:
    # no level series; read the depth the roads are actually standing in
    import rasterio as _rio
    _depth_path = (sys.argv[2] if len(sys.argv) > 2
                   else f"out/depth/{EV}_{_ev.sar_flood}.tif")
    if not os.path.exists(_depth_path):
        raise SystemExit(
            f"no depth raster at {_depth_path}. This event has no single "
            f"named SAR date, so pass the frame to plan on: "
            f"alert.py {EV} out/depth/{EV}_<date>_<hour>.tif")
    with _rio.open(_depth_path) as _s:
        _dep, _inv, _H, _W = _s.read(1), ~_s.transform, _s.height, _s.width
    def _d_at(lon, lat):
        c, r = _inv * (lon, lat); r, c = int(r), int(c)
        return float(_dep[r, c]) if 0 <= r < _H and 0 <= c < _W else 0.0
    cutnames = sorted({d["name"] for _, _, d in G.edges(data=True)
                       if d["name"] and d.get("structure") != "bridge"
                       and _tl._cls(_d_at(d["lon"], d["lat"]), _cfg.MODES) != "car"})

now = dt.datetime(2019, 9, 29, 18, 0)     # T-1 for the 30 Sep peak
NS = "urn:oasis:names:tc:emergency:cap:1.2"
ET.register_namespace("", NS)
root = ET.Element(f"{{{NS}}}alert")
def sub(par, tag, txt):
    e = ET.SubElement(par, f"{{{NS}}}{tag}"); e.text = str(txt); return e
sub(root, "identifier", f"PRAVAAH-PATNA-{now:%Y%m%dT%H%M}")
sub(root, "sender", SENDER)
sub(root, "sent", now.strftime("%Y-%m-%dT%H:%M:%S+05:30"))
for t, v in [("status","Actual"),("msgType","Alert"),("scope","Public")]: sub(root, t, v)

sms_out = []
def shelter_for(place):
    v = pshel.get(place)
    return v["shelter"] if v else "the nearest shelter"

for _, r in ex.head(4).iterrows():
    to = shelter_for(r["place"])
    info = ET.SubElement(root, f"{{{NS}}}info")
    for t, v in [("language","en-IN"),("category","Met"),("event","Flood"),
                 ("responseType","Prepare"),("urgency","Expected"),
                 ("severity","Severe" if r.max_depth > 1 else "Moderate"),
                 ("certainty","Likely")]:
        sub(info, t, v)
    sub(info, "headline", f"{r['place']}: flooding expected, move to a shelter before 20:00")
    sub(info, "description",
        f"About {int(r.people):,} people and {int(r.buildings)} buildings in {r['place']} "
        f"are in the area expected to take water. Typical depth {r.med_depth:.1f} m, "
        f"up to {r.max_depth:.1f} m in the lowest parts.")
    sub(info, "instruction",
        f"Move to {to} before 20:00 today. "
        + (f"{cutnames[0]} may stop taking cars after 22:00. " if cutnames else "")
        + "If you cannot leave, move to an upper floor and call 1070.")
    area = ET.SubElement(info, f"{{{NS}}}area")
    sub(area, "areaDesc", r["place"])
    if r["place"] in places:
        la, lo = places[r["place"]]; sub(area, "circle", f"{la:.4f},{lo:.4f} 3")
    # one GSM-7 SMS is 160 characters; a cell broadcast that splits can arrive
    # out of order, so the first message must stand alone.
    sms = (f"{r['place'].upper()}: Flood water expected. Go to {to} before 8pm. "
           f"Cannot walk? Reply 1. -DDMA")
    if len(sms) > 160:
        sms = f"{r['place'].upper()}: Flood expected. Shelter: {to}. Before 8pm. Reply 1 if stuck."[:160]
    sms_out.append(sms)

ET.ElementTree(root).write(f"out/{EV}_cap12.xml", encoding="utf-8", xml_declaration=True)
assert ET.parse(f"out/{EV}_cap12.xml"), "CAP XML does not parse"
n_info = len(root.findall(f"{{{NS}}}info"))
print(f"\nwrote out/{EV}_cap12.xml  ({n_info} info blocks, parses as valid XML)")

open(f"out/{EV}_sms.txt","w",encoding="utf-8").write("\n\n".join(sms_out))
print(f"wrote out/{EV}_sms.txt\n")
for s in sms_out[:2]:
    print(f"  [{len(s)} chars] {s}")
