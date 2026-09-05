"""India's live flood picture, from CWC's own forecast network.

    python national.py

Not one city. Every gauged forecast station CWC operates, with its official
danger level, what the water is doing right now, and what CWC has forecast.
"""
import datetime as dt, json, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import cwc

since = (dt.datetime.now() - dt.timedelta(days=2)).strftime("%Y-%m-%dT00:00:00.000")
snap = cwc.snapshot(since)
print(f"CWC Flood Forecasting System, pulled {dt.datetime.now():%d %b %Y %H:%M}")
print(f"  {len(snap)} forecast stations")

lvl = [s for s in snap.values() if s["kind"] == "Level"]
inf = [s for s in snap.values() if s["kind"] == "Inflow"]
withobs = [s for s in lvl if s["observed"] is not None and s["danger"]]
withfc = [s for s in snap.values() if s.get("forecast")]
print(f"  {len(lvl)} river level, {len(inf)} reservoir inflow")
print(f"  {len(withobs)} level stations reporting now, {len(withfc)} with a live forecast")


def state(s):
    o, d, w = s["observed"], s["danger"], s.get("warning")
    if o is None or d is None:
        return None
    if o >= d:
        return "ABOVE DANGER"
    if w and o >= w:
        return "above warning"
    return "normal"


buckets = {}
for s in withobs:
    buckets.setdefault(state(s), []).append(s)
print(f"\n  {'status':<16}{'stations':>9}")
for k in ("ABOVE DANGER", "above warning", "normal"):
    print(f"  {k:<16}{len(buckets.get(k, [])):>9}")

for k in ("ABOVE DANGER", "above warning"):
    rows = sorted(buckets.get(k, []), key=lambda s: -(s["observed"] - s["danger"]))
    if not rows:
        continue
    print(f"\n  {k}")
    print(f"    {'station':<24}{'now':>9}{'danger':>9}{'over by':>9}{'HFL':>9}  as of")
    for s in rows[:15]:
        print(f"    {(s['name'] or s['code'])[:22]:<24}{s['observed']:>9.2f}"
              f"{s['danger']:>9.2f}{s['observed']-s['danger']:>+9.2f}"
              f"{(s['hfl'] or 0):>9.2f}  {(s['observed_at'] or '')[:16]}")

# Where is the water heading, per CWC's own issued forecast. Level stations are
# metres and Inflow stations are cumecs, so they are never put in one table: a
# reservoir at 2,400 m3/s against a "danger level" of 220 m is not +2,180 of
# anything.
for kind, unit in (("Level", "m"), ("Inflow", "m3/s")):
    rows = []
    for s_ in withfc:
        if s_["kind"] != kind or s_.get("danger") is None:
            continue
        f = s_["forecast"]
        if not f or f[-1][1] is None:
            continue
        rows.append((f[-1][1] - s_["danger"], s_, f))
    rows.sort(key=lambda x: -x[0])
    if not rows:
        continue
    print()
    print(f"  CWC forecast, {kind} stations, closest to or above threshold ({unit})")
    print(f"    {'station':<24}{'forecast':>11}{'threshold':>11}{'margin':>10}"
          f"{'trend':>9}  for")
    for m, s_, f in rows[:12]:
        d, v, t = f[-1]
        print(f"    {(s_['name'] or s_['code'])[:22]:<24}{v:>11,.2f}"
              f"{s_['danger']:>11,.2f}{m:>+10,.2f}{(t or '')[:8]:>9}  {d[:10]}")

json.dump({c: s for c, s in snap.items()}, open("out/cwc_snapshot.json", "w"), indent=1)
print(f"\n  wrote out/cwc_snapshot.json")
print("  source: ffs.india-water.gov.in, Central Water Commission. No key, no login.")
