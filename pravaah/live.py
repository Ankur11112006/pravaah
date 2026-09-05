"""Everything that answers for ANY point in India, right now.

The modelled half of this project (depth, shelters, which road closes when)
exists only for districts the pipeline has been run for, and it is built from a
past event, because comparing an answer against what actually happened is the
only way to know the answer is worth anything.

This module is the other half, and it has no model in it at all:

    geocode     what somebody typed     ->  real places
    reverse     a GPS fix               ->  the name of that place
    national    CWC's gauge network     ->  refreshed in the background
    river_at    any point               ->  the nearest gauges, live

Nothing here is synthetic and nothing is remembered from a past flood. Every
number is what the issuing agency is publishing at the moment it is asked for,
and each one carries the time it was published so a stale one cannot pass for a
fresh one.

Sources, all free and all keyless: Open-Meteo geocoding, OpenStreetMap
Nominatim, and the Central Water Commission's own flood forecasting service.
"""
import json
import math
import os
import threading
import time
import urllib.parse
import urllib.request
import datetime as dt

UA = {"User-Agent": "pravaah-flood-dss/1.0 (flood decision support for Indian "
                    "districts; contact via the project README)"}
CACHE_DIR = "data/live"
_lock = threading.Lock()
_mem: dict = {}
_last_nominatim = [0.0]


