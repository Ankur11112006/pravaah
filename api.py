"""PRAVAAH backend.

    .venv\\Scripts\\python.exe -m uvicorn api:app --port 8010

Read endpoints serve what the pipeline computed. Write endpoints accept the
things no satellite and no gauge can see: a person saying how deep the water is
outside their door, a person saying they cannot leave, and an officer approving
or overriding a recommendation.

That last group is the point. Every failure this project measured came from the
same place: the instruments miss urban flooding. A citizen report is the only
sensor that does not.
"""
import json, os, sys, time
import datetime as dt
from typing import Optional

from fastapi import (FastAPI, HTTPException, Query, UploadFile, File, Form,
                     Response)
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pravaah import config, store

app = FastAPI(title="PRAVAAH", version="1.0",
              description="A decision layer for Indian floods.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

OUT = "out"
_cache: dict = {}


def _load(path, ttl=30):
    """Read a pipeline output, cached briefly so a dashboard polling every few
    seconds does not re-read a 1.7 MB file every time."""
    hit = _cache.get(path)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _cache[path] = (time.time(), data)
    return data


def _need(data, what):
    if data is None:
        raise HTTPException(404, f"{what} has not been generated yet; "
                                 f"run the pipeline first")
    return data


def _event(ev):
    if ev not in config.EVENTS:
        raise HTTPException(404, f"unknown event {ev!r}; "
                                 f"have {sorted(config.EVENTS)}")
    return config.EVENTS[ev]


# ------------------------------------------------------------------ meta
@app.get("/api/health")
def health():
    ok = {}
    for ev in config.EVENTS:
        ok[ev] = dict(
            plan=os.path.exists(f"{OUT}/{ev}_deadlines.json"),
            citizen=os.path.exists(f"{OUT}/{ev}_citizen_data.json"),
            hazard_mode=config.EVENTS[ev].hazard)
    return dict(status="ok", time=store.now(), events=ok,
                db=os.path.abspath(store.DB), store=store.summary())


@app.get("/api/events")
def events():
    return [dict(name=e.name, aoi=e.aoi, hazard=e.hazard, gauge=e.gauge)
            for e in config.EVENTS.values()]


# ------------------------------------------------------------------ national
@app.get("/api/national")
def national():
    """CWC stations and NDMA alerts, as they are right now.

    This used to serve whatever `build_national.py` last wrote, which on the day
    it mattered was five days old and said the Ganga at Patna was below its
    danger level when it had been above it for three days. It refreshes itself
    now, in the background, and refuses to serve a snapshot old enough to be
    wrong about the thing it is for.
    """
    from pravaah import live
    d = _need(live.national(), "the national snapshot")
    rows = d["rows"]
    return dict(built=d["built"], source=d["source"], cflood=d.get("cflood"),
                age_seconds=d.get("age_seconds"),
                counts=dict(
                    total=len(rows),
                    above_danger=sum(1 for r in rows if r["st"] == 2),
                    above_warning=sum(1 for r in rows if r["st"] == 1),
                    normal=sum(1 for r in rows if r["st"] == 0),
                    not_reporting=sum(1 for r in rows if r["st"] is None)),
                alerts=len(d.get("alerts", [])), stations=rows)


@app.get("/api/national/alerts")
def national_alerts(limit: int = Query(50, ge=1, le=200)):
    d = _need(_load(f"{OUT}/national_data.json", ttl=120), "the national snapshot")
    return d.get("alerts", [])[:limit]


@app.get("/api/national/above-danger")
def above_danger():
    d = _need(_load(f"{OUT}/national_data.json", ttl=120), "the national snapshot")
    rows = [r for r in d["rows"] if r["st"] == 2]
    rows.sort(key=lambda r: -(r["o"] - r["d"]))
    return rows


# ------------------------------------------------------------------ per event
@app.get("/api/events/{ev}/plan")
def plan(ev: str):
    _event(ev)
    from pravaah import timeline as _tl
    raw = _need(_load(f"{OUT}/{ev}_deadlines.json"), f"the plan for {ev}")
    # the file carries its own unit now: metres of water level for a stage-fitted
    # event, frame index for a C-Flood one. Older flat files are metres.
    dl = raw.get("points", raw)
    cutoff_unit = raw.get("unit", "metres") if isinstance(raw, dict) else "metres"
    # The list, not the dict. Two Delhi schools share a name, and the dict form
    # collapses them into one entry, so counting sites or people from it loses
    # whichever one was written first.
    sites = _load(f"{OUT}/{ev}_allocation_sites.json")
    al = sites if sites is not None else _load(f"{OUT}/{ev}_allocation.json") or {}
    tot = sum(v["people"] for v in dl.values())
    none_ = sum(v["people"] for v in dl.values() if v["car_cutoff"] == float("-inf"))
    brg = sum(v["people"] for v in dl.values()
              if v["car_cutoff"] != float("-inf") and v["bridge_dependent"])
    placed = (sum(x["assigned"] for x in al) if isinstance(al, list)
              else sum(al.values()))
    # Two different totals, named apart on purpose. people_wet is everyone the
    # exposure step found standing in water. people_planned is the subset the
    # plan is actually built on: a pickup point needs a road within reach and at
    # least one whole person, so isolated fractional cells carry no point. The
    # arithmetic closes on the second, never the first. Calling both of them
    # "people_wet" is what let the plan quote one number while the exposure
    # table quoted another.
    wet = None
    ex = f"{OUT}/{ev}_exposure.csv"
    if os.path.exists(ex):
        import csv
        with open(ex, encoding="utf-8") as f:
            wet = round(sum(float(r["people"]) for r in csv.DictReader(f)))
    # The four-way split, per event. The control room used to draw Patna's
    # numbers under every district's name because this was not served.
    survival = raw.get("survival") if isinstance(raw, dict) else None
    if survival is None and isinstance(raw, dict) and "points" in raw:
        survival = {"car": _tl.survival(dl, raw.get("first", 0.0),
                                        raw.get("last", 0.0))}

    return dict(event=ev, cutoff_unit=cutoff_unit, survival=survival,
                people_wet=wet, people_planned=tot,
                not_planned=(wet - tot) if wet is not None else None,
                placed=placed, shelters_used=len(al),
                beyond_reach=tot - placed - none_, no_route=none_,
                bridge_dependent=brg,
                arithmetic="placed + beyond_reach + no_route == people_planned",
                caveat="bridge_dependent people are placed only because a bridge "
                       "is assumed open; nobody has confirmed it")


@app.get("/api/events/{ev}/units")
def units(ev: str):
    d = _need(_load(f"{OUT}/{ev}_citizen_data.json"), f"the citizen data for {ev}")
    return d["units"]


@app.get("/api/events/{ev}/units/{place}")
def unit(ev: str, place: str):
    d = _need(_load(f"{OUT}/{ev}_citizen_data.json"), f"the citizen data for {ev}")
    for u in d["units"]:
        if u["place"].lower() == place.lower():
            near = sorted(d["roads"],
                          key=lambda r: (r["lat"] - (u["lat"] or r["lat"])) ** 2
                          + (r["lon"] - (u["lon"] or r["lon"])) ** 2)[:5]
            return dict(**u, roads_near=near, modes=d["modes"],
                        reports=store.reports(event=ev, limit=20))
    raise HTTPException(404, f"no reporting unit named {place!r} in {ev}")


@app.get("/api/events/{ev}/roads")
def roads(ev: str):
    d = _need(_load(f"{OUT}/{ev}_citizen_data.json"), f"the citizen data for {ev}")
    return d["roads"]


@app.get("/api/events/{ev}/shelters")
def shelters(ev: str, open_only: bool = False):
    import csv
    path = f"data/{ev}_shelters_measured.csv"
    if not os.path.exists(path):
        raise HTTPException(404, f"no measured shelters for {ev}")
    # Matched by line number in the measured file. A name is not unique (Delhi
    # has five separate buildings called "MCD Primary School", and matching on
    # the name showed all five the same six people) and neither side rounds a
    # coordinate the same way. Capacity comes from the allocation too, since
    # campuses that share a road node were filled as one site against their
    # combined roof; dividing by one building's roof printed 187% full.
    sites = _load(f"{OUT}/{ev}_allocation_sites.json") or []
    by_row = {x["row"]: x for x in sites if "row" in x}
    out = []
    with open(path, encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f)):
            lat, lon = float(r["lat"]), float(r["lon"])
            name = r["name"] or f'{r["kind"]} at {lat:.4f}N {lon:.4f}E'
            hit = by_row.get(i)
            assigned = hit["assigned"] if hit else 0
            cap = int(hit["cap"]) if hit else int(r["cap"])
            out.append(dict(name=name,
                            kind=r["kind"], lat=lat, lon=lon,
                            capacity=cap, roof_m2=float(r["roof_m2"]),
                            assigned=assigned,
                            use=round(assigned / cap, 3) if cap else None))
    out.sort(key=lambda s: -s["assigned"])
    total = len(out)
    if open_only:
        # Delhi has 929 measured shelters and 11 open ones. A control room
        # polling every four seconds does not need 164 kB of closed buildings
        # each time; it needs the open ones and the count it is out of.
        out = [s for s in out if s["assigned"]]
    return dict(basis="roof footprint / 3.5 sq m per person, NDMA Guidelines on "
                      "Minimum Standards of Relief section 2(c)",
                total=total, shelters=out)


