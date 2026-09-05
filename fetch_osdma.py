"""Odisha's official cyclone and flood shelters, from OSDMA.

OpenStreetMap has two mapped shelter campuses inside the Mahanadi AOI, which
would put the delta's evacuation capacity at 252 people. That is not a finding
about Odisha, it is a finding about OSM coverage: the state has built 814 shelter
buildings, and OSDMA publishes where they are.

    https://www.osdma.org/shelter-locations/?district=<DISTRICT>

The page carries the records as a JSON array in an inline script, so no scraping
of rendered HTML is needed. Public data, no key, no login.

    .venv/Scripts/python.exe fetch_osdma.py

Writes data/osdma_shelters.json. These are POINTS, not campus polygons, so they
carry a location and not an area; build_shelters.py measures each one's roof from
the Microsoft footprint it stands on, exactly as it does for an OSM campus.
"""
import io, json, os, re, sys, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

OUT = "data/osdma_shelters.json"
URL = "https://www.osdma.org/shelter-locations/?district={}"
ARRAY = re.compile(r"var\s+shelters1\s*=\s*(\[.*?\])\s*;", re.S)
DISTRICTS = """ANGUL BALANGIR BALASORE BARAGARH BHADRAK BOUDH CUTTACK DEOGARH
DHENKANAL GAJAPATI GANJAM JAGATSINGHPUR JAJPUR JHARSUGUDA KALAHANDI KANDHAMAL
KENDRAPARA KEONJHAR KHORDHA KORAPUT MALKANGIRI MAYURBHANJ NABARANGPUR NAYAGARH
NUAPADA PURI RAYAGADA SAMBALPUR SONEPUR SUNDARGARH""".split()


def one(d):
    req = urllib.request.Request(URL.format(d),
                                 headers={"User-Agent": "pravaah/1.0 research"})
    with urllib.request.urlopen(req, timeout=90) as r:
        html = r.read().decode("utf-8", "replace")
    m = ARRAY.search(html)
    if not m:
        return []
    # the array is JavaScript, not JSON: it ends with a trailing comma, which
    # json.loads rejects outright
    body = re.sub(r",\s*\]$", "]", m.group(1).strip())
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        print(f"    {d}: array found but did not parse ({e})")
        return []


def main():
    rows, seen = [], set()
    for i, d in enumerate(DISTRICTS, 1):
        try:
            got = one(d)
        except Exception as e:
            print(f"  {d:<16} failed: {e}")
            continue
        new = 0
        for s in got:
            try:
                key = (round(float(s["lat"]), 5), round(float(s["lon"]), 5))
            except (KeyError, TypeError, ValueError):
                continue
            if key in seen:
                continue                      # the same shelter listed twice
            seen.add(key)
            rows.append(dict(lat=key[0], lon=key[1],
                             name=(s.get("name") or s.get("location") or "").strip(),
                             district=(s.get("district") or d).strip(),
                             block=(s.get("block") or "").strip(),
                             village=(s.get("village") or "").strip(),
                             kind=(s.get("shelter") or "").strip()))
            new += 1
        print(f"  {i:>2}/{len(DISTRICTS)}  {d:<16}{len(got):>5} listed{new:>6} new")
        time.sleep(0.4)                       # a government site, not a target

    if not rows:
        sys.exit("nothing retrieved; the page layout may have changed")
    json.dump(dict(source="OSDMA shelter-locations, https://www.osdma.org/shelter-locations/",
                   retrieved=time.strftime("%Y-%m-%d"), shelters=rows),
              io.open(OUT, "w", encoding="utf-8"), indent=1)
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"\n  {len(rows):,} shelters across {len({r['district'] for r in rows})} districts")
    for k, n in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f"    {k or '(unlabelled)':<20}{n:>5}")
    print(f"  wrote {OUT}")


if __name__ == "__main__":
    main()
