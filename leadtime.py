"""The headline metric the original spec asked for and we never had:

    useful lead time = when the river actually crossed a danger threshold
                       minus when a forecast first said it would

Google's GRRR reforecast covers 2016-2022 at lead times 0 to 7 days, so for
Patna 2019 we can ask what a forecaster would genuinely have known, days ahead.
The "actual" is Google's own reanalysis, so forecast and truth come from the
same model: this measures lead time, not model skill.

Source: gs://flood-forecasting, CC-BY-4.0.
"""
import sys
import numpy as np, pandas as pd, xarray as xr
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import config, hazard

EV = config.EVENTS[sys.argv[1] if len(sys.argv) > 1 else "patna"]
WINDOW = ("2019-09-05", "2019-10-15")
B = ("https://storage.googleapis.com/flood-forecasting/hydrologic_predictions"
     "/model_id_8583a5c2_v0")

g = hazard.main_stem_gauge(*EV.gauge)
gid, rp = g["gauge_id"], {int(k): v for k, v in g["rp"].items()}
print(f"{EV.name}: gauge {gid}  ({g['km_away']:.1f} km from the reference point)")

op = lambda p: xr.open_zarr(f"{B}/{p}", chunks=None)
rean = op("reanalysis/streamflow.zarr/").sel(gauge_id=gid)
fcst = op("reforecast/streamflow.zarr/").sel(gauge_id=gid)

act = rean.streamflow.sel(time=slice(*WINDOW)).compute()
at = pd.to_datetime(act.time.values)
peak_i = int(np.argmax(act.values))
print(f"  reanalysis peak {float(act.values[peak_i]):,.0f} m3/s on {at[peak_i]:%d %b %Y}")

sub = fcst.sel(issue_time=slice(*WINDOW)).compute()
its = pd.to_datetime(sub.issue_time.values)
# lead_time is 0..7 days. It arrives as a raw offset, and reading it as
# nanoseconds silently collapses every column to lead 0, which makes the answer
# come out as "no warning at all". Normalise it to whole days explicitly.
raw = np.asarray(sub.lead_time.values)
if np.issubdtype(raw.dtype, np.timedelta64):
    lead_days = (raw / np.timedelta64(1, "D")).astype(int)
else:
    lead_days = raw.astype("int64")
    if lead_days.max() > 7:                       # nanoseconds, not days
        lead_days = (lead_days // 86_400_000_000_000).astype(int)
print(f"  reforecast: {len(its)} issue dates, lead days {lead_days.tolist()}")

print(f"\n  {'threshold':<12}{'crossed on':<14}{'first warned':<14}"
      f"{'lead':>6}{'forecast':>11}")
print("  " + "-" * 60)
for RP in (2, 5, 10):
    thr = rp[RP]
    over = at[act.values >= thr]
    if not len(over):
        print(f"  {str(RP)+'-year':<12}{'never in window':<14}"
              f"{'':<14}{'':>6}{thr:>11,.0f}")
        continue
    cross = over[0]
    # Alignment matters and the dataset warns about it: reanalysis is LEFT
    # labelled (time T is the day starting at T) while reforecast lead_time is
    # RIGHT labelled (lead L is the window ending at T+L). So the forecast for
    # reanalysis day D is the one where issue_time + lead == D + 1 day. Adding
    # them naively gave a 15-day lead out of a 7-day model, which is how the
    # mistake announced itself.
    want = cross + pd.Timedelta(days=1)
    hit = None
    for i, it in enumerate(its):
        v = sub.streamflow.values[i]
        for j, ld in enumerate(lead_days):
            if it + pd.Timedelta(days=int(ld)) == want and v[j] >= thr:
                hit = (it, int(ld), float(v[j]))
                break
        if hit:
            break
    if hit is None:
        print(f"  {str(RP)+'-year':<12}{cross:%d %b %Y}   {'no warning':<14}"
              f"{'':>6}{thr:>11,.0f}")
        continue
    it, ld, v = hit
    print(f"  {str(RP)+'-year':<12}{cross:%d %b %Y}   {it:%d %b %Y}   "
          f"{(cross - it).days:>3} d{v:>11,.0f}")

print(f"\n  thresholds: " + "  ".join(f"{k}y {v:,.0f}" for k, v in
                                      sorted(rp.items())[:4]) + "  m3/s")
print("  The spec asked for 48 to 72 hours at ward level. The river signal is")
print("  what sets the ceiling; the rest of the pipeline spends that time, it")
print("  never adds any.")

# The dataset's own consistency identity, checked rather than assumed:
#   Reanalysis[time=T] == Reforecast[issue_time=T+1, lead_time=0]
z = int(np.nonzero(lead_days == 0)[0][0])
aset = list(at)
for i, it in enumerate(its):
    prev = it - pd.Timedelta(days=1)
    if prev in aset:
        r0 = float(act.values[aset.index(prev)])
        f0 = float(sub.streamflow.values[i][z])
        print(f"\n  identity check: reanalysis[{prev:%d %b}] = {r0:,.0f}  vs  "
              f"reforecast[{it:%d %b}, lead 0] = {f0:,.0f}  -> "
              f"{'match' if abs(r0 - f0) < 1.0 else 'MISMATCH'}")
        break
