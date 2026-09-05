"""Client for SACHET, NDMA's National Disaster Alert Portal.

This is the channel the project's CAP 1.2 output is written for, and it is
readable: live alerts as JSON, with severity, area, centroid, validity window
and the warning text in the local language. No key, no login.
"""
import json, urllib.request

BASE = "https://sachet.ndma.gov.in/cap_public_website"
UA = {"User-Agent": "Mozilla/5.0 (pravaah flood research)"}
WATER = ("flood", "flash flood", "rain", "thunder", "cyclone", "storm surge")


def alerts():
    req = urllib.request.Request(f"{BASE}/FetchAllAlertDetails", headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def water_alerts(rows=None):
    """Only the alerts this project cares about."""
    rows = rows if rows is not None else alerts()
    return [a for a in rows
            if any(w in str(a.get("disaster_type", "")).lower() for w in WATER)]


def centroid(a):
    """(lat, lon) if the alert carries one. The field is a string, and the order
    is not documented, so it is read defensively rather than trusted."""
    c = a.get("centroid")
    if not c:
        return None
    try:
        parts = [float(x) for x in str(c).replace("(", " ").replace(")", " ")
                 .replace(",", " ").split()]
    except ValueError:
        return None
    if len(parts) < 2:
        return None
    x, y = parts[0], parts[1]
    # India sits at 6-38 N, 68-98 E, which is enough to tell the pair apart
    if 6 <= x <= 38 and 68 <= y <= 98:
        return x, y
    if 6 <= y <= 38 and 68 <= x <= 98:
        return y, x
    return None


def near(lat, lon, km=150, rows=None):
    """Water alerts whose centroid is within `km` of a point."""
    import math
    out = []
    for a in water_alerts(rows):
        c = centroid(a)
        if not c:
            continue
        d = math.hypot(c[0] - lat, c[1] - lon) * 111.0
        if d <= km:
            out.append((round(d, 1), a))
    return sorted(out, key=lambda x: x[0])