# ------------------------------------------------------------------ helpers
def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _cached(key, ttl, fn):
    """Memory first, then a file on disk, then the network.

    The disk layer matters more than it looks: a district laptop that has looked
    up its own town once should still name it after a restart with the wifi
    down.
    """
    hit = _mem.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    path = os.path.join(CACHE_DIR, urllib.parse.quote(key, safe="") + ".json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl:
        try:
            v = json.load(open(path, encoding="utf-8"))
            _mem[key] = (time.time(), v)
            return v
        except Exception:
            pass
    v = fn()
    _mem[key] = (time.time(), v)
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        json.dump(v, open(path, "w", encoding="utf-8"))
    except Exception:
        pass
    return v


def km_between(lat1, lon1, lat2, lon2):
    """Great-circle distance. Flat-earth arithmetic is wrong by enough to
    reorder two gauges that are nearly the same distance away."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


# ---------------------------------------------------------------- geocoding
def _label(name, district, state):
    """Name first, then only the parts that add something.

    Written the other way round at first, which dropped the name and left a
    person choosing between "Bihar" and "Bihar": the one word that identifies
    the place was the one being filtered out. A district called "Patna
    District" beside a city called "Patna" adds nothing either.
    """
    parts = [name]
    for x in (district, state):
        if not x:
            continue
        if x == name or x.replace(" District", "") == name:
            continue
        if x in parts:
            continue
        parts.append(x)
    return ", ".join(parts)


def geocode(q, limit=8):
    """What somebody typed, as real places with coordinates.

    The app used to offer a fixed list of eighteen reporting units, which meant
    it had nothing to say to anybody outside one district. Anyone can type where
    they are now.
    """
    q = (q or "").strip()
    if len(q) < 2:
        return []

    def fetch():
        url = ("https://geocoding-api.open-meteo.com/v1/search?"
               + urllib.parse.urlencode(dict(name=q, count=30, language="en",
                                             format="json")))
        return _get(url).get("results") or []

    rows = _cached(f"geo.{q.lower()}", 86400, fetch)
    out = []
    for r in rows:
        # India only. The same name exists in a dozen countries and a person
        # looking for Bhagalpur does not mean the one in Dhaka Division.
        if r.get("country_code") != "IN":
            continue
        out.append(dict(
            name=r["name"], lat=round(r["latitude"], 5), lon=round(r["longitude"], 5),
            district=r.get("admin2"), state=r.get("admin1"),
            population=r.get("population"),
            label=_label(r["name"], r.get("admin2"), r.get("admin1"))))
    # Biggest first: somebody typing "Patna" means the city, not a hamlet.
    out.sort(key=lambda x: -(x["population"] or 0))
    return out[:limit]


def reverse(lat, lon):
    """The name of the place a GPS fix landed in.

    Nominatim asks for one request a second and a real User-Agent, and asks that
    results be cached. All three are honoured here: the phone never talks to
    them, this server does, once per place, and keeps the answer.
    """
    key = f"rev.{round(float(lat), 3)},{round(float(lon), 3)}"

    def fetch():
        gap = 1.1 - (time.time() - _last_nominatim[0])
        if gap > 0:
            time.sleep(gap)
        _last_nominatim[0] = time.time()
        url = ("https://nominatim.openstreetmap.org/reverse?"
               + urllib.parse.urlencode(dict(format="jsonv2", lat=lat, lon=lon,
                                             zoom=12, addressdetails=1)))
        return _get(url)

    d = _cached(key, 86400 * 30, fetch)
    a = d.get("address", {}) if isinstance(d, dict) else {}
    name = (a.get("city") or a.get("town") or a.get("village") or a.get("suburb")
            or a.get("county") or d.get("name") or "Your location")
    district = a.get("state_district") or a.get("county")
    state = a.get("state")
    return dict(name=name, district=district, state=state,
                label=_label(name, district, state),
                lat=round(float(lat), 5), lon=round(float(lon), 5))


# ------------------------------------------------------------ CWC, live
NATIONAL = "out/national_data.json"
_refreshing = [False]


def _build_national():
    """One live pull of CWC's whole forecast network, plus NDMA's alert feed."""
    from pravaah import cwc, sachet
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
        rows.append(dict(n=s["name"] or s["code"], c=s["code"], k=s["kind"],
                         la=round(s["lat"], 4), lo=round(s["lon"], 4),
                         o=o, d=d, w=w, h=s["hfl"], st=st,
                         t=(s["observed_at"] or "")[:16],
                         f=[[a[:10], b, c] for a, b, c in s.get("forecast", [])][:6]))
    alerts = []
    try:
        for x in sachet.water_alerts(sachet.alerts()):
            c = sachet.centroid(x)
            alerts.append(dict(sev=x.get("severity"), kind=x.get("disaster_type"),
                               area=str(x.get("area_description") or "")[:90],
                               msg=str(x.get("warning_message") or "")[:300],
                               la=c[0] if c else None, lo=c[1] if c else None,
                               start=str(x.get("effective_start_time") or "")[:24]))
    except Exception:
        pass
    out = dict(rows=rows, alerts=alerts, cflood=None,
               built=dt.datetime.now().strftime("%d %b %Y %H:%M"),
               built_epoch=time.time(),
               source="Central Water Commission, ffs.india-water.gov.in")
    os.makedirs("out", exist_ok=True)
    tmp = NATIONAL + ".tmp"
    json.dump(out, open(tmp, "w"), separators=(",", ":"))
    os.replace(tmp, NATIONAL)
    return out


STALE_LIMIT = 6 * 3600      # older than this and it is not "now" any more


def national(max_age=1800, block_if_missing=True):
    """CWC's network as it is now, refreshed in the background when it ages.

    A phone asking what the river is doing must not wait eight seconds for a
    government API. It gets the last snapshot immediately and a refresh starts
    behind it, so the next question is answered with newer numbers. The one time
    it blocks is when there is no snapshot at all, because an empty screen is
    worse than a wait.
    """
    have = os.path.exists(NATIONAL)
    if not have:
        return _build_national() if block_if_missing else None
    age = time.time() - os.path.getmtime(NATIONAL)
    # Serving a five-day-old river level under the word "live" is the exact
    # thing this project exists not to do. Past a point, wait for the real one.
    if age > STALE_LIMIT:
        try:
            return dict(_build_national(), age_seconds=0)
        except Exception as e:
            print(f"  live: CWC unreachable, falling back to a {age/3600:.0f}h "
                  f"old snapshot: {e}")
    d = json.load(open(NATIONAL, encoding="utf-8"))
    d["age_seconds"] = int(age)
    if age > max_age and not _refreshing[0]:
        def run():
            _refreshing[0] = True
            try:
                _build_national()
            except Exception as e:
                print(f"  live: national refresh failed: {e}")
            finally:
                _refreshing[0] = False
        threading.Thread(target=run, daemon=True).start()
    return d


def river_at(lat, lon, km=250, count=4):
    """The gauges nearest a point, with what they are reading right now.

    This is the most honest thing this system can tell somebody standing in an
    unmodelled town: not a simulated depth for their street, but the real level
    at the nearest official gauge, its official danger mark, and how old the
    reading is.
    """
    d = national()
    rows = d.get("rows", [])
    near = []
    for r in rows:
        if r["o"] is None:
            continue                      # a silent gauge is not a reading
        dist = km_between(lat, lon, r["la"], r["lo"])
        if dist <= km:
            near.append((dist, r))
    near.sort(key=lambda x: x[0])
    out = []
    for dist, r in near[:count]:
        above = None
        if r["d"] is not None:
            above = round(r["o"] - r["d"], 2)
        out.append(dict(
            name=r["n"], kind=r["k"], km=round(dist, 1),
            lat=r["la"], lon=r["lo"], level=r["o"], danger=r["d"],
            warning=r["w"], hfl=r["h"], above_danger=above,
            status={2: "above danger", 1: "above warning", 0: "normal"}.get(r["st"]),
            at=r["t"], forecast=r.get("f") or []))
    return dict(gauges=out, searched_km=km, built=d.get("built"),
                age_seconds=d.get("age_seconds"),
                source="Central Water Commission flood forecasting network")