# ------------------------------------------------------------------ writes
@app.post("/api/reports", status_code=201)
async def post_report(
        event: str = Form(...), kind: str = Form(...),
        place: Optional[str] = Form(None),
        lat: Optional[float] = Form(None), lon: Optional[float] = Form(None),
        depth_cm: Optional[int] = Form(None), note: Optional[str] = Form(None),
        road: Optional[str] = Form(None), photo: Optional[UploadFile] = File(None)):
    """What a person can see and the instruments cannot."""
    _event(event)
    try:
        rid = store.add_report(event, kind, place, lat, lon, depth_cm, note, None, road)
    except ValueError as e:
        raise HTTPException(422, str(e))
    saved = None
    if photo is not None:
        data = await photo.read()
        if data:
            ext = os.path.splitext(photo.filename or "")[1].lower() or ".jpg"
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                raise HTTPException(415, "photo must be jpg, png or webp")
            try:
                saved = store.save_photo(rid, data, ext)
            except ValueError as e:
                raise HTTPException(413, str(e))
    return dict(id=rid, photo=saved, status="new")


@app.get("/api/reports")
def get_reports(event: Optional[str] = None, status: Optional[str] = None,
                kind: Optional[str] = None, limit: int = Query(200, ge=1, le=1000)):
    return store.reports(event, status, kind, limit)


