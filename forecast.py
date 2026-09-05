"""Turn a 50-member discharge forecast into a probability, and a probability
into an authorised action. This is the last hand-typed number in the system.

  ensemble share above a return period  ->  P(event)
  P(event) vs cost/loss                 ->  which actions are authorised

GloFAS ensemble from Open-Meteo (free, no key). Return periods from Google
Flood Hub, gs://flood-forecasting, CC-BY-4.0.
"""
import sys
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import config, hazard

EV = config.EVENTS[sys.argv[1] if len(sys.argv) > 1 else "patna"]
ACTIONS = [("Check and open shelters", 2, 100),
           ("Pre-position boats and crews", 12, 100),
           ("Move livestock to high ground", 20, 100),
           ("Full evacuation of the ward", 55, 100)]
# Which return period counts as "the flood we are planning for". A 5-year event
# is the one the district actually prepares for; 25-year is the severe case.
PLANNING_RP = "5"

g = hazard.main_stem_gauge(*EV.gauge)
print(f"{EV.name}: main-stem gauge {g['gauge_id']} "
      f"({g['km_away']:.1f} km from the reference point)")
rp = {int(k): v for k, v in g["rp"].items()}
print("  return periods  " + "  ".join(f"{k}y {v:,.0f}" for k, v in
                                       sorted(rp.items())[:6]) + "  m3/s")

days, ens = hazard.ensemble(g["lat"], g["lon"], days=30)
n = ens.shape[1]
print(f"  ensemble: {len(days)} days x {n} members, "
      f"{days[0]} to {days[-1]}\n")

print(f"  {'date':<12}{'median':>9}" +
      "".join(f"{'P>'+str(k)+'y':>9}" for k in (2, 5, 25, 100)))
print("  " + "-" * 57)
rows = []
for i, d in enumerate(days):
    m = ens[i]
    probs = {k: float((m >= rp[k]).mean()) for k in (2, 5, 25, 100)}
    rows.append((d, float(np.median(m)), probs))
    if i % 3 == 0 or probs[5] > 0:
        print(f"  {d:<12}{np.median(m):>9,.0f}" +
              "".join(f"{probs[k]:>9.0%}" for k in (2, 5, 25, 100)))

peak = max(rows, key=lambda r: r[2][int(PLANNING_RP)])
P = peak[2][int(PLANNING_RP)]
print(f"\n  worst day for a 1-in-{PLANNING_RP}-year exceedance: {peak[0]}")
print(f"  P = {P:.0%}  ({int(round(P*n))} of {n} members above "
      f"{rp[int(PLANNING_RP)]:,.0f} m3/s)")

print(f"\n  {'action':<32}{'cost':>6}{'loss':>6}{'triggers above':>16}{'now':>6}")
print("  " + "-" * 66)
fire = []
for name, c, l in ACTIONS:
    thr = c / l
    go = P > thr
    if go:
        fire.append(name)
    print(f"  {name:<32}{c:>6}{l:>6}{thr:>15.0%}{'  YES' if go else '   no':>6}")

print(f"\n  at {P:.0%} the arithmetic authorises: "
      + (", ".join(fire) if fire else "nothing"))
if len(fire) < len(ACTIONS):
    nxt = ACTIONS[len(fire)]
    print(f"  the next step up, {nxt[0].lower()}, needs {nxt[1]/nxt[2]:.0%}")
print("\n  Nobody typed this probability. It is the share of a 50-member forecast")
print("  above a published return period, and both sources are free and open.")
