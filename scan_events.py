import json, urllib.parse, urllib.request, datetime as dt

EVENTS = [
    ("Chennai 2015",      (80.10,12.85,80.35,13.20), "2015-12-02"),
    ("Chennai 2021",      (80.10,12.85,80.35,13.20), "2021-11-11"),
    ("Chennai Michaung",  (80.10,12.85,80.35,13.20), "2023-12-04"),
    ("Kerala 2018",       (76.30, 9.10,76.90, 9.80), "2018-08-17"),
    ("Patna 2019",        (85.05,25.55,85.30,25.68), "2019-09-30"),
    ("Hyderabad 2020",    (78.30,17.25,78.65,17.55), "2020-10-15"),
    ("Bengaluru 2022",    (77.55,12.85,77.80,13.05), "2022-09-06"),
    ("Assam 2022",        (91.50,26.00,92.90,26.80), "2022-06-19"),
    ("Delhi Yamuna 2023", (77.15,28.55,77.35,28.75), "2023-07-14"),
    ("Vijayawada 2024",   (80.55,16.42,80.80,16.60), "2024-09-02"),
]

def s1(bbox, start, end):
    w,s,e,n = bbox
    poly = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"
    q = urllib.parse.urlencode({
        "platform": "Sentinel-1", "intersectsWith": poly,
        "start": start+"T00:00:00Z", "end": end+"T23:59:59Z",
        "processingLevel": "GRD_HD", "output": "json"})
    url = "https://api.daac.asf.alaska.edu/services/search/param?" + q
    with urllib.request.urlopen(url, timeout=120) as r:
        d = json.load(r)
    rows = d[0] if d and isinstance(d[0], list) else d
    out = {}
    for x in rows:
        t = x.get("startTime","")[:10]
        out.setdefault(t, x.get("flightDirection"))
    return out

for name, bbox, peak in EVENTS:
    p = dt.date.fromisoformat(peak)
    acqs = s1(bbox, str(p - dt.timedelta(days=14)), str(p + dt.timedelta(days=14)))
    best, bd = None, 99
    marks = []
    for d_, direc in sorted(acqs.items()):
        off = (dt.date.fromisoformat(d_) - p).days
        marks.append(f"{d_}({off:+d})")
        if 0 <= off < bd:          # post-peak, closest
            best, bd = d_, off
    flag = "OK " if (best is not None and bd <= 3) else "no "
    print(f"{flag}{name:<18} peak {peak}  best post-peak: {best} (+{bd}d)" if best else f"{flag}{name:<18} peak {peak}  best post-peak: NONE")
    print(f"     all: {' '.join(marks) if marks else '(none)'}")