@app.post("/api/reports/{rid}/resolve")
def resolve(rid: int, by: str = Form("officer")):
    if not store.resolve_report(rid, by):
        raise HTTPException(404, "no open report with that id")
    return dict(id=rid, status="resolved")


@app.get("/api/reports/{rid}/photo")
def photo(rid: int):
    rows = [r for r in store.reports(limit=1000) if r["id"] == rid]
    if not rows or not rows[0]["photo"]:
        raise HTTPException(404, "no photo on that report")
    return FileResponse(os.path.join(store.PHOTOS, rows[0]["photo"]))


@app.post("/api/help", status_code=201)
def post_help(event: str = Form(...), place: Optional[str] = Form(None),
              lat: Optional[float] = Form(None), lon: Optional[float] = Form(None),
              people: int = Form(1), mobility: Optional[str] = Form(None),
              contact: Optional[str] = Form(None), note: Optional[str] = Form(None)):
    """"I cannot leave" is a different request from "there is water here"."""
    _event(event)
    try:
        hid = store.add_help(event, place, lat, lon, people, mobility, contact, note)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return dict(id=hid, status="waiting",
                note="queued by mobility first, then group size, then age")


@app.get("/api/help")
def get_help(event: Optional[str] = None, status: Optional[str] = None,
             limit: int = Query(200, ge=1, le=1000)):
    return store.help_queue(event, status, limit)


@app.post("/api/help/{hid}/assign")
def assign(hid: int, team: str = Form(...), eta: Optional[str] = Form(None)):
    if not store.assign_help(hid, team, eta):
        raise HTTPException(404, "no waiting request with that id")
    return dict(id=hid, status="assigned", team=team, eta=eta)


@app.post("/api/help/{hid}/close")
def close(hid: int):
    if not store.close_help(hid):
        raise HTTPException(404, "no request with that id")
    return dict(id=hid, status="closed")


@app.post("/api/decisions", status_code=201)
def post_decision(event: str = Form(...), action: str = Form(...),
                  decision: str = Form(...),
                  probability: Optional[float] = Form(None),
                  threshold: Optional[float] = Form(None),
                  reason: Optional[str] = Form(None),
                  officer: Optional[str] = Form(None)):
    """Approvals and overrides, logged where they survive a closed browser."""
    _event(event)
    try:
        did = store.add_decision(event, action, decision, probability, threshold,
                                 reason, officer)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return dict(id=did, decision=decision)


