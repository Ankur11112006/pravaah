"""Map tiles for offline use, fetched once by the district server.

A flood is exactly when the network is not there, so the map has to already be on
the phone. The tiles come from OpenStreetMap, but NOT from every handset: the
OSMF tile policy forbids bulk downloading, and thousands of phones each pulling a
few hundred tiles is precisely that. So this server fetches each tile once, keeps
it, and serves it to any phone that asks. One polite client instead of a crowd.

Sizes, measured rather than guessed, for a box 30 km around a ward:
    z9-12   1.3 MB      z9-13   4.4 MB (320 tiles)      z9-14   15 MB

z9-13 is the default: enough to see which road is which, small enough to download
on a phone before anything has happened.
"""
import io, math, os, time, urllib.request

CACHE = "data/tiles"
UA = {"User-Agent": "pravaah-flood-dss/1.0 (district server; one fetch per tile, "
                    "cached and reused; contact via the project README)"}
SRC = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

# OSMF asks for no more than a couple of threads and a real User-Agent. One
# request at a time with a small gap is slower than we could go and is the point.
POLITE_GAP = 0.12
_last = [0.0]


def deg2num(lat, lon, z):
    r = math.radians(lat)
    k = 2 ** z
    x = int((lon + 180.0) / 360.0 * k)
    y = int((1.0 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2.0 * k)
    return max(0, min(k - 1, x)), max(0, min(k - 1, y))


def tiles_for(w, s, e, n, zmin=9, zmax=13):
    """Every (z, x, y) covering a bounding box, coarse zooms first.

    Coarse first matters: a half-finished download still draws a whole map, just
    a blurry one, instead of a sharp postage stamp in a sea of grey.
    """
    out = []
    for z in range(zmin, zmax + 1):
        x0, y0 = deg2num(n, w, z)
        x1, y1 = deg2num(s, e, z)
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                out.append((z, x, y))
    return out


def box_around(lat, lon, km):
    """A bounding box `km` around a point, corrected for latitude."""
    dlat = km / 110.574
    dlon = km / (111.320 * math.cos(math.radians(lat)) or 1e-9)
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def path_for(z, x, y):
    return os.path.join(CACHE, str(z), str(x), f"{y}.png")


def have(z, x, y):
    p = path_for(z, x, y)
    return os.path.exists(p) and os.path.getsize(p) > 0


def fetch(z, x, y):
    """One tile, from disk if we already have it. Returns bytes or None."""
    p = path_for(z, x, y)
    if have(z, x, y):
        return io.open(p, "rb").read()
    gap = POLITE_GAP - (time.time() - _last[0])
    if gap > 0:
        time.sleep(gap)
    _last[0] = time.time()
    req = urllib.request.Request(SRC.format(z=z, x=x, y=y), headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
    except Exception:
        return None
    if not data:
        return None
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, "wb") as f:
        f.write(data)
    return data


def plan(lat, lon, km=30, zmin=9, zmax=13, tile_kb=14):
    """What a phone would have to download, before it starts.

    Nobody should be asked to accept a download whose size is not on the button,
    so the count is exact and the size is measured from what is already cached
    where we have it, estimated where we do not.
    """
    w, s, e, n = box_around(lat, lon, km)
    t = tiles_for(w, s, e, n, zmin, zmax)
    known = sum(os.path.getsize(path_for(*c)) for c in t if have(*c))
    n_known = sum(1 for c in t if have(*c))
    est = known + (len(t) - n_known) * tile_kb * 1024
    return dict(
        bbox=[round(v, 4) for v in (w, s, e, n)],
        zmin=zmin, zmax=zmax, km=km,
        tiles=[list(c) for c in t],
        count=len(t), cached=n_known,
        bytes=int(est), mb=round(est / 1024 / 1024, 1),
    )
