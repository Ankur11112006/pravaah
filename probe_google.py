"""Google Flood Hub open data: find the main-stem gauge for each event and read
its return periods, so a discharge can be turned into a severity a human
understands ("this is a one-in-25-year flood").

Source: gs://flood-forecasting/hydrologic_predictions, CC-BY-4.0.
"""
import sys
import numpy as np, zarr, fsspec
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import config, hazard

B = ("https://storage.googleapis.com/flood-forecasting/hydrologic_predictions"
     "/model_id_8583a5c2_v0")


def store(p):
    return zarr.open(fsspec.get_mapper(f"{B}/{p}"), mode="r")


loc = store("hybas_outlet_locations_UNOFFICIAL.zarr")
lat = loc["latitude"][:]; lon = loc["longitude"][:]; gid = loc["gauge_id"][:]
rp = store("return_periods.zarr")
rp_gid = rp["gauge_id"][:]
periods = sorted(int(k.split("_")[-1]) for k in rp.array_keys()
                 if k.startswith("return_period_"))
idx = {g: i for i, g in enumerate(rp_gid)}
two = rp["return_period_2"][:]
print(f"{len(gid):,} outlets, {len(rp_gid):,} with return periods, "
      f"periods {periods[0]}-{periods[-1]} years")

for ev in (config.PATNA, config.DELHI):
    glat, glon = ev.gauge
    d = np.hypot(lat - glat, lon - glon) * 111.0
    near = np.nonzero(d < 25)[0]
    print(f"\n{ev.name.upper()}   reference point {glat}, {glon}")
    print(f"  {len(near)} HydroBASINS outlets within 25 km")
    # HydroBASINS puts an outlet on every small catchment, so the CLOSEST one is
    # usually a drain. Snapping to it gave the Ganga a 200-year flood of 148
    # m3/s. Take the largest instead: the main stem carries the most water.
    cand = [(i, idx[gid[i]]) for i in near if gid[i] in idx]
    if not cand:
        print("  none carry return periods"); continue
    k, j = max(cand, key=lambda c: two[c[1]])
    print(f"  main stem: {gid[k]} at {lat[k]:.4f},{lon[k]:.4f}, {d[k]:.1f} km away")
    vals = [(p, float(rp[f"return_period_{p}"][j])) for p in periods]
    print("  " + "  ".join(f"{p}y {v:,.0f}" for p, v in vals) + "  m3/s")

    # place the discharge we already used against that scale
    q = hazard.discharge(glat, glon, ev.sar_base, ev.sar_flood)
    obs = {d_: v for d_, v in q.items() if v is not None}
    if not obs:
        continue
    peak_d = max(obs, key=obs.get); peak = obs[peak_d]
    above = [p for p, v in vals if peak >= v]
    verdict = (f"about a 1-in-{max(above)}-year event or worse" if above
               else f"below the {periods[0]}-year level")
    print(f"  GloFAS peak in our window: {peak:,.0f} m3/s on {peak_d}")
    print(f"  -> {verdict}")
    print(f"     (GloFAS and Google are different models; comparing one to the"
          f" other's\n      return periods is indicative, not a calibration.)")
