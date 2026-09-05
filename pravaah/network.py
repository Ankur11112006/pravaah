"""Road graph carrying terrain, not a snapshot.

Each edge stores the LOWEST ground elevation along it, because that is the point
that goes under first and governs what can still pass. Depth at any time is then
level(t) minus that elevation, so the whole timeline is analytic and we never
rasterise 24 frames a day."""
import json, math, collections
import numpy as np, rasterio, networkx as nx

def _length_m(lon, lat):
    return sum(math.hypot((lon[i+1]-lon[i])*111320*math.cos(math.radians(lat[i])),
                          (lat[i+1]-lat[i])*110540) for i in range(len(lon)-1))

def build(osm_path, dem_path):
    with rasterio.open(dem_path) as s:
        dem, inv, H, W = s.read(1), ~s.transform, s.height, s.width

    def elev(lon, lat, raised):
        """Lowest ground along the segment, as a 10th percentile rather than a raw
        minimum: one stray 30 m pixel that lands in the river should not condemn a
        whole road. Raised structures take a high percentile instead, because the
        deck sits above the terrain the DEM sampled."""
        c, r = inv * (np.asarray(lon), np.asarray(lat))
        r, c = np.floor(r).astype(int), np.floor(c).astype(int)
        ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
        if not ok.any(): return np.nan
        v = dem[r[ok], c[ok]].astype("float32")
        v = v[np.isfinite(v) & (v > 0)]
        if not len(v): return np.nan
        return float(np.percentile(v, 90 if raised else 10))

    def structure(tags):
        if tags.get("tunnel", "no") != "no": return "tunnel"
        if tags.get("bridge", "no") != "no": return "bridge"
        if tags.get("embankment", "no") != "no": return "embankment"
        return ""

    ways = [w for w in json.load(open(osm_path, encoding="utf-8"))["elements"]
            if w.get("geometry") and len(w["geometry"]) >= 2 and "nodes" in w]
    use = collections.Counter()
    for w in ways: use.update(set(w["nodes"]))

    G = nx.Graph()
    for w in ways:
        ids, geo, tags = w["nodes"], w["geometry"], w.get("tags", {})
        if len(ids) != len(geo): continue
        cuts = [0] + [i for i in range(1, len(ids)-1) if use[ids[i]] > 1] + [len(ids)-1]
        for a, b in zip(cuts, cuts[1:]):
            seg = geo[a:b+1]
            if len(seg) < 2: continue
            lon = [p["lon"] for p in seg]; lat = [p["lat"] for p in seg]
            L = _length_m(lon, lat)
            if L <= 0 or ids[a] == ids[b]: continue
            if G.has_edge(ids[a], ids[b]) and G[ids[a]][ids[b]]["length"] <= L: continue
            st = structure(tags)
            step = max(1, (len(lon)-1)//7)           # <=8 points is plenty to draw
            geom = [[round(lon[i], 5), round(lat[i], 5)]
                    for i in range(0, len(lon), step)]
            if geom[-1] != [round(lon[-1], 5), round(lat[-1], 5)]:
                geom.append([round(lon[-1], 5), round(lat[-1], 5)])
            G.add_edge(ids[a], ids[b], length=L, structure=st, geom=geom,
                       bed=elev(lon, lat, st in ("bridge", "embankment")),
                       name=tags.get("name", ""), hw=tags.get("highway", ""),
                       lon=lon[len(lon)//2], lat=lat[len(lat)//2])
    return G

def mode_at(bed, level, modes, structure=""):
    """What can still use a road whose controlling point sits at `bed`.

    A bridge is NOT assumed passable. A terrain model cannot see a deck, so the
    honest answer for a bridge is that its status is unknown and a human has to
    confirm it. Bridges are the single points of failure in a flood; guessing
    either way is worse than saying so."""
    if structure == "bridge":
        return "unknown", float("nan")
    d = max(0.0, level - bed) if np.isfinite(bed) else 0.0
    for lim, m in modes:
        if d < lim: return m, d
