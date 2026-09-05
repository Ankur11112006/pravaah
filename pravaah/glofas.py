"""The two live forecast calls, kept away from the raster stack.

Both of these are plain HTTP against free public services, but they used to sit
in hazard.py, which imports rasterio and scipy at module level. That meant the
backend could not answer "what is the flood probability" without installing the
whole geospatial pipeline, on a server that never opens a raster. They live here
so the API needs numpy and nothing else.

hazard.py re-exports them, so every pipeline script that already imports them
from there keeps working.
"""
import json, urllib.parse, urllib.request
import numpy as np


def main_stem_gauge(lat, lon, radius_km=25, cache="data/_gauge_cache.json"):
    """The Google Flood Hub outlet for the MAIN RIVER near a point, with its
    return periods.

    HydroBASINS puts an outlet on every small catchment, so the nearest one is
    usually a drain: at Patna it gave the Ganga a 200-year flood of 148 m3/s.
    Pick the largest within the radius instead. Source is
    gs://flood-forecasting, CC-BY-4.0."""
    import json as _json, os
    key = f"{lat:.4f},{lon:.4f},{radius_km}"
    if os.path.exists(cache):
        c = _json.load(open(cache))
        if key in c:
            return c[key]
    import zarr, fsspec
    B = ("https://storage.googleapis.com/flood-forecasting/hydrologic_predictions"
         "/model_id_8583a5c2_v0")
    op = lambda p: zarr.open(fsspec.get_mapper(f"{B}/{p}"), mode="r")
    loc = op("hybas_outlet_locations_UNOFFICIAL.zarr")
    la, lo, gid = loc["latitude"][:], loc["longitude"][:], loc["gauge_id"][:]
    rp = op("return_periods.zarr")
    idx = {g: i for i, g in enumerate(rp["gauge_id"][:])}
    periods = sorted(int(k.split("_")[-1]) for k in rp.array_keys()
                     if k.startswith("return_period_"))
    two = rp["return_period_2"][:]
    d = np.hypot(la - lat, lo - lon) * 111.0
    cand = [(i, idx[gid[i]]) for i in np.nonzero(d < radius_km)[0] if gid[i] in idx]
    if not cand:
        raise SystemExit(f"no Google outlet with return periods within "
                         f"{radius_km} km of {lat},{lon}")
    k, j = max(cand, key=lambda c: two[c[1]])
    out = dict(gauge_id=str(gid[k]), lat=float(la[k]), lon=float(lo[k]),
               km_away=float(d[k]),
               rp={str(p): float(rp[f"return_period_{p}"][j]) for p in periods})
    c = _json.load(open(cache)) if os.path.exists(cache) else {}
    c[key] = out
    _json.dump(c, open(cache, "w"), indent=1)
    return out


def ensemble(lat, lon, days=30):
    """GloFAS 50-member ensemble discharge forecast. Free, no key."""
    q = urllib.parse.urlencode(dict(
        latitude=lat, longitude=lon, forecast_days=days, ensemble="true",
        daily="river_discharge"))
    with urllib.request.urlopen(
            "https://flood-api.open-meteo.com/v1/flood?" + q, timeout=90) as r:
        d = json.load(r)["daily"]
    members = [k for k in d if k.startswith("river_discharge_member")]
    arr = np.array([[d[m][i] for m in members] for i in range(len(d["time"]))],
                   dtype="float64")
    return d["time"], arr          # (days, members)
