"""Pack the CWC national snapshot into the page's data file."""
import datetime as dt, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import cwc

since = (dt.datetime.now() - dt.timedelta(days=2)).strftime("%Y-%m-%dT00:00:00.000")
snap = cwc.snapshot(since)

rows = []
for s in snap.values():
    if s["lat"] is None or s["lon"] is None:
        continue
    o, d, w = s["observed"], s["danger"], s["warning"]
    st = None
    if o is not None and d is not None:
        st = 2 if o >= d else (1 if w and o >= w else 0)
    rows.append(dict(
        n=s["name"] or s["code"], c=s["code"], k=s["kind"],
        la=round(s["lat"], 4), lo=round(s["lon"], 4),
        o=o, d=d, w=w, h=s["hfl"], st=st,
        t=(s["observed_at"] or "")[:16],
        f=[[a[:10], b, c] for a, b, c in s.get("forecast", [])][:6]))

# SACHET: NDMA's live alert feed, the channel our CAP output is written for
from pravaah import sachet, cflood
try:
    al = sachet.alerts()
    wa = sachet.water_alerts(al)
    alerts = []
    for x in wa:
        c = sachet.centroid(x)
        alerts.append(dict(sev=x.get("severity"), kind=x.get("disaster_type"),
                           area=str(x.get("area_description") or "")[:90],
                           msg=str(x.get("warning_message") or "")[:300],
                           la=c[0] if c else None, lo=c[1] if c else None,
                           start=str(x.get("effective_start_time") or "")[:24]))
    print(f"  SACHET: {len(al)} alerts, {len(wa)} water related, "
          f"{sum(1 for a_ in alerts if a_['la'] is not None)} with a centroid")
except Exception as e:
    alerts = []; print("  SACHET unavailable:", e)

# C-Flood: is an operational inundation run available, and for what
try:
    d_, ws, fr = cflood.latest()
    cf = dict(date=str(d_), workspace=ws, frames=sorted(fr),
              basin="Mahanadi (Upper, Mid, Delta)")
    print(f"  C-Flood: run {d_}, frames {sorted(fr)} h ahead")
except Exception as e:
    cf = None; print("  C-Flood unavailable:", e)

out = dict(rows=rows, alerts=alerts, cflood=cf,
           built=dt.datetime.now().strftime("%d %b %Y %H:%M"),
           source="Central Water Commission, ffs.india-water.gov.in")
json.dump(out, open("out/national_data.json", "w"), separators=(",", ":"))
n = len(rows)
ab = sum(1 for r in rows if r["st"] == 2)
wa = sum(1 for r in rows if r["st"] == 1)
print(f"out/national_data.json  {os.path.getsize('out/national_data.json')/1e3:.0f} kB")
print(f"  {n} stations | {ab} above danger | {wa} above warning | "
      f"{sum(1 for r in rows if r['f'])} with forecasts")