@app.get("/api/decisions")
def get_decisions(event: Optional[str] = None,
                  limit: int = Query(200, ge=1, le=1000)):
    return store.decisions(event, limit)


@app.get("/")
def root():
    """The control room page, served by the same process that serves its data.

    One command starts the whole demo, and the page's API base is just its own
    origin, so there is no address to type and nothing to get wrong on stage.
    """
    page = os.path.join(OUT, "pravaah_control.html")
    if not os.path.exists(page):
        raise HTTPException(404, "pravaah_control.html has not been built yet")
    return FileResponse(page, media_type="text/html")


@app.get("/ui")
def ui_walkthrough():
    """The layout walkthrough, kept separate from the working control room."""
    page = os.path.join(OUT, "pravaah_ui.html")
    if not os.path.exists(page):
        raise HTTPException(404, "pravaah_ui.html has not been built yet")
    return FileResponse(page, media_type="text/html")


@app.get("/api/alerts")
def alerts(lat: Optional[float] = None, lon: Optional[float] = None,
           km: float = Query(200, ge=1, le=2000), water_only: bool = False,
           q: Optional[str] = None, limit: int = Query(100, ge=1, le=500)):
    """Live NDMA SACHET alerts, shaped for a phone.

    With lat/lon it answers "what is happening near me", nearest first, which is
    the only question a person in a flood actually has. Without them it is the
    national picture. `live` is false when the network was unreachable and these
    came off disk; the app is expected to say so rather than imply freshness.
    """
    from pravaah import alertfeed
    rows, at, live = alertfeed.fetch()
    if water_only:
        rows = [r for r in rows if r["water"]]
    if q:
        needle = q.lower()
        rows = [r for r in rows
                if needle in r["kind"].lower() or needle in r["area"].lower()
                or needle in r["message"].lower() or needle in r["issuer"].lower()]
    if lat is not None and lon is not None:
        rows = alertfeed.near(rows, lat, lon, km)
    return dict(live=live, fetched=at, count=len(rows), alerts=rows[:limit])


@app.get("/api/weather")
def weather(lat: float, lon: float):
    """Current conditions and the next 24 hours, from Open-Meteo.

    Proxied through the backend on purpose: the phone needs no key, the answer
    is cached for everyone at once, and a handset on 2G makes one request to a
    server it is already talking to instead of a second one to the internet.
    """
    import urllib.parse, urllib.request
    key = f"wx:{lat:.3f},{lon:.3f}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 900:
        return hit[1]
    qs = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "precipitation,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_sum,precipitation_probability_max",
        "forecast_days": 5, "timezone": "auto",
    })
    try:
        with urllib.request.urlopen(
                "https://api.open-meteo.com/v1/forecast?" + qs, timeout=12) as r:
            data = json.load(r)
    except Exception as e:
        if hit:
            return dict(hit[1], stale=True)
        raise HTTPException(503, f"weather service unreachable: {e}")
    data["stale"] = False
    _cache[key] = (time.time(), data)
    return data


@app.get("/apk")
def apk(download: bool = True):
    """Hand the citizen app to a phone on the same wifi.

    Sideloading over a cable needs a cable and a laptop; this needs neither. The
    backend is already listening on every interface so the phone can reach the
    API, and the same socket can hand over the installer.
    """
    path = "app/android/app/build/outputs/apk/release/app-release.apk"
    if not os.path.exists(path):
        raise HTTPException(404, "no release APK built yet; run "
                                 "gradlew assembleRelease in app/android")
    return FileResponse(path, media_type="application/vnd.android.package-archive",
                        filename="PRAVAAH.apk")


