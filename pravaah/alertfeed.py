"""Normalised alert feed for the citizen app.

SACHET is the source of truth and it is public, but its records carry seventeen
fields with inconsistent names, times in three formats and severity in two
parallel systems (CAP words and IMD colours). The phone should not have to know
any of that, so the shaping happens here, once, on the server.

Everything is cached to disk. During a flood the phone may be on 2G and the
laptop may be on nothing at all, and a stale alert with its age shown is worth
far more than a spinner.
"""
import datetime as dt
import io, json, math, os, re, time

CACHE = "out/alerts_cache.json"
TTL = 600          # ten minutes; SACHET itself updates on that sort of cadence

# CAP severity words and IMD colours both appear, sometimes disagreeing. One
# scale, ordered, so the phone can sort and colour without a lookup table.
LEVEL = {
    "extreme": 3, "severe": 3, "red": 3,
    "moderate": 2, "orange": 2, "amber": 2,
    "minor": 1, "yellow": 1, "alert": 1, "watch": 1,
    "green": 0, "unknown": 1,
}
LABEL = {3: "High", 2: "Medium", 1: "Low", 0: "Advisory"}

# What a flood app is for. Everything else is still served, but flagged, so the
# app can lead with water without pretending the rest does not exist.
WATER = ("flood", "rain", "thunder", "cyclone", "storm", "surge", "waterlog",
         "landslide", "tsunami", "heavy")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def centroid(a):
    """(lat, lon) or None. The field is a string and the order is undocumented,
    so the pair is told apart by where India actually is."""
    c = a.get("centroid")
    if not c:
        return None
    parts = [p for p in (_num(x) for x in re.split(r"[(),\s]+", str(c))) if p is not None]
    if len(parts) < 2:
        return None
    x, y = parts[0], parts[1]
    if 6 <= x <= 38 and 68 <= y <= 98:
        return x, y
    if 6 <= y <= 38 and 68 <= x <= 98:
        return y, x
    return None


def _when(v):
    """SACHET sends times as ISO, as epoch millis, and as `Mon Sep 04 12:28:00
    IST 2026`. Return an ISO string, or the raw value if it is none of those."""
    if v in (None, ""):
        return None
    s = str(v).strip()
    if s.isdigit():
        n = int(s)
        return dt.datetime.fromtimestamp(n / (1000 if n > 1e11 else 1),
                                         dt.timezone.utc).isoformat()
    for fmt in ("%a %b %d %H:%M:%S %Z %Y", "%a %b %d %H:%M:%S %Y",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(s.replace("IST", "").replace("  ", " ").strip()
                                        if "%Z" not in fmt else s, fmt).isoformat()
        except ValueError:
            continue
    return s


def _issuer(a):
    for k in ("alert_source", "sender_org_id", "sender", "source"):
        v = a.get(k)
        if v:
            return str(v).strip()
    return "Government of India"


def shape(a):
    """One SACHET record, in the shape the phone actually renders."""
    sev_raw = str(a.get("severity") or a.get("severity_level") or "").lower()
    col_raw = str(a.get("severity_color") or "").lower()
    level = LEVEL.get(sev_raw, LEVEL.get(col_raw, 1))
    kind = (a.get("disaster_type") or a.get("type") or "Alert").strip()
    c = centroid(a)
    area = (a.get("area_description") or a.get("area_covered") or "").strip()
    return dict(
        id=str(a.get("identifier") or a.get("alert_id_sdma_autoinc") or ""),
        kind=kind,
        issuer=_issuer(a),
        severity=LABEL[level],
        level=level,
        area=area,
        message=(a.get("warning_message") or "").strip(),
        start=_when(a.get("effective_start_time")),
        end=_when(a.get("effective_end_time")),
        lat=c[0] if c else None,
        lon=c[1] if c else None,
        water=any(w in kind.lower() for w in WATER),
    )


def _read_cache():
    if not os.path.exists(CACHE):
        return None
    try:
        return json.load(io.open(CACHE, encoding="utf-8"))
    except (ValueError, OSError):
        return None


def fetch(force=False):
    """Live alerts, or the last good ones. Never raises for the caller.

    Returns (rows, fetched_at_epoch, live). `live` false means the network was
    unreachable and these came off disk, which the app is expected to say.
    """
    cached = _read_cache()
    if not force and cached and time.time() - cached.get("at", 0) < TTL:
        return cached["rows"], cached["at"], True
    try:
        from . import sachet
        rows = [shape(a) for a in sachet.alerts()]
        rows = [r for r in rows if r["kind"]]
        rows.sort(key=lambda r: (-r["level"], r["start"] or ""), reverse=False)
        rows.sort(key=lambda r: -r["level"])
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(dict(at=time.time(), rows=rows),
                  io.open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        return rows, time.time(), True
    except Exception:
        if cached:
            return cached["rows"], cached.get("at", 0), False
        return [], 0, False


def near(rows, lat, lon, km=200):
    """Alerts whose centroid is within `km`, nearest first.

    An alert with no centroid is kept, at the end: SACHET does not always carry
    one, and dropping it would hide a real warning for a formatting reason.
    """
    out = []
    for r in rows:
        if r["lat"] is None:
            out.append((1e9, r))
            continue
        d = math.hypot(r["lat"] - lat, (r["lon"] - lon) * math.cos(math.radians(lat))) * 111.0
        if d <= km:
            out.append((round(d, 1), r))
    out.sort(key=lambda x: x[0])
    return [dict(r, km=None if d >= 1e9 else d) for d, r in out]
