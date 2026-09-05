"""Client for CWC's Flood Forecasting System, ffs.india-water.gov.in.

No key, no login. The service speaks a Spring-Data style JSON "specification"
query language; the helpers below hide that. This is India's operational flood
forecast network: 200+ gauged stations with official danger, warning and
highest-ever levels, live observed water level, and issued forecasts.

Our earlier documents called this "government login only". That was wrong.
"""
import json, urllib.parse, urllib.request

BASE = "https://ffs.india-water.gov.in/iam/api"
UA = {"User-Agent": "Mozilla/5.0 (pravaah flood research)"}


def _get(path, spec=None, timeout=240):
    url = f"{BASE}/{path}"
    if spec is not None:
        url += "?" + urllib.parse.urlencode({"specification": json.dumps(spec)})
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _eq(field, value):
    return {"valueIsRelationField": False, "fieldName": field,
            "operator": "eq", "value": value}


def stations(kind="Level"):
    """Static station facts: danger / warning / highest-ever level, catchment."""
    return {s["stationCode"]: s for s in _get(
        "flood-forecast-static/specification/", {"where": {"expression": _eq("type", kind)}})}


def geography(kind="Level"):
    """Station name and coordinates."""
    return {g["stationCode"]: g for g in _get(
        "layer-station-geo/specification/",
        {"where": {"expression": _eq(
            "layerStationStationCode.floodForecastStaticStationCode.type", kind)}})}


def observed(kind="Level", datatype="HHS"):
    """Latest observed reading per station. HHS is hourly water level."""
    rows = _get("new-entry-data-aggregate/specification/",
                {"where": {"expression": _eq("id.datatypeCode", datatype)},
                 "and": {"expression": _eq(
                     "stationCode.floodForecastStaticStationCode.type", kind)}})
    out = {}
    for r in rows:
        c = r.get("stationCode")
        if c and (c not in out or r.get("latestDataTime", "") > out[c].get("latestDataTime", "")):
            out[c] = r
    return out


def forecasts(since):
    """Issued forecasts with a forecast date after `since` (ISO string)."""
    rows = _get("new-forecasted-entry-data/specification/",
                {"expression": {"valueIsRelationField": False,
                                "fieldName": "id.forecastedDate",
                                "operator": "gt", "value": since}})
    by = {}
    for r in rows:
        by.setdefault(r["stationCode"], []).append(r)
    for v in by.values():
        v.sort(key=lambda r: r["id"]["forecastedDate"])
    return by


def snapshot(since):
    """Everything joined: one row per station, for both Level and Inflow networks."""
    out = {}
    for kind in ("Level", "Inflow"):
        st, geo = stations(kind), geography(kind)
        obs = observed(kind)
        for c, s in st.items():
            g = geo.get(c, {})
            o = obs.get(c, {})
            out[c] = dict(code=c, kind=kind, name=g.get("name"),
                          lat=g.get("lat"), lon=g.get("lon"),
                          danger=s.get("dangerLevel"), warning=s.get("warningLevel"),
                          hfl=s.get("highestFlowLevel"),
                          observed=o.get("latestDataValue"),
                          observed_at=o.get("latestDataTime"))
    # CWC's forecast endpoint fails on its own from time to time, with a 500
    # while the level endpoints are answering perfectly. Losing the forecast
    # column is a smaller loss than losing every live level in the country, so
    # this degrades instead of raising.
    try:
        fc = forecasts(since)
    except Exception as e:
        print(f"  cwc: forecasts unavailable ({e}); levels are still live")
        fc = {}
    for c, rows in fc.items():
        if c in out:
            out[c]["forecast"] = [(r["id"]["forecastedDate"], r["realValue"], r.get("trend"))
                                  for r in rows]
    return out