@app.get("/get")
def get_page():
    """A page a phone can actually read, rather than a raw download link.

    The default server address inside the app is the Android emulator's alias for
    a laptop, which is meaningless on a real handset, so the one setting that has
    to be changed is spelled out here rather than left to be discovered.
    """
    import socket
    ip = "127.0.0.1"
    try:
        s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s_.connect(("8.8.8.8", 80)); ip = s_.getsockname()[0]; s_.close()
    except Exception:
        pass
    have = os.path.exists("app/android/app/build/outputs/apk/release/app-release.apk")
    return HTMLResponse(f"""<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Install PRAVAAH</title>
<style>
 body{{margin:0;background:#0d2c4b;color:#e8eef5;
   font:16px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
 .w{{max-width:520px;margin:0 auto;padding:28px 20px 60px}}
 h1{{font-size:26px;margin:0 0 4px}} .sub{{color:#9fbcdb;margin:0 0 26px}}
 a.btn{{display:block;background:#1565d8;color:#fff;text-align:center;
   text-decoration:none;padding:16px;border-radius:999px;font-weight:600;
   font-size:17px;margin:22px 0}}
 ol{{padding-left:20px}} li{{margin:10px 0;color:#cddcec}}
 code{{background:#12395f;padding:2px 7px;border-radius:5px;font-size:15px}}
 .box{{border:1px solid #3a5b7d;border-radius:12px;padding:14px 16px;margin:20px 0}}
 .box b{{display:block;color:#7fb2ff;font-size:13px;letter-spacing:.6px;
   text-transform:uppercase;margin-bottom:6px}}
 .warn{{border-color:#d29922}} .warn b{{color:#f0b429}}
</style>
<div class=w>
 <h1>PRAVAAH</h1>
 <p class=sub>Flood decision support. Install on this phone.</p>
 {"<a class=btn href='/apk'>Download the app</a>"
  if have else
  "<div class='box warn'><b>Not built yet</b>Run gradlew assembleRelease "
  "in app/android on the laptop, then reload this page.</div>"}
 <div class="box warn">
   <b>One setting to change</b>
   The app ships pointing at an emulator, which does not exist on your phone.
   After it opens: <b style="display:inline;text-transform:none;letter-spacing:0">
   More &rarr; District server address</b>, and set it to
   <code>http://{ip}:8010</code>
 </div>
 <ol>
  <li>Tap <b style="display:inline;text-transform:none;letter-spacing:0;color:#fff">Download the app</b> above.</li>
  <li>Android will warn about installing from a browser. Allow it for this once.</li>
  <li>Open PRAVAAH, accept the terms, and choose your area.</li>
  <li>If it says it cannot reach the district, use the server address above.</li>
 </ol>
 <p style="color:#7e97b3;font-size:13.5px">
  Your phone and this laptop have to be on the same wifi. Nothing leaves that
  network: there is no account, no tracking, and phone numbers are stored
  scrambled.</p>
</div>""")


@app.get("/api/tiles/plan")
def tiles_plan(lat: float, lon: float, km: float = Query(30, ge=2, le=120),
               zmin: int = Query(9, ge=1, le=16), zmax: int = Query(13, ge=1, le=17)):
    """What an offline map for this area would cost, before downloading it.

    The phone shows this on the button, so it has to be the real count, not a
    guess: exact tiles, and bytes measured for whatever is already cached here.
    """
    from pravaah import tiles
    if zmax < zmin:
        raise HTTPException(422, "zmax must not be below zmin")
    return tiles.plan(lat, lon, km, zmin, zmax)


@app.get("/api/tiles/{z}/{x}/{y}.png")
def tile(z: int, x: int, y: int):
    """One map tile, fetched once by this server and reused for every phone.

    This exists so that handsets never hit OpenStreetMap directly. Their tile
    policy forbids bulk downloading, and a few hundred phones each pulling a few
    hundred tiles is exactly that. One polite client, cached on disk.
    """
    from pravaah import tiles
    if not (0 <= z <= 19):
        raise HTTPException(422, "zoom out of range")
    data = tiles.fetch(z, x, y)
    if data is None:
        raise HTTPException(502, "tile unavailable upstream")
    return Response(content=data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=2592000"})


@app.get("/api/reference")
def reference():
    """What the write endpoints will accept, so a client never has to guess."""
    return dict(report_kinds=list(store.KINDS), mobility=list(store.MOBILITY),
                decisions=list(store.DECISIONS), reason_codes=store.REASONS,
                limits=dict(photo_bytes=8_000_000, depth_cm=[0, 1000],
                            people=[1, 500]))


# ------------------------------------------------------------------ forecast
# The cost-loss ladder. Cost of acting, loss avoided if the flood comes: an
# action is authorised when the probability clears cost/loss. Both columns come
# from the NDMA/NIDM relief cost tables, not from a feeling about the weather.
ACTIONS = [("Check and open shelters", 2, 100),
           ("Pre-position boats and crews", 12, 100),
           ("Move livestock to high ground", 20, 100),
           ("Full evacuation of the ward", 55, 100)]
PLANNING_RP = 5


@app.get("/api/events/{ev}/forecast")
def forecast(ev: str):
    """Probability from the live GloFAS ensemble, and what it authorises.

    This used to be a number typed into the control page next to a caption that
    said it was computed. It is computed here: the share of a 50-member
    discharge forecast above a published return period, both free and open.

    Cached for half an hour. GloFAS updates once a day, and a control room
    polling every four seconds must not hammer somebody else's free service.
    """
    e = _event(ev)
    hit = _cache.get(("fc", ev))
    # A failure must not be cached as long as an answer. GloFAS being briefly
    # unreachable used to blank the Act panel for the full half hour, long after
    # the network came back, because the error was stored under the success TTL.
    if hit and time.time() - hit[0] < (120 if hit[1].get("probability") is None
                                       else 1800):
        return hit[1]
    try:
        from pravaah import glofas
        import numpy as np
        g = glofas.main_stem_gauge(*e.gauge)
        rp = {int(k): float(v) for k, v in g["rp"].items()}
        days, ens = glofas.ensemble(g["lat"], g["lon"], days=15)
        rows = [(str(d), float((ens[i] >= rp[PLANNING_RP]).mean()))
                for i, d in enumerate(days)]
        worst = max(rows, key=lambda r: r[1])
        p = worst[1]
        # Every return period, not only the planning one. In the monsoon the
        # 5-year exceedance sits at 100% for a fortnight, which is true and
        # tells an officer nothing. The severe bands are where the discussion
        # actually is, so the page shows the whole ladder of them.
        wi = [r[0] for r in rows].index(worst[0])
        bands = [dict(years=k, threshold_m3s=round(rp[k]),
                      p=round(float((ens[wi] >= rp[k]).mean()), 3))
                 for k in sorted(rp) if k in (2, 5, 10, 20, 25, 50, 100)]
        out = dict(
            event=ev, probability=round(p, 3), worst_day=worst[0],
            members=int(ens.shape[1]), return_period_years=PLANNING_RP,
            threshold_m3s=round(rp[PLANNING_RP]),
            gauge=g["gauge_id"], km_away=round(g["km_away"], 1),
            daily=[dict(day=d, p=round(v, 3)) for d, v in rows], bands=bands,
            actions=[dict(name=nm, cost=c, loss=l, threshold=round(c / l, 3),
                          authorised=p > c / l) for nm, c, l in ACTIONS],
            source="GloFAS 50-member ensemble via Open-Meteo; return periods "
                   "from Google Flood Hub, CC-BY-4.0")
    except Exception as exc:
        # Better an honest gap than a plausible number. The page shows the
        # reason where the probability would have been.
        out = dict(event=ev, probability=None, error=str(exc)[:180],
                   actions=[dict(name=nm, cost=c, loss=l,
                                 threshold=round(c / l, 3), authorised=None)
                            for nm, c, l in ACTIONS])
    _cache[("fc", ev)] = (time.time(), out)
    return out


# ---------------------------------------------------------------- anywhere
# The three endpoints that let the app work outside the districts the pipeline
# has been run for. Nothing here is modelled and nothing is remembered from a
# past flood: it is what the agencies are publishing at the moment it is asked.
@app.get("/api/geocode")
def geocode(q: str = Query(..., min_length=2, max_length=80),
            limit: int = Query(8, ge=1, le=20)):
    """Places matching what somebody typed, anywhere in India."""
    from pravaah import live
    try:
        return live.geocode(q, limit)
    except Exception as e:
        raise HTTPException(503, f"place search unavailable: {e}")


@app.get("/api/place")
def place(lat: float = Query(..., ge=-90, le=90),
          lon: float = Query(..., ge=-180, le=180)):
    """The name of the place a GPS fix landed in."""
    from pravaah import live
    try:
        return live.reverse(lat, lon)
    except Exception as e:
        raise HTTPException(503, f"place lookup unavailable: {e}")


@app.get("/api/river")
def river(lat: float = Query(..., ge=-90, le=90),
          lon: float = Query(..., ge=-180, le=180),
          km: float = Query(250, ge=10, le=800),
          count: int = Query(4, ge=1, le=20)):
    """The nearest CWC gauges to a point, with what they are reading now.

    For a town with no model behind it this is the most useful true thing the
    system has: not a simulated depth for their street, but the real level at
    the nearest official gauge, its official danger mark, and how old the
    reading is.
    """
    from pravaah import live
    try:
        return live.river_at(lat, lon, km, count)
    except Exception as e:
        raise HTTPException(503, f"river levels unavailable: {e}")
